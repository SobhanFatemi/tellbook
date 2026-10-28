"""Reconcile explicitly confirmed legacy Rial files, never guess changed prices."""
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from catalog.locking import lock_catalog
from publisher_catalog.models import PublisherImportBatch, Edition
from publisher_catalog.parsing import read_publisher_rows
from publisher_catalog.services import normalize_persian, clean_title_and_extract_author
from publisher_catalog.staging import normalize_identifier


class Command(BaseCommand):
    help = 'Dry-run legacy Rial price correction for specified source batches; --apply requires an audit path.'

    def add_arguments(self, parser):
        parser.add_argument('--batch', type=int, action='append', required=True)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--audit', required=True)

    @transaction.atomic
    def handle(self, *args, **opts):
        lock_catalog()
        reports=[]
        seen=set()
        for pk in opts['batch']:
            batch=PublisherImportBatch.objects.select_related('profile','publisher').get(pk=pk)
            if not batch.publisher_id or not batch.profile_id or batch.status != 'done':
                raise CommandError('Only completed legacy single-publisher batches are supported.')
            if batch.publisher_id in seen:
                raise CommandError('Choose only the latest authoritative batch per publisher.')
            seen.add(batch.publisher_id)
            profile=batch.profile
            # Read only matching identifiers and raw price; unrelated old metadata is not rewritten.
            mapping={k:v for k,v in profile.column_mapping.items() if k in {'title','price','isbn','sku'}}
            raw_profile=SimpleNamespace(price_unit='toman',mode='single',column_mapping=mapping,sheet_name=profile.sheet_name,header_row_index=profile.header_row_index)
            with batch.file.open('rb') as source:
                rows,_=read_publisher_rows(source,raw_profile,include_invalid=True)
            indexes={key:defaultdict(list) for key in ['isbn','sku','title']}
            for row in rows:
                if row.get('error'):
                    continue
                title,_=clean_title_and_extract_author(row['title'],publisher_hint=batch.publisher.name)
                indexes['title'][normalize_persian(title)].append(row)
                for key in ['isbn','sku']:
                    if row.get(key): indexes[key][normalize_identifier(row[key])].append(row)
            for ed in Edition.objects.filter(publisher=batch.publisher).select_related('book'):
                matches=[]
                for key in ['isbn','sku']:
                    if getattr(ed,key):
                        matches=indexes[key].get(normalize_identifier(getattr(ed,key)),[])
                        if matches: break
                if not matches: matches=indexes['title'].get(normalize_persian(ed.book.title),[])
                prices={Decimal(row['price']) for row in matches}
                entry={'edition':ed.pk,'book':ed.book_id,'title':ed.book.title,'publisher':batch.publisher.name,'source_batch':pk,'before':str(ed.price)}
                if len(prices)!=1:
                    entry.update(status='unresolved',reason='No unique exact source price')
                else:
                    raw=next(iter(prices));correct=raw/10
                    entry.update(source_rial=str(raw),expected_toman=str(correct))
                    if correct != correct.to_integral_value():
                        entry.update(status='unresolved',reason='Fractional Toman source')
                    elif ed.price==correct:
                        entry['status']='already_correct'
                    elif ed.price!=raw:
                        entry.update(status='unresolved',reason='Current price differs from raw source and converted price; preserve manual change')
                    else:
                        entry['status']='convert'
                        if opts['apply']:
                            ed.price=correct
                            ed.save(update_fields=['price','updated_at'])
                if opts['apply']:
                    note = 'قیمت فعلی با ردیف یکتای فایل اصلی تطبیق ندارد؛ پیش از تأیید قیمت، فایل ناشر را بررسی کنید.' if entry['status']=='unresolved' else ''
                    ed.price_review_note=note
                    ed.save(update_fields=['price_review_note','updated_at'])
                reports.append(entry)
            if opts['apply']:
                profile.price_unit='rial';profile.save(update_fields=['price_unit','updated_at'])
        path=Path(opts['audit']);path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists(): raise CommandError('Audit path already exists; use a fresh path.')
        path.write_text(json.dumps({'applied':opts['apply'],'entries':reports},ensure_ascii=False,indent=2))
        counts={state:sum(row['status']==state for row in reports) for state in ['convert','already_correct','unresolved']}
        self.stdout.write(json.dumps(counts))
        self.stdout.write(str(path))
