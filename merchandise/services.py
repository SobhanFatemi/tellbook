from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from core.services import lock_buyer
from publisher_catalog.models import Edition
from requests_orders.models import Quote, Order
from requests_orders.services import create_order
from stock.models import StockItem
from .models import Product, Purchase, FulfillmentUnit


def product_state(product):
    """Availability never implies that a sourced item is already on hand."""
    if not product.is_active or product.price <= 0:
        return False, False, 0
    if not product.is_bundle:
        return True, True, product.lead_days
    components = list(product.components.all())
    if not components:
        return False, False, 0
    days = 0
    for component in components:
        if component.product_id:
            child = component.product
            if child.is_bundle or not child.is_active:
                return False, False, 0
            days = max(days, child.lead_days)
        else:
            edition = component.edition
            if not edition.is_active:
                return False, False, 0
            days = max(days, edition.publisher.typical_lead_days)
    return True, True, days


def release_purchase(order):
    purchase = Purchase.objects.filter(order=order).first()
    if not purchase or purchase.released or purchase.fulfilled:
        return
    purchase.released = True
    purchase.save(update_fields=['released'])


def fulfill_purchase(order, indices=None, ready_only=False):
    purchase = order.merchandise
    pending = purchase.fulfillment_units.filter(stock_item=None, failed=False).order_by('index')
    if indices is not None:
        pending = pending.filter(index__in=indices)
    chosen = [record for record in pending if not ready_only or not purchase.units[record.index]['needs_sourcing']]
    if not chosen and not ready_only:
        raise ValidationError('اقلام انتخاب‌شده قبلاً آماده یا بسته شده‌اند.')
    for record in chosen:
        unit = purchase.units[record.index]
        item = StockItem.objects.create(unit_price=unit['paid'], merchandise_data=unit)
        item.claim_for_buyer(order.buyer, order)
        record.stock_item = item
        record.save(update_fields=['stock_item'])
    settle_order(order)
    if order.payment.shipment_id:
        from shipping.services import sync_shipment_readiness
        sync_shipment_readiness(order.payment.shipment)


def fail_pending_units(order, reason):
    from refunds.models import Refund
    from shipping.services import cancel_shipment, sync_shipment_readiness
    purchase = order.merchandise
    pending = list(purchase.fulfillment_units.filter(stock_item=None, failed=False))
    if not pending:
        raise ValidationError('قلمی در انتظار تهیه باقی نمانده است.')
    amount = 0
    for record in pending:
        unit = purchase.units[record.index]
        amount += unit['paid']
        record.failed = True
        record.save(update_fields=['failed'])
    # A prepaid parcel still carries ready items; refund its fee only when it has no items.
    if order.payment.shipment_id and not purchase.fulfillment_units.filter(stock_item__isnull=False).exists():
        amount += order.payment.shipment.shipping_fee
        cancel_shipment(order.payment.shipment)
    Refund.objects.create(order=order, payment=order.payment, reason=Refund.Reason.SOURCING_FAILED,
                          original_amount=amount, deduction_amount=0, refund_amount=amount)
    order.failure_reason = reason
    order.save(update_fields=['failure_reason'])
    settle_order(order)
    if order.payment.shipment_id:
        sync_shipment_readiness(order.payment.shipment)


