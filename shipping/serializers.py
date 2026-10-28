from rest_framework import serializers

from accounts.serializers import iranian_mobile_validator
from payments.serializers import PaymentSummarySerializer
from stock.models import StockItem
from .models import ShippingAddress, Shipment


class ShippingAddressSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(validators=[iranian_mobile_validator])
    postal_code = serializers.RegexField(r'^[0-9]{10}$')

    class Meta:
        model = ShippingAddress
        fields = ['id', 'full_name', 'phone', 'province', 'city', 'address_line', 'postal_code', 'is_default']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ShipmentItemSerializer(serializers.ModelSerializer):
    title = serializers.ReadOnlyField()

    class Meta:
        model = StockItem
        fields = ['id', 'title']


class ShipmentSerializer(serializers.ModelSerializer):
    payment = PaymentSummarySerializer(read_only=True)
    items = ShipmentItemSerializer(source='stock_items_set', many=True, read_only=True)

    class Meta:
        model = Shipment
        fields = ['id', 'recipient_name', 'recipient_phone', 'province', 'city', 'address_line', 'postal_code',
                  'shipping_fee', 'delivery_method', 'book_count', 'tracking_code', 'status', 'payment', 'items', 'created_at', 'shipped_at', 'delivered_at']


class ShipShelfSerializer(serializers.Serializer):
    stock_item_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False, max_length=100)
    expected_shipping_fee = serializers.DecimalField(max_digits=12, decimal_places=0, min_value=0)
    delivery_method = serializers.ChoiceField(choices=["postal", "courier"], default="postal")
    address = ShippingAddressSerializer(required=False)
    collector_name = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate_stock_item_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError('Select each book only once.')
        return value


class MarkShippedSerializer(serializers.Serializer):
    tracking_code = serializers.CharField(max_length=100)
