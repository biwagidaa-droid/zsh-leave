import logging
import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible

logger = logging.getLogger(__name__)


@deconstructible
class PrivateAttachmentStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(
            location=None,
            base_url=None,
            file_permissions_mode=0o600,
            directory_permissions_mode=0o700,
        )

    @property
    def location(self):
        return str(settings.ZSH_ATTACHMENT_ROOT)

    @property
    def base_url(self):
        return None

    def _save(self, name, content):
        root = self.location
        os.makedirs(root, mode=0o700, exist_ok=True)
        self._ensure_private_permissions(root, 0o700)
        stored_name = super()._save(name, content)
        file_path = self.path(stored_name)
        directory = file_path.rsplit("/", 1)[0]
        try:
            while directory.startswith(root + "/"):
                self._ensure_private_permissions(directory, 0o700)
                directory = directory.rsplit("/", 1)[0]
            self._ensure_private_permissions(file_path, 0o600)
        except OSError:
            try:
                super().delete(stored_name)
            except OSError:
                logger.error("Failed to clean up an attachment after permissions failed.")
            raise
        return stored_name

    @staticmethod
    def _ensure_private_permissions(path, mode):
        os.chmod(path, mode)
