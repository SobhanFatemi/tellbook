from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateReceiptStorage(FileSystemStorage):
    @property
    def base_location(self):
        return str(getattr(settings, 'PRIVATE_MEDIA_ROOT', Path(settings.MEDIA_ROOT).parent / 'private_media'))

    def url(self, name):
        raise ValueError('Receipts must be accessed through the authorized download endpoint.')
