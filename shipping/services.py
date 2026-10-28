from django.shortcuts import get_object_or_404
from rest_framework.exceptions import APIException, ValidationError

from core.models import StoreSettings
from stock.models import StockItem
from .models import Shipment, ShippingAddress


class ShippingConflict(APIException):
    status_code = 409
    default_detail = 'Shipping details changed. Review them and try again.'


def count_unit_books(units):
    """Count physical books inside immutable purchased bundles, not accessories."""
    return sum(component['quantity'] for unit in units for component in unit.get('contents', []) if component.get('book_id'))


def count_shelf_books(items):
    return sum(1 if item.book_id else count_unit_books([item.merchandise_data]) for item in items)


def create_shipping_request(buyer, address_id, expected_fee, *, book_count=1, method='postal', address_data=None, collector_name=''):
    """Caller holds the buyer lock and an atomic transaction. Never trust client counts."""
    config = StoreSettings.objects.select_for_update().filter(pk=1).first() or StoreSettings(pk=1)
    fee = 0 if method == 'courier' else config.shipping_fee if book_count <= 6 else config.shipping_fee_over_six
    if fee is None or (method != 'courier' and fee <= 0):
        raise ValidationError({'detail': 'هزینه ارسال هنوز در تنظیمات ثبت نشده است.'})
    if fee != expected_fee:
        raise ShippingConflict('هزینه ارسال تغییر کرده است؛ مبلغ جدید را بررسی کنید.')
    if method == 'courier':
        if not buyer.full_name.strip():
            if not collector_name.strip():
                raise ValidationError({'detail': 'نام و نام خانوادگی خودتان را برای تحویل به پیک وارد کنید.'})
            buyer.full_name = collector_name.strip()
            buyer.save(update_fields=['full_name'])
        shipment = Shipment(buyer=buyer, recipient_name=buyer.full_name, recipient_phone=buyer.phone)
    else:
        if address_data:
            address = ShippingAddress.objects.create(user=buyer, **address_data)
        else:
            address = get_object_or_404(ShippingAddress, pk=address_id, user=buyer)
        shipment = Shipment.from_address(buyer, address)
    shipment.shipping_fee = fee
    shipment.delivery_method = method
    shipment.book_count = book_count
    shipment.save()
    return shipment


def cancel_shipment(shipment):
    shipment.status = Shipment.Status.CANCELLED
    shipment.save(update_fields=['status', 'updated_at'])
    StockItem.objects.filter(shipment=shipment).update(shipment=None)


def sync_shipment_readiness(shipment):
    payment = shipment.payment
    if shipment.status in [Shipment.Status.CANCELLED, Shipment.Status.SHIPPED, Shipment.Status.DELIVERED]:
        return
    if payment.status != 'verified':
        status = Shipment.Status.AWAITING_PAYMENT
    elif payment.order_id and payment.order.status != 'stock_ready':
        status = Shipment.Status.WAITING_BOOKS
    else:
        status = Shipment.Status.PREPARING
    shipment.status = status
    shipment.save(update_fields=['status', 'updated_at'])
