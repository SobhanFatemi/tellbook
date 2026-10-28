import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from catalog.categories import normalize_category
from catalog.locking import lock_catalog
from catalog.models import Book
from publisher_catalog.models import PublisherImportRow


class Command(BaseCommand):
    help = 'Preview or apply conservative category cleanup without guessing subjects.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--report', required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        lock_catalog()
        path = Path(options['report'])
        if path.exists():
            raise CommandError('Use a fresh report path.')
        changes = []
        for book in Book.objects.select_for_update().all():
            fields = {}
            for field in ['category', 'subcategory']:
                before = getattr(book, field)
                after = normalize_category(before)
                if before != after:
                    fields[field] = {'before': before, 'after': after}
                    setattr(book, field, after)
            if fields:
                changes.append({'book': book.pk, 'fields': fields})
                if options['apply']:
                    book.save(update_fields=[*fields, 'updated_at'])
        # Existing review decisions stay intact; the fingerprint guard still
        # requires rebuilding stale previews before applying catalog changes.
        if options['apply']:
            for row in PublisherImportRow.objects.select_for_update().filter(batch__status='review'):
                data = dict(row.data)
                for field in ['category', 'subcategory']:
                    if field in data:
                        data[field] = normalize_category(data[field])
                if data != row.data:
                    row.data = data
                    row.save(update_fields=['data'])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'applied': options['apply'], 'changes': changes}, ensure_ascii=False, indent=2))
        self.stdout.write(f'{len(changes)} books; report: {path}')
