from django.urls import path

from .views import HoldStockItemView, MyShelfView

urlpatterns = [
    path("shelf/mine/", MyShelfView.as_view(), name="my-shelf"),
    path("<int:stock_item_id>/hold/", HoldStockItemView.as_view(), name="hold-stock-item"),
]
