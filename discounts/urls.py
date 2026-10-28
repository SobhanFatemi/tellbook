from django.urls import path

from .views import DiscountCodeDetailView, DiscountCodeListCreateView, ValidateDiscountCodeView

urlpatterns = [
    path("", DiscountCodeListCreateView.as_view(), name="discount-code-list-create"),
    path("<int:code_id>/", DiscountCodeDetailView.as_view(), name="discount-code-detail"),
    path("validate/", ValidateDiscountCodeView.as_view(), name="discount-code-validate"),
]
