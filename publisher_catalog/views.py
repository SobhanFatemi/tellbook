from drf_spectacular.utils import extend_schema
from rest_framework.generics import CreateAPIView, ListAPIView, UpdateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db import transaction

from core.permissions import IsCreator
from .models import Edition, Publisher, PublisherImportBatch, PublisherImportProfile
from .parsing import preview_columns, WorksheetNotFound
from .serializers import (
    ImportPriceUnitSerializer,
    EditionSerializer,
    EditionUpdateSerializer,
    PreviewColumnsRequestSerializer,
    PublisherImportBatchSerializer,
    PublisherImportProfileSerializer,
    PublisherSerializer,
    SaveImportProfileRequestSerializer,
    UploadPublisherFileRequestSerializer,
)


class PublisherListCreateView(CreateAPIView, ListAPIView):
    serializer_class = PublisherSerializer
    permission_classes = [IsCreator]
    queryset = Publisher.objects.all().order_by("name")

    @transaction.atomic
    def perform_create(self, serializer):
        from catalog.locking import lock_catalog
        lock_catalog()
        serializer.save()



@extend_schema(
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'file': {'type': 'string', 'format': 'binary'},
                'sheet_name': {'type': 'string'},
                'header_row_index': {'type': 'integer', 'default': 0},
            },
            'required': ['file'],
        }
    }
)
class PreviewPublisherColumnsView(APIView):
    """Onboarding step 1: upload a sample file, see its real column headers."""
    permission_classes = [IsCreator]

    def post(self, request):
        serializer = PreviewColumnsRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            result = preview_columns(
                data["file"],
                sheet_name=data.get("sheet_name") or None,
                header_row_index=data.get("header_row_index", 0),
            )
        except WorksheetNotFound as exc:
            return Response({"detail": str(exc), "available_sheets": exc.available_sheets}, status=400)
        except Exception:
            return Response({"detail": "خواندن فایل اکسل انجام نشد. سالم‌بودن فایل xlsx و شماره ردیف عنوان ستون‌ها را بررسی کنید."}, status=400)
        return Response(result)


class PublisherImportProfileListView(ListAPIView):
    """
    So you can check what mappings already exist for a publisher before
    accidentally creating a duplicate profile via SaveImportProfileView.
    Supports ?publisher_id=<id> to filter to just one publisher.
    """
    serializer_class = PublisherImportProfileSerializer
    permission_classes = [IsCreator]

    def get_queryset(self):
        qs = PublisherImportProfile.objects.all().order_by("-created_at")
        publisher_id = self.request.query_params.get("publisher_id")
        if publisher_id:
            qs = qs.filter(publisher_id=publisher_id)
        return qs


@extend_schema(request=SaveImportProfileRequestSerializer)
class SaveImportProfileView(APIView):
    """
    Onboarding step 2: save the column mapping. mode='single' requires a
    publisher_id; mode='multi' does not (each row carries its own publisher).
    """
    permission_classes = [IsCreator]

    def post(self, request):
        serializer = SaveImportProfileRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        mode = data["mode"]
        publisher_id = data.get("publisher_id")

        if mode == PublisherImportProfile.Mode.SINGLE and not publisher_id:
            return Response({"detail": "publisher_id is required for mode=single."}, status=400)

        profile = PublisherImportProfile.objects.create(
            price_unit=data["price_unit"],
            publisher_id=publisher_id if mode == PublisherImportProfile.Mode.SINGLE else None,
            mode=mode,
            column_mapping=data["column_mapping"],
            header_row_index=data.get("header_row_index", 0),
            sheet_name=data.get("sheet_name") or None,
            label=data.get("label", ""),
        )
        return Response(PublisherImportProfileSerializer(profile).data, status=201)


@extend_schema(
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'file': {'type': 'string', 'format': 'binary'},
            },
            'required': ['file'],
        }
    }
)
class UploadPublisherFileView(APIView):
    """
    The actual recurring upload, against an existing saved profile. Handles
    both single-publisher and multi-publisher files transparently based on
    the profile's mode.

    Processing happens in a Celery task, not inline -- a large sheet
    (real files tested against had 65k+ rows) would time out an HTTP
    request if parsed and synced synchronously. This view just saves the
    file, enqueues the task, and returns immediately; poll
    ImportBatchStatusView for progress/results.
    """
    permission_classes = [IsCreator]

    def post(self, request, profile_id):
        profile = get_object_or_404(PublisherImportProfile.objects.select_related("publisher"), id=profile_id)
        serializer = UploadPublisherFileRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        batch = PublisherImportBatch.objects.create(
            profile=profile,
            publisher=profile.publisher if profile.mode == PublisherImportProfile.Mode.SINGLE else None,
            file=serializer.validated_data["file"],
            status=PublisherImportBatch.Status.PENDING,
            complete_catalog=serializer.validated_data["complete_catalog"],
            profile_snapshot={"mode": profile.mode, "price_unit": serializer.validated_data["price_unit"], "publisher_name": profile.publisher.name if profile.publisher else "", "column_mapping": profile.column_mapping, "header_row_index": profile.header_row_index, "sheet_name": profile.sheet_name},
        )

        from .admin_api import queue_preview
        queue_preview(batch)

        return Response({
            "batch_id": batch.id,
            "status": batch.status,
            "detail": "Import queued. Poll /api/publishers/import-batches/<batch_id>/ for progress.",
        }, status=202)


class ImportBatchStatusView(APIView):
    permission_classes = [IsCreator]

    def get(self, request, batch_id):
        batch = get_object_or_404(PublisherImportBatch, id=batch_id)
        return Response(PublisherImportBatchSerializer(batch).data)


class NeedsReviewBookListView(ListAPIView):
    permission_classes = [IsCreator]

    def get_queryset(self):
        from catalog.models import Book
        return Book.objects.filter(needs_review=True)

    def list(self, request, *args, **kwargs):
        from catalog.serializers import BookSerializer
        return Response(BookSerializer(self.get_queryset(), many=True).data)


class EditionListForBookView(ListAPIView):
    """All active editions of one book -- the 'which publisher?' picker for buyers."""
    serializer_class = EditionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Edition.objects.filter(book_id=self.kwargs["book_id"], is_active=True).order_by("price")


@extend_schema(request={'multipart/form-data': EditionUpdateSerializer})
class EditionUpdateView(UpdateAPIView):
    """
    Staff-only edit -- cover is the main reason this exists. None of the real
    supplier files (چشمه, ماهی, ليست کتاب) contain any cover images at all,
    so this is how a cover actually gets attached: manually, after she has
    the book in hand, or via the offline-fetch bulk-import flow.
    """
    serializer_class = EditionUpdateSerializer
    permission_classes = [IsCreator]
    queryset = Edition.objects.all()



class ImportPriceUnitView(RetrieveUpdateAPIView):
    """Declare units for future imports; never silently reprice existing editions."""
    permission_classes = [IsCreator]
    serializer_class = ImportPriceUnitSerializer
    queryset = PublisherImportProfile.objects.all()
