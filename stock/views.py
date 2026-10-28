from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import StockItem
from .serializers import StockItemSerializer


class MyShelfView(ListAPIView):
    """Everything a buyer currently has claimed — on hold or ready to ship."""
    serializer_class = StockItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return StockItem.objects.filter(
            buyer=self.request.user,
            source_order__status__in=["paid", "sourcing", "stock_ready"],
            source_order__payment__status="verified",
            status__in=[StockItem.Status.ON_HOLD, StockItem.Status.READY_TO_SHIP],
        )


class HoldStockItemView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, stock_item_id):
        return Response({"detail": "Hold markers have been replaced by selecting books when requesting shipment."}, status=410)
