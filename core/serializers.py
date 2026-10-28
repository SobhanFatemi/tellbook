from rest_framework import serializers

from catalog.models import Book
from payments.models import Payment
from publisher_catalog.models import PublisherImportBatch
from requests_orders.models import BookRequest
from shipping.models import Shipment
from stock.models import StockItem


class NeedsQuoteSerializer(serializers.ModelSerializer):
    buyer_phone = serializers.CharField(source="buyer.phone", read_only=True)

    class Meta:
        model = BookRequest
        fields = ["id", "title", "author", "description", "buyer_phone", "created_at"]


class PendingPaymentSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(read_only=True, allow_null=True)
    buyer_phone = serializers.CharField(source="buyer.phone", read_only=True)
    amount_expected = serializers.ReadOnlyField()

    class Meta:
        model = Payment
        fields = ["id", "order_id", "shipment_id", "buyer_phone", "amount_expected", "uploaded_at"]


class ExpiringStockSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source="title", read_only=True)
    buyer_phone = serializers.CharField(source="buyer.phone", read_only=True)

    class Meta:
        model = StockItem
        fields = ["id", "book_title", "buyer_phone", "status", "expires_at"]


class ShipmentToSendSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = ["id", "recipient_name", "city", "status", "created_at"]


class NeedsReviewBookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ["id", "title", "category", "created_at"]


class ImportBatchSummarySerializer(serializers.ModelSerializer):
    publisher_name = serializers.CharField(source="publisher.name", read_only=True, default=None)

    class Meta:
        model = PublisherImportBatch
        fields = ["id", "publisher_name", "status", "total_rows", "processed_rows", "needs_review_rows"]
