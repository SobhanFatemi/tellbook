from .price_review import LowPriceReview
from .admin_api import PublisherDetail, ProfileDetail, BatchList, BatchRows, RowDecision, ConfirmBatch, RebuildBatch
from django.urls import path

from .views import (
    ImportPriceUnitView,
    EditionListForBookView,
    EditionUpdateView,
    ImportBatchStatusView,
    NeedsReviewBookListView,
    PreviewPublisherColumnsView,
    PublisherImportProfileListView,
    PublisherListCreateView,
    SaveImportProfileView,
    UploadPublisherFileView,
)

urlpatterns = [
    path("price-review/", LowPriceReview.as_view()),
    path("<int:pk>/", PublisherDetail.as_view()),
    path("import-batches/", BatchList.as_view()),
    path("import-batches/<int:batch_id>/rows/", BatchRows.as_view()),
    path("import-batches/<int:batch_id>/rows/<int:pk>/", RowDecision.as_view()),
    path("import-batches/<int:batch_id>/confirm/", ConfirmBatch.as_view()),
    path("import-batches/<int:batch_id>/rebuild/", RebuildBatch.as_view()),
    path("import-profiles/<int:pk>/", ProfileDetail.as_view(), name="import-price-unit"),
    path("", PublisherListCreateView.as_view(), name="publisher-list-create"),
    path("preview-columns/", PreviewPublisherColumnsView.as_view(), name="preview-publisher-columns"),
    path("import-profiles/", SaveImportProfileView.as_view(), name="save-import-profile"),
    path("import-profiles/mine/", PublisherImportProfileListView.as_view(), name="list-import-profiles"),
    path("import-profiles/<int:profile_id>/upload/", UploadPublisherFileView.as_view(), name="upload-publisher-file"),
    path("import-batches/<int:batch_id>/", ImportBatchStatusView.as_view(), name="import-batch-status"),
    path("needs-review/", NeedsReviewBookListView.as_view(), name="needs-review-books"),
    path("editions/book/<int:book_id>/", EditionListForBookView.as_view(), name="editions-for-book"),
    path("editions/<int:pk>/edit/", EditionUpdateView.as_view(), name="edition-update"),
]
