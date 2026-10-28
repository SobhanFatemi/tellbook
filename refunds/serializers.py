from rest_framework import serializers

from .models import Refund, RefundPolicy


class RefundSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source="order.id", read_only=True)
    buyer_phone = serializers.CharField(source="order.buyer.phone", read_only=True)

    class Meta:
        model = Refund
        fields = [
            "id", "order_id", "buyer_phone", "payment", "reason", "original_amount",
            "deduction_amount", "refund_amount", "status", "processed_by", "processed_at",
            "created_at", "processing_note", "suggested_amount",
        ]
        read_only_fields = fields


class MarkRefundProcessedSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)
    refund_amount = serializers.DecimalField(max_digits=12, decimal_places=0, min_value=0, required=False)


class RefundPolicySerializer(serializers.ModelSerializer):
    deduction_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)

    class Meta:
        model = RefundPolicy
        fields = ["id", "reason", "deduction_percentage", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
