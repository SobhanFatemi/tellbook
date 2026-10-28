from rest_framework import serializers

from .models import Payment


class PaymentProofUploadSerializer(serializers.ModelSerializer):
    proof_image = serializers.ImageField(required=True, allow_null=False)

    def validate_proof_image(self, value):
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Receipt image must be no larger than 5 MB.")
        return value

    class Meta:
        model = Payment
        fields = ["proof_image"]


class PaymentReviewSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(read_only=True, allow_null=True)
    proof_image = serializers.SerializerMethodField()

    def get_proof_image(self, obj):
        return f"/api/payments/{obj.pk}/receipt/" if obj.proof_image else None
    amount_expected = serializers.ReadOnlyField()

    class Meta:
        model = Payment
        fields = ["id", "order_id", "shipment_id", "amount_expected", "proof_image", "status", "uploaded_at"]


class PaymentSummarySerializer(serializers.ModelSerializer):
    """Buyer-facing view of their own payment -- nested into OrderSerializer
    so a buyer can tell "still need to upload a receipt" apart from
    "already uploaded, waiting on Dayana" apart from "rejected, try again"."""
    amount_expected = serializers.ReadOnlyField()
    has_proof = serializers.SerializerMethodField()
    proof_image = serializers.SerializerMethodField()

    def get_proof_image(self, obj):
        return f"/api/payments/{obj.pk}/receipt/" if obj.proof_image else None

    class Meta:
        model = Payment
        fields = ["id", "order_id", "shipment_id", "status", "amount_expected", "auto_cancel_at", "has_proof", "proof_image", "rejection_reason", "uploaded_at"]

    def get_has_proof(self, obj):
        return bool(obj.proof_image)


class VerifyPaymentActionSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")
