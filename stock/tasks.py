"""Expire paid shelf storage atomically, without touching assigned shipments."""
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from requests_orders.models import Order
from core.services import lock_buyer
from shipping.services import cancel_shipment
from .models import StockEvent, StockItem


@shared_task
def expire_stock_items():
    from refunds.models import Refund

    candidates = list(StockItem.objects.filter(
        status__in=[StockItem.Status.READY_TO_SHIP, StockItem.Status.ON_HOLD],
        expires_at__lte=timezone.now(),
    ).values_list('pk', 'source_order_id', 'buyer_id'))
    expired = refunded = 0
    for item_id, order_id, buyer_id in candidates:
        with transaction.atomic():
            if buyer_id:
                lock_buyer(buyer_id)
            order = Order.objects.select_for_update().filter(pk=order_id).first() if order_id else None
            item = StockItem.objects.select_for_update().get(pk=item_id)
            if (item.source_order_id != order_id or not item.expires_at or
                    item.expires_at > timezone.now() or
                    item.status not in [StockItem.Status.READY_TO_SHIP, StockItem.Status.ON_HOLD]):
                continue
            if item.shipment_id:
                shipping_payment = getattr(item.shipment, 'payment', None)
                if shipping_payment and shipping_payment.status in ['pending_verification', 'verified']:
                    continue
                cancel_shipment(item.shipment)
                if shipping_payment:
                    shipping_payment.auto_cancel_at = None
                    shipping_payment.status = 'rejected'
                    shipping_payment.rejection_reason = 'A selected book reached its storage deadline.'
                    shipping_payment.save()
                item.shipment_id = None
            if item.merchandise_data and order and order.payment.status == 'verified':
                from merchandise.services import expire_merchandise_item
                expire_merchandise_item(item, order)
                expired += 1
                refunded += 1
                continue
            if order and order.status == Order.Status.STOCK_READY and order.payment.status == 'verified':
                Refund.build_for_order(order, Refund.Reason.EXPIRED).save()
                order.transition_to(Order.Status.REFUNDED)
                StockEvent.objects.create(stock_item=item, event_type=StockEvent.EventType.REFUNDED)
                refunded += 1
            item.release_expired()
            expired += 1
    return {'expired': expired, 'refunded': refunded}
