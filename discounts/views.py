from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsCreator
from .models import DiscountCode
from .serializers import DiscountCodeSerializer, ValidateDiscountCodeSerializer
from .services import DiscountCodeError, validate_discount_code


class DiscountCodeListCreateView(generics.ListCreateAPIView):
    """Creator-only: list and create discount codes."""
    serializer_class = DiscountCodeSerializer
    permission_classes = [IsCreator]
    queryset = DiscountCode.objects.all().order_by("-created_at")


class DiscountCodeDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Creator-only: view/update/delete a single discount code."""
    serializer_class = DiscountCodeSerializer
    permission_classes = [IsCreator]
    queryset = DiscountCode.objects.all()
    lookup_url_kwarg = "code_id"

    def destroy(self, request, *args, **kwargs):
        # Order.discount_code is SET_NULL, and usage_limit/per_user_limit are
        # counted from orders -- deleting a used code would erase its usage
        # history, letting someone recreate the same code with fresh limits.
        # Used codes get deactivated instead (is_active=False), never deleted.
        code = self.get_object()
        if code.orders.exists():
            return Response(
                {"detail": "This code has been used on orders and can't be deleted. Deactivate it instead."},
                status=409,
            )
        return super().destroy(request, *args, **kwargs)


@extend_schema(request=ValidateDiscountCodeSerializer)
class ValidateDiscountCodeView(APIView):
    """
    Buyer-facing: check a code against an order total before/during
    checkout, without actually placing an order. Mirrors exactly the same
    validation that AcceptQuoteView/BuyInStockView/BuyEditionView apply
    when the order is actually created, so a code that validates here will
    also apply there (barring a race on usage_limit).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ValidateDiscountCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            code, discount_amount = validate_discount_code(
                serializer.validated_data["code"],
                serializer.validated_data["order_total"],
                request.user,
            )
        except DiscountCodeError as exc:
            return Response({"valid": False, "detail": str(exc)}, status=400)

        return Response({
            "valid": True,
            "code": code.code,
            "discount_amount": discount_amount,
            "final_total": serializer.validated_data["order_total"] - discount_amount,
        })
