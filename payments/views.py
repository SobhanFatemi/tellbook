import hashlib
from datetime import timedelta
from pathlib import Path

from django.db import transaction
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsCreator
from notifications.services import NotificationService
from requests_orders.models import Order
from stock.models import StockItem
from shipping.services import sync_shipment_readiness
from .models import Payment
from .services import accepts_receipt, lock_payment
from .serializers import PaymentProofUploadSerializer, PaymentReviewSerializer, VerifyPaymentActionSerializer


def owned_payments(user):
    return Payment.objects.filter(Q(order__buyer=user) | Q(shipment__buyer=user))


@transaction.atomic
def upload_receipt(request, payment_id):
    get_object_or_404(owned_payments(request.user), pk=payment_id)
    payment = lock_payment(payment_id)
    if not accepts_receipt(payment):
        return Response({'detail': 'This payment is not accepting a receipt.'}, status=409)
    if payment.auto_cancel_at and payment.auto_cancel_at <= timezone.now():
        return Response({'detail': 'The payment window has expired. Start a new order or shipment.'}, status=409)
    serializer = PaymentProofUploadSerializer(payment, data=request.data)
    serializer.is_valid(raise_exception=True)
    image = serializer.validated_data['proof_image']
    digest = hashlib.sha256(image.read()).hexdigest()
    image.seek(0)
    proof = serializer.save()
    proof.proof_image_hash = digest
    proof.uploaded_at = timezone.now()
    proof.status = Payment.Status.PENDING_VERIFICATION
    proof.auto_cancel_at = None
    proof.rejection_reason = ''
    proof.save()
    transaction.on_commit(lambda: NotificationService.notify_creator_payment_uploaded(proof))
    return Response({'detail': 'Receipt uploaded, awaiting verification.'})


@extend_schema(request={'multipart/form-data': PaymentProofUploadSerializer})
class UploadPaymentProofView(APIView):
    """Keep the existing order-based upload URL compatible."""
    def post(self, request, order_id):
        payment = get_object_or_404(owned_payments(request.user), order_id=order_id)
        return upload_receipt(request, payment.pk)


@extend_schema(request={'multipart/form-data': PaymentProofUploadSerializer})
class UploadPaymentByIdView(APIView):
    def post(self, request, payment_id):
        return upload_receipt(request, payment_id)


class PaymentVerificationQueueView(ListAPIView):
    serializer_class = PaymentReviewSerializer
    permission_classes = [IsCreator]
    queryset = Payment.objects.filter(status=Payment.Status.PENDING_VERIFICATION).select_related('order__buyer', 'shipment__buyer')


@extend_schema(request=VerifyPaymentActionSerializer)
class VerifyPaymentView(APIView):
    permission_classes = [IsCreator]

    @transaction.atomic
    def post(self, request, payment_id):
        payment = lock_payment(payment_id)
        serializer = VerifyPaymentActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from shipping.models import Shipment
        if (payment.status != Payment.Status.PENDING_VERIFICATION or
            (payment.order_id and payment.order.status != Order.Status.AWAITING_PAYMENT) or
            (payment.shipment_id and payment.shipment.status != Shipment.Status.AWAITING_PAYMENT)):
            return Response({'detail': 'This receipt has already been reviewed or its purchase is closed.'}, status=409)
        if serializer.validated_data['approve']:
            if not payment.proof_image:
                return Response({'detail': 'A receipt is required before approval.'}, status=400)
            payment.status = Payment.Status.VERIFIED
            payment.verified_by = request.user
            payment.verified_at = timezone.now()
            payment.auto_cancel_at = None
            payment.rejection_reason = ''
            payment.save()
            if payment.order_id:
                order = payment.order
                order.transition_to(Order.Status.PAID)
                items = list(StockItem.objects.select_for_update().filter(source_order=order, status=StockItem.Status.RESERVED))
                for item in items:
                    item.claim_for_buyer(order.buyer, order)
                if hasattr(order, "merchandise"):
                    from merchandise.services import fulfill_purchase
                    fulfill_purchase(order, ready_only=True)
                elif items:
                    order.transition_to(Order.Status.STOCK_READY)
            if payment.shipment_id:
                sync_shipment_readiness(payment.shipment)
        else:
            reason = serializer.validated_data.get('reason', '').strip()
            if not reason:
                return Response({'detail': 'Explain why the receipt was rejected.'}, status=400)
            payment.status = Payment.Status.REJECTED
            payment.rejection_reason = reason
            reserved_copy = payment.order_id and (StockItem.objects.filter(source_order_id=payment.order_id, status=StockItem.Status.RESERVED).exists() or (hasattr(payment.order, "merchandise") and any(u["allocations"] for u in payment.order.merchandise.units)))
            payment.auto_cancel_at = timezone.now() + (timedelta(minutes=30) if reserved_copy else timedelta(hours=48))
            payment.save()
        return Response({'detail': 'Payment reviewed.'})


class PaymentReceiptView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, payment_id):
        payments = Payment.objects.all() if request.user.role == request.user.Role.CREATOR else owned_payments(request.user)
        payment = get_object_or_404(payments, pk=payment_id)
        if not payment.proof_image:
            return Response({'detail': 'No receipt uploaded.'}, status=404)
        try:
            response = FileResponse(payment.proof_image.open('rb'), as_attachment=True, filename='payment-receipt' + Path(payment.proof_image.name).suffix)
        except FileNotFoundError:
            return Response({'detail': 'Receipt file is unavailable.'}, status=404)
        response['Cache-Control'] = 'private, no-store'
        return response
