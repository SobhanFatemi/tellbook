from django.urls import path

from .views import (
    MarkRefundProcessedView,
    RefundDetailView,
    RefundListView,
    RefundPolicyDetailView,
    RefundPolicyListCreateView,
)

urlpatterns = [
    path("", RefundListView.as_view(), name="refund-list"),
    path("<int:refund_id>/", RefundDetailView.as_view(), name="refund-detail"),
    path("<int:refund_id>/process/", MarkRefundProcessedView.as_view(), name="refund-mark-processed"),
    path("policies/", RefundPolicyListCreateView.as_view(), name="refund-policy-list-create"),
    path("policies/<int:policy_id>/", RefundPolicyDetailView.as_view(), name="refund-policy-detail"),
]
