"""Finish conversion of confirmed legacy Rial test data, using the original audit."""
import json
from decimal import Decimal
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime
from catalog.locking import lock_catalog
from publisher_catalog.models import Edition, PublisherImportRow
from requests_orders.models import Quote
from payments.models import Payment


class Command(BaseCommand):
    help = 'Dry-run remaining legacy currency corrections; requires the original reconciliation audit.'

    def add_arguments(self, parser):
        parser.add_argument('--source-audit', required=True)
        parser.add_argument('--report', required=True)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--legacy-before', required=True, help='ISO timestamp when original correction began; never rewrite newer orders')

    @transaction.atomic
    def handle(self, *args, **options):
        lock_catalog()
        cutoff = parse_datetime(options['legacy_before'])
        if not cutoff or cutoff.utcoffset() is None:
            raise CommandError('Use an ISO timestamp with timezone.')
        destination = Path(options['report'])
        if destination.exists():
            raise CommandError('Choose a new report path.')
        source = json.loads(Path(options['source_audit']).read_text())
        if not source.get('applied'):
            raise CommandError('Source audit must describe the applied initial conversion.')
        changes, skipped = [], []
        for entry in source['entries']:
            raw = Decimal(entry['before'])
            if entry['status'] not in {'convert', 'unresolved'} or raw <= 0:
                continue
            converted = raw / 10
            if converted != converted.to_integral_value():
                skipped.append({'edition': entry['edition'], 'reason': 'Fractional Toman; review required'})
                continue
            edition = Edition.objects.select_for_update().filter(pk=entry['edition'], book_id=entry['book']).first()
            if not edition:
                continue
            if entry['status'] == 'unresolved':
                if edition.price == raw:
                    changes.append({'model': 'edition', 'id': edition.pk, 'before': str(raw), 'after': str(converted)})
                    if options['apply']:
                        # Preserve the source mismatch flag: converting units does not resolve which edition/price is current.
                        edition.price = converted
                        edition.save(update_fields=['price', 'updated_at'])
                        for row in PublisherImportRow.objects.select_for_update().filter(batch__status='review', before__edition_id=edition.pk):
                            if str(row.before.get('price')) == str(raw):
                                row.before = {**row.before, 'price': str(converted)}
                                row.save(update_fields=['before'])
                        # Keep the batch fingerprint stale so confirmation still requires a refreshed preview.
                elif edition.price != converted:
                    skipped.append({'edition': edition.pk, 'reason': 'Changed since original audit'})
            # Only exact legacy source-linked snapshots with no other monetary components.
            for quote in Quote.objects.select_for_update().filter(source_listing=edition, book_cost=raw, service_fee=0, shipping_fee=0, created_at__lt=cutoff):
                order = getattr(quote, 'order', None)
                if order and (order.total_price != raw or order.discount_amount or order.stock_items.exists()):
                    skipped.append({'quote': quote.pk, 'reason': 'Order components require manual review'})
                    continue
                payment = Payment.objects.select_for_update().filter(order=order).first() if order else None
                if payment and payment.base_amount != raw:
                    skipped.append({'quote': quote.pk, 'reason': 'Payment mismatch'})
                    continue
                if order and order.refunds.exists():
                    skipped.append({'quote': quote.pk, 'reason': 'Refund history requires review'})
                    continue
                changes.append({'model': 'quote/order/payment', 'id': quote.pk, 'order': order.pk if order else None, 'payment': payment.pk if payment else None, 'before': str(raw), 'after': str(converted)})
                if options['apply']:
                    quote.book_cost = converted
                    quote.save(update_fields=['book_cost', 'updated_at'])
                    if order:
                        order.total_price = converted
                        order.save(update_fields=['total_price', 'updated_at'])
                    if payment:
                        payment.base_amount = converted
                        payment.save(update_fields=['base_amount', 'updated_at'])
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps({'applied': options['apply'], 'changes': changes, 'skipped': skipped}, ensure_ascii=False, indent=2))
        self.stdout.write(f'{len(changes)} corrections; {len(skipped)} skipped; report: {destination}')
