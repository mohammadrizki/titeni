from secrets import token_urlsafe

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.authentication import accounts_with_email
from apps.evidence.external import token_digest
from apps.evidence.models import EvidenceIntegration, EvidenceSource


class Command(BaseCommand):
    help = "Issue, rotate, or disable the scoped bearer credential for an evidence integration."

    def add_arguments(self, parser) -> None:
        parser.add_argument("email")
        parser.add_argument("program_code")
        parser.add_argument("source_code")
        actions = parser.add_mutually_exclusive_group()
        actions.add_argument("--rotate", action="store_true")
        actions.add_argument("--disable", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        account = accounts_with_email(options["email"]).select_for_update(no_key=True).first()
        if account is None:
            raise CommandError("Akun integrasi tidak ditemukan.")
        source = EvidenceSource.objects.filter(
            program__code=options["program_code"], code=options["source_code"]
        ).first()
        if source is None:
            raise CommandError("Sumber bukti tidak ditemukan pada prodi ini.")
        credential = EvidenceIntegration.objects.select_for_update().filter(account=account).first()
        if credential is not None and credential.source_id != source.pk:
            raise CommandError("Akun sudah terikat pada sumber bukti lain.")
        if options["disable"]:
            if credential is None:
                raise CommandError("Akun belum memiliki kredensial integrasi.")
            credential.enabled = False
            credential.save(update_fields=["enabled", "updated_at"])
            return
        if not account.is_active:
            raise CommandError("Akun integrasi harus aktif.")
        if credential is not None and not options["rotate"]:
            raise CommandError("Kredensial sudah ada. Gunakan --rotate untuk menggantinya.")
        if credential is None and options["rotate"]:
            raise CommandError("Akun belum memiliki kredensial integrasi.")
        token = f"titeni_{token_urlsafe(32)}"
        if credential is None:
            EvidenceIntegration.objects.create(
                account=account, source=source, token_digest=token_digest(token)
            )
        else:
            credential.token_digest = token_digest(token)
            credential.enabled = True
            credential.save(update_fields=["token_digest", "enabled", "updated_at"])
        self.stdout.write(token)