@transaction.atomic
def checkout(buyer, data):
    lock_buyer(buyer.pk)
    previous = Purchase.objects.filter(buyer=buyer, key=data['key']).first()
    if previous:
        return previous.order
    # Lock the catalog in deterministic order so staff cannot disable a component
    # between availability validation and purchase creation.
    products = {p.pk: p for p in Product.objects.select_for_update().order_by('pk')}
    edition_ids = set()
    for line in data['lines']:
        if line.get('edition_id'):
            edition_ids.add(line['edition_id'])
        elif line.get('product_id') in products:
            edition_ids.update(products[line['product_id']].components.exclude(edition=None).values_list('edition_id', flat=True))
    editions = {e.pk: e for e in Edition.objects.select_for_update().filter(pk__in=edition_ids).order_by('pk')}
    units, total, days = [], 0, 0
    for line in data['lines']:
        contents = []
        if line.get('edition_id'):
            edition = editions.get(line['edition_id'])
            if not edition or not edition.is_active:
                raise ValidationError('نسخه انتخاب‌شده دیگر قابل سفارش نیست.')
            price = int(edition.book.apply_discount(edition.price))
            title = f'{edition.book.title} — {edition.publisher.name}'
            days = max(days, edition.publisher.typical_lead_days)
            product_id = None
            contents.append({'title': title, 'quantity': 1, 'edition_id': edition.pk, 'book_id': edition.book_id, 'price': int(edition.price)})
        else:
            product = products.get(line['product_id'])
            if not product or not product.is_active or not product.sold_separately or product.price <= 0:
                raise ValidationError('یکی از محصولات دیگر قابل خرید نیست؛ سبد را بازبینی کنید.')
            title, price, product_id = product.title, product.price, product.pk
            components = list(product.components.all()) if product.is_bundle else []
            if product.is_bundle and not components:
                raise ValidationError('محتویات پک هنوز ثبت نشده است.')
            entries = [(c.product_id, c.edition_id, c.quantity) for c in components] if product.is_bundle else [(product.pk, None, 1)]
            for pid, eid, count in entries:
                if pid:
                    child = products.get(pid)
                    if not child or child.is_bundle or not child.is_active:
                        raise ValidationError('یکی از اقلام پک موجود نیست.')
                    days = max(days, child.lead_days)
                    contents.append({'title': child.title, 'quantity': count, 'product_id': pid, 'price': child.price})
                else:
                    edition = editions.get(eid)
                    if not edition or not edition.is_active:
                        raise ValidationError('یکی از کتاب‌های پک دیگر قابل تهیه نیست.')
                    days = max(days, edition.publisher.typical_lead_days)
                    contents.append({'title': f'{edition.book.title} — {edition.publisher.name}', 'quantity': count, 'edition_id': eid, 'book_id': edition.book_id, 'price': int(edition.price)})
        if price <= 0 or price != line['expected_price']:
            raise ValidationError('قیمت تغییر کرده است؛ قیمت جدید را در سبد بررسی کنید.')
        for _ in range(line['quantity']):
            units.append({'title': title, 'price': price, 'product_id': product_id, 'contents': contents, 'allocations': {}, 'needs_sourcing': True})
            total += price
    if total > 999999999999:
        raise ValidationError('مبلغ سبد بیش از حد مجاز است.')
    quote = Quote.objects.create(book_cost=total, estimated_days=days, is_auto_quoted=True)
    from shipping.services import count_unit_books
    order = create_order(quote, buyer, data.get('discount_code', ''), delivery=data, book_count=count_unit_books(units))
    # Allocate the actual paid amount exactly, including a possible discount.
    remaining = int(order.total_price)
    for index, unit in enumerate(units):
        unit['paid'] = remaining if index == len(units)-1 else int(Decimal(unit['price']) * order.total_price / total)
        remaining -= unit['paid']
    purchase = Purchase.objects.create(order=order, buyer=buyer, key=data['key'], units=units, requires_sourcing=any(u['needs_sourcing'] for u in units))
    FulfillmentUnit.objects.bulk_create([FulfillmentUnit(purchase=purchase, index=i) for i in range(len(units))])
    from notifications.services import NotificationService
    transaction.on_commit(lambda: NotificationService.notify_creator_new_order(order))
    return order


def expire_merchandise_item(item, order):
    """Refund only this shelf unit, never its already-shipped siblings."""
    from refunds.models import Refund, RefundPolicy
    from stock.models import StockEvent
    policy = RefundPolicy.objects.filter(reason=Refund.Reason.EXPIRED).first()
    original = Decimal(item.merchandise_data['paid'])
    deduction = min(original, (original * (policy.deduction_percentage if policy else 0) / 100).quantize(Decimal('1')))
    Refund.objects.create(order=order, payment=order.payment, reason=Refund.Reason.EXPIRED,
                          original_amount=original, deduction_amount=deduction, refund_amount=original-deduction)
    StockEvent.objects.create(stock_item=item, event_type=StockEvent.EventType.REFUNDED)
    item.status = StockItem.Status.AVAILABLE
    item.buyer = None
    item.expires_at = None
    item.save(update_fields=['status', 'buyer', 'expires_at'])
    settle_order(order)


def settle_order(order):
    purchase = order.merchandise
    complete = not purchase.fulfillment_units.filter(stock_item=None, failed=False).exists()
    purchase.fulfilled = complete
    purchase.save(update_fields=['fulfilled'])
    if not complete:
        return
    units = order.stock_items.all()
    if units.filter(status__in=['ready_to_ship', 'on_hold']).exists():
        if order.status in [Order.Status.PAID, Order.Status.SOURCING]:
            order.transition_to(Order.Status.STOCK_READY)
        return
    if order.status in [Order.Status.PAID, Order.Status.SOURCING] and units.filter(status='shipped').exists():
        order.transition_to(Order.Status.STOCK_READY)
    if order.status == Order.Status.STOCK_READY:
        order.transition_to(Order.Status.SHIPPED if units.filter(status='shipped').exists() else Order.Status.REFUNDED)
    elif order.status in [Order.Status.PAID, Order.Status.SOURCING]:
        if order.status == Order.Status.PAID:
            order.transition_to(Order.Status.SOURCING)
        order.transition_to(Order.Status.FAILED)
        order.transition_to(Order.Status.REFUNDED)
