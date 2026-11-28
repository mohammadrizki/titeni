from django.db import migrations

FORMER_NAME = "Kaprodi"
NEW_NAME = "Penanggung Jawab Akademik Prodi"


def rename_role(apps, schema_editor, old_name, new_name):
    roles = apps.get_model("accounts", "AccessRole").objects.using(schema_editor.connection.alias)
    role = roles.select_for_update().filter(name=old_name).first()
    if role is None:
        return
    if roles.filter(name=new_name).exists():
        raise RuntimeError(
            f"Both '{old_name}' and '{new_name}' exist. "
            "Resolve the role duplication before applying this migration."
        )
    roles.filter(pk=role.pk).update(name=new_name)


def rename_forward(apps, schema_editor):
    rename_role(apps, schema_editor, FORMER_NAME, NEW_NAME)


def rename_backward(apps, schema_editor):
    rename_role(apps, schema_editor, NEW_NAME, FORMER_NAME)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0006_rename_synthesis_reviewer_role")]

    operations = [migrations.RunPython(rename_forward, rename_backward)]
