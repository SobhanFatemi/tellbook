"""Targeted repair for the two user-reported, source-verified catalog credits."""
import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from catalog.models import Book


class Command(BaseCommand):
    help = "Preview known duplicate/publisher credits; --apply requires a before-state audit path."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--audit-file')

    def handle(self, *args, **options):
        fixes = []
        for book in Book.objects.filter(title__in=['1984', '۱۹۸۴', 'آخرين تزار', 'آخرین تزار']):
            credits = list(book.book_contributions.filter(role='author').values('id', 'person_id', 'person__name'))
            names = {c['person__name'] for c in credits}
            remove_names = set()
            if book.title in ['1984', '۱۹۸۴'] and {'جورج اوورل', 'جورج اورول'} <= names:
                remove_names.add('جورج اوورل')
            if book.title in ['آخرين تزار', 'آخرین تزار'] and 'ادوارد رادزينسکي' in names:
                remove_names.update({'ماهي', 'ماهی'} & names)
            remove = [c['id'] for c in credits if c['person__name'] in remove_names]
            if remove:
                fixes.append({'book_id': book.pk, 'title': book.title, 'before': credits, 'remove_ids': remove})
        self.stdout.write(json.dumps(fixes, ensure_ascii=False, indent=2))
        if options['apply']:
            if not options['audit_file']:
                from django.core.management.base import CommandError
                raise CommandError('--audit-file is required')
            # Exclusive create prevents overwriting a prior before-state.
            with Path(options['audit_file']).open('x') as output:
                json.dump(fixes, output, ensure_ascii=False, indent=2)
            with transaction.atomic():
                for fix in fixes:
                    Book.objects.get(pk=fix['book_id']).book_contributions.filter(pk__in=fix['remove_ids']).delete()
            self.stdout.write(f'Applied {len(fixes)} targeted book repairs.')
