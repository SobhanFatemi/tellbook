"""Move historical public receipts to the authenticated private storage."""
import hashlib
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from payments.storage import PrivateReceiptStorage


class Command(BaseCommand):
    help = 'Move existing payment_proofs out of public media without changing database paths.'

    def handle(self, *args, **options):
        source = Path(settings.MEDIA_ROOT) / 'payment_proofs'
        destination = Path(PrivateReceiptStorage().location) / 'payment_proofs'
        if source.resolve() == destination.resolve():
            raise CommandError('Private receipt storage must be outside public media.')
        if not source.exists():
            self.stdout.write('No public receipts to move.')
            return
        files = list(source.rglob('*'))
        if source.is_symlink() or any(p.is_symlink() for p in files):
            raise CommandError('Refusing to relocate symlinks in receipt storage.')
        moved = 0
        for file in files:
            if not file.is_file():
                continue
            target = destination / file.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if hashlib.sha256(file.read_bytes()).digest() != hashlib.sha256(target.read_bytes()).digest():
                    raise CommandError('A different private file already occupies a receipt path; resolve it before retrying.')
                file.unlink()
            else:
                shutil.move(str(file), str(target))
            moved += 1
        self.stdout.write(self.style.SUCCESS(f'Privatized {moved} receipt file(s).'))
