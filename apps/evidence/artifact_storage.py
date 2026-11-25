from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateArtifactStorage(FileSystemStorage):
    @property
    def location(self) -> str:
        return str(Path(settings.EVIDENCE_ARTIFACT_ROOT).resolve())

    def url(self, name: str | None) -> str:
        raise NotImplementedError("Evidence artifacts are available through authorized downloads.")


def evidence_artifact_storage() -> PrivateArtifactStorage:
    return PrivateArtifactStorage(file_permissions_mode=0o600, directory_permissions_mode=0o700)


def artifact_upload_path(instance, filename: str) -> str:
    return f"records/{instance.record_id}/{uuid4().hex}.pdf"
