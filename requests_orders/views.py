from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsCreator
from core.services import lock_buyer
from notifications.services import NotificationService
from payments.models import Payment
from publisher_catalog.models import Edition
from stock.models import StockItem
from .models import BookRequest, Order, Quote
from .services import create_order, refund_failed_sourcing
from .serializers import (
    ApplyDiscountSerializer, BookRequestCreateSerializer, BookRequestSerializer,
    MarkBookRequestFailedSerializer, MarkOrderSourcedSerializer, OrderSerializer, SendQuoteSerializer,
)


class BookRequestCreateView(CreateAPIView):
    serializer_class = BookRequestCreateSerializer
    permission_classes = [IsAuthenticated]


@extend_schema(parameters=[OpenApiParameter("status", str, required=False)])
class AdminRequestListView(ListAPIView):
    serializer_class = BookRequestSerializer
    permission_classes = [IsCreator]

    def get_queryset(self):
        qs = BookRequest.objects.select_related("quote", "buyer").order_by("-created_at")
        status = self.request.query_params.get("status")
        return qs.filter(status=status) if status else qs


class MyRequestsView(ListAPIView):
    serializer_class = BookRequestSerializer

    def get_queryset(self):
        return BookRequest.objects.select_related("quote", "buyer").filter(buyer=self.request.user).order_by("-created_at")


@extend_schema(request=SendQuoteSerializer)
class SendQuoteView(APIView):
    permission_classes = [IsCreator]

    @transaction.atomic
    def post(self, request, request_id):
        reference = get_object_or_404(BookRequest, pk=request_id)
        lock_buyer(reference.buyer_id)
        book_request = BookRequest.objects.select_for_update().get(pk=request_id)
        if book_request.status != BookRequest.Status.PENDING or Quote.objects.filter(request=book_request).exists():
            return Response({"detail": "This request has already been quoted or closed."}, status=409)
        serializer = SendQuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        book = data.pop("book", None) or book_request.book
        quote = Quote.objects.create(request=book_request, book=book, quoted_by=request.user, **data)
        transaction.on_commit(lambda: NotificationService.notify_buyer_quote_sent(book_request.buyer, book_request, quote))
        return Response({"detail": "Quote sent.", "quote_id": quote.id})


@extend_schema(request=ApplyDiscountSerializer)
class AcceptQuoteView(APIView):
    @transaction.atomic
    def post(self, request, quote_id):
        lock_buyer(request.user.pk)
        quote = get_object_or_404(Quote.objects.select_for_update(), pk=quote_id, request__buyer=request.user)
        if quote.accepted_at or quote.request.status != BookRequest.Status.PENDING:
            return Response({"detail": "This quote is already accepted or unavailable."}, status=409)
        serializer = ApplyDiscountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = create_order(quote, request.user, serializer.validated_data["discount_code"], delivery=serializer.validated_data)
        quote.accepted_at = timezone.now()
        quote.save(update_fields=["accepted_at", "updated_at"])
        transaction.on_commit(lambda: NotificationService.notify_creator_new_order(order))
        return Response(OrderSerializer(order).data, status=201)


@extend_schema(parameters=[OpenApiParameter("status", str, required=False)])
class AdminOrderListView(ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsCreator]

    def get_queryset(self):
        qs = Order.objects.select_related("quote__book", "payment__shipment", "buyer", "cancellation").order_by("-created_at")
        status = self.request.query_params.get("status")
        return qs.filter(status=status) if status else qs


class MyOrdersView(ListAPIView):
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.select_related("quote__book", "payment__shipment", "buyer", "cancellation").filter(buyer=self.request.user).order_by("-created_at")


@extend_schema(request=ApplyDiscountSerializer)
class BuyInStockView(APIView):
    @transaction.atomic
    def post(self, request, book_id):
        return Response({"detail": "خرید از موجودی فروشگاه حذف شده است؛ نسخه ناشر را به سبد اضافه کنید."}, status=410)


@extend_schema(request=ApplyDiscountSerializer)
class BuyEditionView(APIView):
    @transaction.atomic
    def post(self, request, edition_id):
        serializer = ApplyDiscountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lock_buyer(request.user.pk)
        edition = Edition.objects.select_for_update().filter(pk=edition_id, is_active=True).first()
        if not edition:
            return Response({"detail": "No longer available from this publisher."}, status=409)
        quote = Quote.objects.create(
            book=edition.book, book_cost=edition.book.apply_discount(edition.price),
            estimated_days=edition.publisher.typical_lead_days, is_auto_quoted=True, source_listing=edition,
        )
        order = create_order(quote, request.user, serializer.validated_data["discount_code"], delivery=serializer.validated_data)
        transaction.on_commit(lambda: NotificationService.notify_creator_new_order(order))
        return Response(OrderSerializer(order).data, status=201)


