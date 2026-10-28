"""Whole-order cancellation, serialized with receipt review and dispatch."""
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView
from core.permissions import IsCreator
from core.services import lock_buyer
from payments.models import Payment
from refunds.models import Refund
from shipping.models import Shipment
from shipping.services import cancel_shipment
from stock.models import StockItem, StockEvent
from .models import Order, OrderCancellation, BookRequest


class CancellationConflict(APIException):
    status_code = 409


class CancelOrderSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000)
    return_confirmed = serializers.BooleanField(default=False)


def cancellation_plan(order_id):
    """Caller is atomic. Lock order matches payment/dispatch: buyer first."""
    reference = get_object_or_404(Order, pk=order_id)
    lock_buyer(reference.buyer_id)
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status in [Order.Status.CANCELLED, Order.Status.REFUNDED, Order.Status.FAILED]:
        raise CancellationConflict('این سفارش قبلاً بسته شده است؛ بازگشت وجه را از بخش بازگشت وجه پیگیری کنید.')
    items = list(order.stock_items.filter(buyer_id=order.buyer_id).order_by('pk'))
    payment_reference = get_object_or_404(Payment, order=order)
    shipment_ids = {item.shipment_id for item in items if item.shipment_id}
    if payment_reference.shipment_id:
        shipment_ids.add(payment_reference.shipment_id)
    shipments = list(Shipment.objects.select_for_update().filter(pk__in=shipment_ids).order_by('pk'))
    payments = list(Payment.objects.select_for_update().filter(buyer_query(order, shipment_ids)).order_by('pk'))
    payment = next(p for p in payments if p.order_id == order.pk)
    requires_return = order.status == Order.Status.SHIPPED or any(item.status == StockItem.Status.SHIPPED for item in items)
    cancelled_shipments = []
    for shipment in shipments:
        if shipment.status in [Shipment.Status.SHIPPED, Shipment.Status.DELIVERED, Shipment.Status.CANCELLED]:
            continue
        if not shipment.stock_items_set.exclude(source_order=order).exists():
            cancelled_shipments.append(shipment)
    closing_ids = {s.pk for s in cancelled_shipments}
    relevant = [p for p in payments if p.order_id == order.pk or p.shipment_id in closing_ids]
    if any(p.status == Payment.Status.PENDING_VERIFICATION for p in relevant):
        raise CancellationConflict('ابتدا رسید در انتظار بررسی را تأیید یا رد کنید تا مبلغ واقعی بازگشت مشخص شود.')
    obligations = []
    for p in relevant:
        if p.status != Payment.Status.VERIFIED:
            continue
        # Existing obligations reserve their original share, including retained
        # deductions: cancellation must never refund that share a second time.
        allocated = p.refunds.aggregate(total=Sum('original_amount'))['total'] or Decimal(0)
        retained_shipping = Decimal(0)
        if p.order_id and p.shipment_id and p.shipment_id not in closing_ids and p.shipment.status != Shipment.Status.CANCELLED:
            retained_shipping = p.shipment.shipping_fee or Decimal(0)
        amount = max(Decimal(0), p.base_amount - retained_shipping - allocated)
        if amount:
            obligations.append((p, amount))
    return order, items, relevant, cancelled_shipments, obligations, requires_return


def buyer_query(order, shipment_ids):
    from django.db.models import Q
    return Q(order=order) | Q(shipment_id__in=shipment_ids, order__isnull=True)


class CancelOrderView(APIView):
    permission_classes = [IsCreator]

    @transaction.atomic
    def get(self, request, order_id):
        order, items, payments, shipments, obligations, requires_return = cancellation_plan(order_id)
        return Response({'requires_return': requires_return, 'refund_amount': sum((amount for _, amount in obligations), Decimal(0)),
                         'refunds': [{'payment_id': p.pk, 'amount': amount, 'shipping_only': p.order_id is None} for p, amount in obligations],
                         'cancelled_shipments': [s.pk for s in shipments]})

    @transaction.atomic
    def post(self, request, order_id):
        serializer = CancelOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order, items, payments, shipments, obligations, requires_return = cancellation_plan(order_id)
        data = serializer.validated_data
        if requires_return and not data['return_confirmed']:
            raise CancellationConflict('پیش از لغو و بازگشت وجه، دریافت تمام اقلام ارسال‌شده این سفارش را تأیید کنید.')
        decision = OrderCancellation.objects.create(order=order, reason=data['reason'], created_by=request.user,
            previous_status=order.status, return_confirmed_at=timezone.now() if requires_return else None)
        for payment, amount in obligations:
            Refund.objects.create(order=order, payment=payment, reason=Refund.Reason.RETURN if requires_return else Refund.Reason.CANCELLATION,
                                  original_amount=amount, refund_amount=amount)
        for shipment in shipments:
            cancel_shipment(shipment)
        for item in items:
            was_shipped = item.status == StockItem.Status.SHIPPED
            # Keep source_order and shipped parcel links for history. These
            # ownership records are never exposed as sellable inventory.
            item.buyer = None
            item.expires_at = None
            item.reserved_at = None
            item.status = StockItem.Status.AVAILABLE
            if not was_shipped:
                item.shipment = None
            item.save(update_fields=['buyer', 'expires_at', 'reserved_at', 'status', 'shipment', 'updated_at'])
            StockEvent.objects.create(stock_item=item, event_type=StockEvent.EventType.REFUNDED, note=f'Cancellation {decision.pk}')
        purchase = getattr(order, 'merchandise', None)
        if purchase:
            purchase.fulfillment_units.filter(stock_item=None, failed=False).update(failed=True)
            purchase.released = True
            purchase.save(update_fields=['released'])
        for payment in payments:
            payment.auto_cancel_at = None
            if payment.status != Payment.Status.VERIFIED:
                payment.status = Payment.Status.REJECTED
                payment.rejection_reason = data['reason']
            payment.save(update_fields=['auto_cancel_at', 'status', 'rejection_reason', 'updated_at'])
        order.status = Order.Status.CANCELLED
        order.save(update_fields=['status', 'updated_at'])
        if order.quote.request_id:
            BookRequest.objects.filter(pk=order.quote.request_id).update(status=BookRequest.Status.FAILED, failure_reason=data['reason'], updated_at=timezone.now())
        from notifications.services import NotificationService
        transaction.on_commit(lambda: NotificationService.notify_creator_order_update(order))
        from .serializers import OrderSerializer
        return Response(OrderSerializer(order).data)
