from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListCreateAPIView, ListAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsCreator
from core.services import lock_buyer
from payments.models import Payment
from requests_orders.models import Order
from stock.models import StockEvent, StockItem
from .models import ShippingAddress, Shipment
from .services import cancel_shipment, create_shipping_request, count_shelf_books
from .serializers import MarkShippedSerializer, ShipmentSerializer, ShippingAddressSerializer, ShipShelfSerializer


class ShippingAddressListCreateView(ListCreateAPIView):
    serializer_class = ShippingAddressSerializer

    def get_queryset(self):
        return ShippingAddress.objects.filter(user=self.request.user).order_by('-is_default', '-pk')


class ShippingAddressDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = ShippingAddressSerializer

    def get_queryset(self):
        return ShippingAddress.objects.filter(user=self.request.user)


@extend_schema(request=ShipShelfSerializer)
class ShipMyShelfView(APIView):
    @transaction.atomic
    def post(self, request, address_id=None):
        serializer = ShipShelfSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        lock_buyer(request.user.pk)
        items = list(StockItem.objects.select_for_update(of=('self',)).filter(
            pk__in=data['stock_item_ids'], buyer=request.user, shipment__isnull=True,
            source_order__status__in=[Order.Status.PAID, Order.Status.SOURCING, Order.Status.STOCK_READY], source_order__payment__status=Payment.Status.VERIFIED,
            expires_at__gt=timezone.now(), status__in=[StockItem.Status.READY_TO_SHIP, StockItem.Status.ON_HOLD],
        ).order_by('pk'))
        if len(items) != len(data['stock_item_ids']):
            return Response({'detail': 'Some selected books are unavailable, unpaid, expired, or already assigned. Refresh your shelf.'}, status=409)
        shipment = create_shipping_request(request.user, address_id, data['expected_shipping_fee'],
            book_count=count_shelf_books(items), method=data['delivery_method'],
            address_data=data.get('address'), collector_name=data.get('collector_name', ''))
        StockItem.objects.filter(pk__in=[item.pk for item in items]).update(shipment=shipment)
        payment = Payment.objects.create(shipment=shipment, base_amount=shipment.shipping_fee, auto_cancel_at=timezone.now() + timedelta(hours=48))
        if shipment.delivery_method == 'courier':
            # No shipping money is due. Item payments were verified above.
            payment.status = Payment.Status.VERIFIED
            payment.auto_cancel_at = None
            payment.verified_at = timezone.now()
            payment.save(update_fields=['status', 'auto_cancel_at', 'verified_at'])
            shipment.status = Shipment.Status.PREPARING
            shipment.save(update_fields=['status'])
        return Response(ShipmentSerializer(shipment).data, status=201)


class MyShipmentsView(ListAPIView):
    serializer_class = ShipmentSerializer

    def get_queryset(self):
        return Shipment.objects.filter(buyer=self.request.user).select_related('payment').prefetch_related('stock_items_set__book').order_by('-created_at')


class ShipmentQueueView(ListAPIView):
    serializer_class = ShipmentSerializer
    permission_classes = [IsCreator]

    def get_queryset(self):
        return Shipment.objects.exclude(status__in=[Shipment.Status.CANCELLED, Shipment.Status.DELIVERED]).select_related('payment').prefetch_related('stock_items_set__book').order_by('created_at')


class CancelUnpaidShipmentView(APIView):
    @transaction.atomic
    def post(self, request, shipment_id):
        lock_buyer(request.user.pk)
        shipment = get_object_or_404(Shipment.objects.select_for_update(), pk=shipment_id, buyer=request.user)
        payment = getattr(shipment, 'payment', None)
        if (shipment.status != Shipment.Status.AWAITING_PAYMENT or not payment or payment.order_id or
                payment.status not in [Payment.Status.PENDING_PROOF, Payment.Status.REJECTED]):
            return Response({'detail': 'Only a separate unpaid shipping request without a pending receipt can be cancelled.'}, status=409)
        cancel_shipment(shipment)
        payment.auto_cancel_at = None
        payment.save(update_fields=['auto_cancel_at'])
        return Response({'detail': 'Shipping request cancelled. Your books remain on the shelf.'})


@extend_schema(request=MarkShippedSerializer)
class MarkShippedView(APIView):
    permission_classes = [IsCreator]

    @transaction.atomic
    def post(self, request, shipment_id):
        reference = get_object_or_404(Shipment, pk=shipment_id)
        lock_buyer(reference.buyer_id)
        shipment = Shipment.objects.select_for_update().get(pk=shipment_id)
        serializer = MarkShippedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = getattr(shipment, 'payment', None)
        if shipment.status != Shipment.Status.PREPARING or not payment or payment.status != Payment.Status.VERIFIED:
            return Response({'detail': 'Dispatch requires verified shipping payment and ready books.'}, status=409)
        items = list(StockItem.objects.select_for_update().filter(shipment=shipment).order_by('pk'))
        if not items or any(item.buyer_id != shipment.buyer_id or
                            item.status not in [StockItem.Status.READY_TO_SHIP, StockItem.Status.ON_HOLD] or
                            not item.source_order_id or item.source_order.status not in [Order.Status.PAID, Order.Status.SOURCING, Order.Status.STOCK_READY] or
                            item.source_order.payment.status != Payment.Status.VERIFIED for item in items):
            return Response({'detail': 'Every shipment item must have verified book payment and be ready.'}, status=409)
        shipment.tracking_code = serializer.validated_data['tracking_code']
        shipment.status = Shipment.Status.SHIPPED
        shipment.shipped_at = timezone.now()
        shipment.save()
        for item in items:
            item.status = StockItem.Status.SHIPPED
            item.save(update_fields=['status', 'updated_at'])
            StockEvent.objects.create(stock_item=item, event_type=StockEvent.EventType.SHIPPED)
        for order in Order.objects.filter(pk__in={item.source_order_id for item in items}).order_by('pk'):
            if hasattr(order, "merchandise"):
                from merchandise.services import settle_order
                settle_order(order)
            else:
                order.transition_to(Order.Status.SHIPPED)
        return Response(ShipmentSerializer(shipment).data)


class MarkDeliveredView(APIView):
    permission_classes = [IsCreator]

    @transaction.atomic
    def post(self, request, shipment_id):
        reference = get_object_or_404(Shipment, pk=shipment_id)
        lock_buyer(reference.buyer_id)
        shipment = Shipment.objects.select_for_update().get(pk=shipment_id)
        if shipment.status != Shipment.Status.SHIPPED:
            return Response({'detail': 'Only a shipped parcel can be marked delivered.'}, status=409)
        shipment.status = Shipment.Status.DELIVERED
        shipment.delivered_at = timezone.now()
        shipment.save()
        return Response(ShipmentSerializer(shipment).data)
