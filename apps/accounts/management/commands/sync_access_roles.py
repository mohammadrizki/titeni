from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.accounts.role_catalog import synchronize_roles


class Command(BaseCommand):
    help = "Preview or synchronize the managed role matrix after migrations."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--actor-id", help="UUID of the authorizing active superuser.")
        parser.add_argument("--apply", action="store_true", help="Persist the displayed changes.")

    def handle(self, *args, **options) -> None:
        actors = User.objects.filter(is_superuser=True, is_active=True)
        try:
            actor = actors.get(pk=options["actor_id"]) if options["actor_id"] else actors.get()
        except (User.DoesNotExist, User.MultipleObjectsReturned, ValidationError) as error:
            raise CommandError(
                "Specify the UUID of an active superuser using --actor-id."
            ) from error
        try:
            report = synchronize_roles(actor, apply=options["apply"])
        except ValueError as error:
            raise CommandError(str(error)) from error
        for name, added, removed, created in report:
            label = "baru" if created else "ada"
            self.stdout.write(f"{name} ({label}) +{added} -{removed}")
        if not options["apply"]:
            self.stdout.write("Pratinjau. Gunakan --apply untuk menyimpan.")
