from rest_framework import serializers

from catalog.serializers import BookSerializer
from .models import StockItem


class StockItemSerializer(serializers.ModelSerializer):
    book = BookSerializer(read_only=True)
    title = serializers.ReadOnlyField()
    merchandise_data = serializers.SerializerMethodField()

    def get_merchandise_data(self, obj):
        return {key: obj.merchandise_data[key] for key in ('title', 'contents', 'paid') if key in obj.merchandise_data}


    class Meta:
        model = StockItem
        fields = ["id", "book", "title", "merchandise_data", "status", "expires_at", "shipment_id", "effective_price", "discount_reason"]
