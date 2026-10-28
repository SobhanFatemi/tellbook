from rest_framework import serializers

from catalog.models import Book
from shipping.serializers import ShippingAddressSerializer
from .models import BookRequest, Order, Quote


class ApplyDiscountSerializer(serializers.Serializer):
    """Optional body for order-creation endpoints -- a blank/omitted code means no discount requested."""
    discount_code = serializers.CharField(required=False, allow_blank=True, default="")
    delivery_mode = serializers.ChoiceField(choices=["shelf", "ship_when_ready", "courier"], default="shelf")
    address_id = serializers.IntegerField(min_value=1, required=False)
    expected_shipping_fee = serializers.DecimalField(max_digits=12, decimal_places=0, min_value=0, required=False)
    address = ShippingAddressSerializer(required=False)
    collector_name = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["delivery_mode"] == "ship_when_ready" and (not (attrs.get("address_id") or attrs.get("address")) or "expected_shipping_fee" not in attrs):
            raise serializers.ValidationError("Choose an address and confirm the shipping fee.")
        if attrs["delivery_mode"] == "courier" and "expected_shipping_fee" not in attrs:
            raise serializers.ValidationError("هزینه صفر ارسال با پیک را تأیید کنید.")
        if attrs.get('address_id') and attrs.get('address'):
            raise serializers.ValidationError("یک آدرس انتخاب یا وارد کنید.")
        return attrs


class BookRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookRequest
        fields = ["id", "book", "title", "author", "description", "reference_image", "source", "status"]
        read_only_fields = ["id", "source", "status"]

    def validate(self, attrs):
        # A request needs at least one way to identify the book -- a bare
        # "author" with nothing else isn't enough to act on.
        if not (attrs.get("book") or attrs.get("title") or attrs.get("description") or attrs.get("reference_image")):
            raise serializers.ValidationError(
                "Provide at least a title, description, or reference photo."
            )
        return attrs

    def create(self, validated_data):
        validated_data["buyer"] = self.context["request"].user
        # source is derived, not client-supplied: linking an existing book
        # means it was found via search, anything else is a blind/unmatched entry.
        validated_data["source"] = (
            BookRequest.Source.DB_SEARCH if validated_data.get("book") else BookRequest.Source.BUYER_ENTERED
        )
        return super().create(validated_data)


class QuoteSerializer(serializers.ModelSerializer):
    total_price = serializers.ReadOnlyField()
    book_title = serializers.CharField(source="book.title", read_only=True, default="")

    class Meta:
        model = Quote
        fields = ["id", "book", "book_title", "book_cost", "service_fee", "shipping_fee", "estimated_days", "total_price", "is_auto_quoted", "accepted_at"]


class BookRequestSerializer(serializers.ModelSerializer):
    """Read serializer for listing -- includes the nested Quote (if any) so
    the buyer can see the price/timeline Dayana quoted and accept it.
    BookRequestCreateSerializer stays separate and write-only-ish since a
    buyer creating a request has no quote yet and shouldn't be able to set one."""
    quote = QuoteSerializer(read_only=True)
    buyer_phone = serializers.CharField(source="buyer.phone", read_only=True)

    class Meta:
        model = BookRequest
        fields = [
            "id", "book", "title", "author", "description", "reference_image",
            "source", "status", "failure_reason", "quote", "buyer_phone", "created_at",
        ]
        read_only_fields = fields


class SendQuoteSerializer(serializers.Serializer):
    book = serializers.PrimaryKeyRelatedField(queryset=Book.objects.all(), required=False, allow_null=True)
    book_cost = serializers.DecimalField(max_digits=12, decimal_places=0, min_value=0)
    service_fee = serializers.DecimalField(max_digits=12, decimal_places=0, default=0, min_value=0)
    shipping_fee = serializers.DecimalField(max_digits=12, decimal_places=0, default=0, min_value=0, max_value=0)
    estimated_days = serializers.IntegerField(min_value=0)


class OrderSerializer(serializers.ModelSerializer):
    cancellation = serializers.SerializerMethodField()

    def get_cancellation(self, obj):
        record = getattr(obj, "cancellation", None)
        return {"reason": record.reason, "created_at": record.created_at, "return_confirmed_at": record.return_confirmed_at} if record else None

    delivery = serializers.SerializerMethodField()

    def get_delivery(self, obj):
        payment = getattr(obj, 'payment', None)
        shipment = payment.shipment if payment and payment.shipment_id else None
        return {'mode': shipment.delivery_method if shipment else 'shelf',
                'shipping_fee': shipment.shipping_fee if shipment else 0,
                'recipient_name': shipment.recipient_name if shipment else ''}

    items = serializers.SerializerMethodField()

    def get_items(self, obj):
        purchase = getattr(obj, "merchandise", None)
        if not purchase:
            return []
        states = {r.index: r for r in purchase.fulfillment_units.select_related("stock_item")}
        return [{"index": i, "product_id": u.get("product_id"), "title": u["title"], "price": u["paid"], "contents": u["contents"],
                 "status": "failed" if states[i].failed else states[i].stock_item.status if states[i].stock_item_id else "awaiting_sourcing"}
                for i, u in enumerate(purchase.units)]

    quote = QuoteSerializer(read_only=True)
    payment = serializers.SerializerMethodField()
    buyer_phone = serializers.CharField(source="buyer.phone", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id", "items", "delivery", "quote", "status", "total_price", "discount_source", "cancellation",
            "discount_amount", "payment", "buyer_phone", "created_at", "failure_reason",
        ]

    def get_payment(self, obj):
        from payments.serializers import PaymentSummarySerializer

        payment = getattr(obj, "payment", None)
        return PaymentSummarySerializer(payment).data if payment else None


class MarkBookRequestFailedSerializer(serializers.Serializer):
    failure_reason = serializers.CharField()


class MarkOrderSourcedSerializer(serializers.Serializer):
    """Mark a sourced book ready; its ownership record is created for this buyer."""
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=0, required=False, min_value=0)

    def validate(self, attrs):
        if "stock_item_id" in self.initial_data:
            raise serializers.ValidationError("انتخاب از موجودی فروشگاه دیگر پشتیبانی نمی‌شود.")
        return attrs