@extend_schema(request=MarkBookRequestFailedSerializer)
class MarkBookRequestFailedView(APIView):
    permission_classes = [IsCreator]

    @transaction.atomic
    def post(self, request, request_id):
        reference = get_object_or_404(BookRequest, pk=request_id)
        lock_buyer(reference.buyer_id)
        book_request = BookRequest.objects.select_for_update().get(pk=request_id)
        serializer = MarkBookRequestFailedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if book_request.status in [BookRequest.Status.FAILED, BookRequest.Status.READY]:
            return Response({"detail": "This request is already closed."}, status=409)
        order = Order.objects.select_for_update().filter(quote__request=book_request).first()
        if order and order.status not in [Order.Status.PAID, Order.Status.SOURCING, Order.Status.AWAITING_PAYMENT, Order.Status.CANCELLED]:
            return Response({"detail": "The linked order can no longer fail sourcing."}, status=409)
        refunded = False
        if order:
            payment = Payment.objects.select_for_update().get(order=order)
            if payment.status == Payment.Status.PENDING_VERIFICATION:
                return Response({"detail": "Review the submitted payment before closing this request."}, status=409)
            if payment.status == Payment.Status.VERIFIED:
                refund_failed_sourcing(order, payment, serializer.validated_data["failure_reason"])
                refunded = True
            elif order.status == Order.Status.AWAITING_PAYMENT:
                order.transition_to(Order.Status.CANCELLED)
                payment.auto_cancel_at = None
                payment.save(update_fields=["auto_cancel_at"])
        book_request.status = BookRequest.Status.FAILED
        book_request.failure_reason = serializer.validated_data["failure_reason"]
        book_request.save(update_fields=["status", "failure_reason", "updated_at"])
        transaction.on_commit(lambda: NotificationService.notify_buyer_request_failed(book_request.buyer, book_request, refunded=refunded))
        return Response({"detail": "Request marked as failed.", "refunded": refunded})


@extend_schema(request=None)
class StartOrderSourcingView(APIView):
    permission_classes = [IsCreator]

    @transaction.atomic
    def post(self, request, order_id):
        reference = get_object_or_404(Order, pk=order_id)
        lock_buyer(reference.buyer_id)
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.status != Order.Status.PAID or order.payment.status != Payment.Status.VERIFIED:
            return Response({"detail": "Only a paid order can start sourcing."}, status=409)
        order.transition_to(Order.Status.SOURCING)
        if order.quote.request_id:
            BookRequest.objects.filter(pk=order.quote.request_id).update(status=BookRequest.Status.SOURCING)
        return Response(OrderSerializer(order).data)


@extend_schema(request=MarkOrderSourcedSerializer)
class MarkOrderSourcedView(APIView):
    permission_classes = [IsCreator]

    @transaction.atomic
    def post(self, request, order_id):
        reference = get_object_or_404(Order, pk=order_id)
        lock_buyer(reference.buyer_id)
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.status not in [Order.Status.PAID, Order.Status.SOURCING] or order.payment.status != Payment.Status.VERIFIED:
            return Response({"detail": "Only a paid order awaiting sourcing can be fulfilled."}, status=409)
        if hasattr(order, "merchandise"):
            raise ValidationError({"detail": "برای این سفارش، آماده‌بودن تمام اقلام را از بخش محصولات تأیید کنید."})
        serializer = MarkOrderSourcedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not order.quote.book_id:
            raise ValidationError({"detail": "ابتدا کتاب این سفارش را در پیشنهاد قیمت مشخص کنید."})
        item = StockItem.objects.create(book_id=order.quote.book_id, unit_price=data.get("unit_price", order.quote.book_cost))
        item.claim_for_buyer(order.buyer, order)
        order.transition_to(Order.Status.STOCK_READY)
        if order.payment.shipment_id:
            from shipping.services import sync_shipment_readiness
            sync_shipment_readiness(order.payment.shipment)
        if order.quote.request_id:
            BookRequest.objects.filter(pk=order.quote.request_id).update(status=BookRequest.Status.READY)
        return Response(OrderSerializer(order).data)


@extend_schema(request=MarkBookRequestFailedSerializer)
class MarkOrderFailedView(APIView):
    permission_classes = [IsCreator]

    @transaction.atomic
    def post(self, request, order_id):
        reference = get_object_or_404(Order, pk=order_id)
        lock_buyer(reference.buyer_id)
        order = Order.objects.select_for_update().get(pk=order_id)
        payment = Payment.objects.select_for_update().get(order=order)
        serializer = MarkBookRequestFailedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if order.status not in [Order.Status.PAID, Order.Status.SOURCING] or payment.status != Payment.Status.VERIFIED:
            return Response({"detail": "Only a paid order awaiting sourcing can fail sourcing."}, status=409)
        reason = serializer.validated_data["failure_reason"]
        refund_failed_sourcing(order, payment, reason)
        if order.quote.request_id:
            book_request = order.quote.request
            book_request.status = BookRequest.Status.FAILED
            book_request.failure_reason = reason
            book_request.save(update_fields=["status", "failure_reason", "updated_at"])
            transaction.on_commit(lambda: NotificationService.notify_buyer_request_failed(order.buyer, book_request, refunded=True))
        return Response(OrderSerializer(order).data)
