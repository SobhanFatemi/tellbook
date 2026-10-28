from rest_framework import serializers

from .models import DiscountCode


class DiscountCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiscountCode
        fields = [
            "id", "code", "value", "min_order_value", "usage_limit", "per_user_limit",
            "valid_from", "valid_until", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ValidateDiscountCodeSerializer(serializers.Serializer):
    code = serializers.CharField()
    order_total = serializers.DecimalField(max_digits=12, decimal_places=0)
