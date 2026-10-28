from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from core.permissions import IsCreator
from catalog.locking import lock_catalog
from catalog.admin_api import AdminPagination
from catalog.models import Book
from .models import Publisher, Edition, PublisherImportProfile as Profile, PublisherImportBatch as Batch, PublisherImportRow as Row
from .serializers import PublisherSerializer, SaveImportProfileRequestSerializer, PublisherImportProfileSerializer, PublisherImportBatchSerializer
from .staging import before_values, normalize_persian, refresh_deactivations, validate_ready


def queue_preview(batch):
    from .tasks import process_publisher_import
    try:
        process_publisher_import.apply_async(args=[batch.pk], queue="catalog_imports")
    except Exception:
        Batch.objects.filter(pk=batch.pk).update(status=Batch.Status.FAILED, error_message="صف پردازش در دسترس نیست. کمی بعد «ساخت دوباره پیش‌نمایش» را انتخاب کنید.")


class PublisherDetail(generics.RetrieveUpdateAPIView):
    permission_classes = [IsCreator]
    serializer_class = PublisherSerializer
    queryset = Publisher.objects.all()

    @transaction.atomic
    def perform_update(self, serializer):
        lock_catalog()
        serializer.save()


class ProfileDetail(generics.RetrieveUpdateAPIView):
    permission_classes = [IsCreator]
    queryset = Profile.objects.all()

    def get_serializer_class(self):
        return PublisherImportProfileSerializer if self.request.method == "GET" else ProfileEditSerializer


class ProfileEditSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["label", "price_unit", "column_mapping", "sheet_name", "header_row_index"]

    def validate(self, attrs):
        current = self.instance
        payload = {"mode": current.mode, "publisher_id": current.publisher_id, "label": attrs.get("label", current.label), "price_unit": attrs.get("price_unit", current.price_unit), "column_mapping": attrs.get("column_mapping", current.column_mapping), "sheet_name": attrs.get("sheet_name", current.sheet_name), "header_row_index": attrs.get("header_row_index", current.header_row_index)}
        checked = SaveImportProfileRequestSerializer(data=payload)
        checked.is_valid(raise_exception=True)
        return attrs


class BatchList(generics.ListAPIView):
    permission_classes = [IsCreator]
    serializer_class = PublisherImportBatchSerializer
    pagination_class = AdminPagination

    def get_queryset(self):
        qs = Batch.objects.select_related("publisher", "profile").order_by("-created_at", "-pk")
        pub = self.request.query_params.get("publisher_id")
        if pub:
            if not pub.isdecimal():
                raise serializers.ValidationError("ناشر معتبر نیست.")
            qs = qs.filter(publisher_id=pub)
        return qs


class RowSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source="book.title", read_only=True, default="")
    class Meta:
        model = Row
        fields = ["id", "row_number", "data", "decision", "book", "book_title", "candidates", "before", "error"]


class BatchRows(generics.ListAPIView):
    permission_classes = [IsCreator]
    serializer_class = RowSerializer
    pagination_class = AdminPagination

    def get_queryset(self):
        qs = Row.objects.filter(batch_id=self.kwargs["batch_id"]).select_related("book")
        decision = self.request.query_params.get("decision")
        if decision in {"pending", "match", "new", "skip"}:
            qs = qs.filter(decision=decision)
        query = self.request.query_params.get("q", "").strip()[:200]
        if query:
            qs = qs.filter(data__title__icontains=query)
        return qs


class RowDecision(APIView):
    permission_classes = [IsCreator]

    @transaction.atomic
    def patch(self, request, batch_id, pk):
        lock_catalog()
        batch = get_object_or_404(Batch.objects.select_for_update(), pk=batch_id)
        if batch.status != Batch.Status.REVIEW:
            return Response({"detail": "این فایل اکنون قابل ویرایش نیست."}, status=409)
        row = get_object_or_404(Row.objects.select_for_update(), pk=pk, batch=batch)
        decision = request.data.get("decision")
        if decision not in {"match", "new", "skip"}:
            raise serializers.ValidationError("تصمیم معتبر نیست.")
        if row.error and decision != "skip":
            raise serializers.ValidationError("ردیف نامعتبر را در فایل اصلاح کنید و پیش‌نمایش تازه بسازید.")
        if decision == "match":
            field = serializers.PrimaryKeyRelatedField(queryset=Book.objects.all())
            book = field.run_validation(request.data.get("book_id"))
            row.book = book
            edition = next((ed for ed in book.editions.select_related("publisher") if normalize_persian(ed.publisher.name) == normalize_persian(row.data["publisher_name"])), None)
            row.before = before_values(book, edition)
        elif decision == "new":
            row.book = None
            row.before = {}
        # A skipped matched row remains represented in complete-catalog imports.
        row.decision = decision
        row.save()
        batch.needs_review_rows = batch.rows.filter(decision="pending").count()
        batch.revision += 1
        refresh_deactivations(batch)
        batch.save()
        return Response(RowSerializer(row).data)


class ConfirmBatch(APIView):
    permission_classes = [IsCreator]

    @transaction.atomic
    def post(self, request, batch_id):
        lock_catalog()
        batch = get_object_or_404(Batch.objects.select_for_update(), pk=batch_id)
        if batch.status == Batch.Status.DONE:
            return Response(PublisherImportBatchSerializer(batch).data)
        if request.data.get("revision") != batch.revision:
            return Response({"detail": "پیش‌نمایش تغییر کرده است. صفحه را تازه‌سازی و دوباره بررسی کنید."}, status=409)
        validate_ready(batch)
        batch.status = Batch.Status.APPLYING
        batch.error_message = ""
        batch.save()
        transaction.on_commit(lambda: queue_apply(batch.pk))
        return Response({"status": "applying"}, status=202)


def queue_apply(pk):
    from .tasks import apply_publisher_import
    try:
        apply_publisher_import.apply_async(args=[pk], queue="catalog_imports")
    except Exception:
        Batch.objects.filter(pk=pk).update(status=Batch.Status.FAILED, error_message="صف پردازش در دسترس نیست. دوباره پیش‌نمایش بسازید.")


class RebuildBatch(APIView):
    permission_classes = [IsCreator]

    @transaction.atomic
    def post(self, request, batch_id):
        batch = get_object_or_404(Batch.objects.select_for_update(), pk=batch_id)
        if batch.status not in {Batch.Status.REVIEW, Batch.Status.FAILED}:
            return Response({"detail": "فایل در حال پردازش است یا قبلاً اعمال شده است."}, status=409)
        if not batch.profile_snapshot:
            raise serializers.ValidationError("برای این ورود قدیمی، فایل را دوباره بارگذاری کنید.")
        batch.status = Batch.Status.PENDING
        batch.error_message = ""
        batch.save()
        transaction.on_commit(lambda: queue_preview(batch))
        return Response({"status": "pending"}, status=202)
