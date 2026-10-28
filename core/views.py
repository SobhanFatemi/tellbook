from datetime import timedelta

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Book
from payments.models import Payment
from publisher_catalog.models import PublisherImportBatch
from publisher_catalog.price_review import flagged, configured_threshold
from requests_orders.models import BookRequest, Order
from shipping.models import Shipment
from stock.models import StockItem
from .permissions import IsCreator
from .serializers import (
    ExpiringStockSerializer,
    ImportBatchSummarySerializer,
    NeedsQuoteSerializer,
    NeedsReviewBookSerializer,
    PendingPaymentSerializer,
    ShipmentToSendSerializer,
)

EXPIRING_SOON_DAYS = 5  # flag holds expiring within this many days


class AdminDashboardView(APIView):
    """
    The single 'needs your attention' view for Dayana -- every queue that
    needs a human decision, in one place, instead of digging through each
    endpoint separately. Read-only summary; acting on any item still goes
    through its own existing endpoint (send-quote, verify-payment, etc).
    """
    permission_classes = [IsCreator]

    def get(self, request):
        needs_quote = BookRequest.objects.filter(status=BookRequest.Status.PENDING, quote__isnull=True)
        pending_payments = Payment.objects.filter(status=Payment.Status.PENDING_VERIFICATION)

        expiring_cutoff = timezone.now() + timedelta(days=EXPIRING_SOON_DAYS)
        expiring_stock = StockItem.objects.filter(
            status__in=[StockItem.Status.READY_TO_SHIP, StockItem.Status.ON_HOLD],
            expires_at__lte=expiring_cutoff,
            expires_at__gte=timezone.now(),
        )

        shipments_to_send = Shipment.objects.filter(status=Shipment.Status.PREPARING)
        needs_review_books = Book.objects.filter(needs_review=True)
        active_import_batches = PublisherImportBatch.objects.filter(
            status__in=[PublisherImportBatch.Status.PENDING, PublisherImportBatch.Status.PROCESSING, PublisherImportBatch.Status.REVIEW, PublisherImportBatch.Status.APPLYING]
        )

        return Response({
            "price_review_threshold": str(configured_threshold()),
            "order_counts": {status: Order.objects.filter(status=status).count() for status, _ in Order.Status.choices},
            "counts": {
                "price_review": flagged(configured_threshold()).filter(is_active=True).count(),
                "needs_quote": needs_quote.count(),
                "pending_payments": pending_payments.count(),
                "expiring_soon": expiring_stock.count(),
                "shipments_to_send": shipments_to_send.count(),
                "needs_review_books": needs_review_books.count(),
                "import_batches_active": active_import_batches.count(),
            },
            "needs_quote": NeedsQuoteSerializer(needs_quote[:20], many=True).data,
            "pending_payments": PendingPaymentSerializer(pending_payments[:20], many=True).data,
            "expiring_soon": ExpiringStockSerializer(expiring_stock[:20], many=True).data,
            "shipments_to_send": ShipmentToSendSerializer(shipments_to_send[:20], many=True).data,
            "needs_review_books": NeedsReviewBookSerializer(needs_review_books[:20], many=True).data,
            "import_batches_active": ImportBatchSummarySerializer(active_import_batches[:20], many=True).data,
        })
