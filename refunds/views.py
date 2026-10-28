from django.utils import timezone
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from payments.models import Payment
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsCreator
from .models import Refund, RefundPolicy
from .serializers import MarkRefundProcessedSerializer, RefundPolicySerializer, RefundSerializer


@extend_schema(parameters=[OpenApiParameter("status", str, required=False, description="Filter by Refund.Status")])
class RefundListView(generics.ListAPIView):
    """Creator-only: list refunds, optionally filtered by ?status=pending|processed."""
    serializer_class = RefundSerializer
    permission_classes = [IsCreator]

    def get_queryset(self):
        qs = Refund.objects.select_related("order__buyer").order_by("-created_at")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class RefundDetailView(generics.RetrieveAPIView):
    serializer_class = RefundSerializer
    permission_classes = [IsCreator]
    queryset = Refund.objects.select_related("order__buyer")
    lookup_url_kwarg = "refund_id"


@extend_schema(request=MarkRefundProcessedSerializer)
class MarkRefundProcessedView(APIView):
    """
    Creator-only: she's sent the money back manually (same pattern as
    payment verification -- there's no processor integration to call).
    """
    permission_classes = [IsCreator]

    @transaction.atomic
    def post(self, request, refund_id):
        serializer = MarkRefundProcessedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reference = get_object_or_404(Refund, id=refund_id)
        # Serialize all refunds of this payment, not only this refund record.
        payment = Payment.objects.select_for_update().get(pk=reference.payment_id)
        refund = Refund.objects.select_for_update().get(pk=refund_id)
        if refund.status != Refund.Status.PENDING:
            return Response({"detail": "این بازگشت وجه قبلاً ثبت شده است."}, status=409)
        if payment.status != Payment.Status.VERIFIED:
            return Response({"detail": "پرداخت تأییدشده‌ای برای بازگشت وجه وجود ندارد."}, status=400)
        if refund.reason == Refund.Reason.RETURN and not getattr(getattr(refund.order, "cancellation", None), "return_confirmed_at", None):
            return Response({"detail": "دریافت اقلام مرجوعی هنوز تأیید نشده است."}, status=409)
        amount = serializer.validated_data.get("refund_amount", refund.refund_amount)
        already_refunded = payment.refunds.filter(status=Refund.Status.PROCESSED).aggregate(total=Sum("refund_amount"))["total"] or 0
        if amount > min(refund.original_amount, payment.base_amount - already_refunded):
            return Response({"detail": "مبلغ بازگشت از سهم این مورد یا مانده پرداخت بیشتر است."}, status=400)
        note = serializer.validated_data["note"].strip()
        if amount != refund.refund_amount and not note:
            return Response({"detail": "دلیل تغییر مبلغ بازگشت را بنویسید."}, status=400)
        refund.suggested_amount = refund.refund_amount
        refund.refund_amount = amount
        refund.deduction_amount = refund.original_amount - amount
        refund.processing_note = note
        refund.status = Refund.Status.PROCESSED
        refund.processed_by = request.user
        refund.processed_at = timezone.now()
        refund.save(update_fields=["suggested_amount", "refund_amount", "deduction_amount", "processing_note", "status", "processed_by", "processed_at", "updated_at"])
        return Response(RefundSerializer(refund).data)


class RefundPolicyListCreateView(generics.ListCreateAPIView):
    serializer_class = RefundPolicySerializer
    permission_classes = [IsCreator]
    queryset = RefundPolicy.objects.all()


class RefundPolicyDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RefundPolicySerializer
    permission_classes = [IsCreator]
    queryset = RefundPolicy.objects.all()
    lookup_url_kwarg = "policy_id"
