from django.urls import path
from .cancellation import CancelOrderView

from .views import (
    AcceptQuoteView,
    AdminOrderListView,
    AdminRequestListView,
    BookRequestCreateView,
    BuyInStockView,
    BuyEditionView,
    MarkBookRequestFailedView,
    MarkOrderSourcedView,
    MarkOrderFailedView,
    MyOrdersView,
    MyRequestsView,
    SendQuoteView,
    StartOrderSourcingView,
)

urlpatterns = [
    path("<int:order_id>/cancel/", CancelOrderView.as_view(), name="cancel-order"),
    path("<int:order_id>/fail/", MarkOrderFailedView.as_view(), name="mark-order-failed"),
    path("requests/", BookRequestCreateView.as_view(), name="request-create"),
    path("requests/mine/", MyRequestsView.as_view(), name="my-requests"),
    path("requests/all/", AdminRequestListView.as_view(), name="admin-request-list"),
    path("requests/<int:request_id>/quote/", SendQuoteView.as_view(), name="send-quote"),
    path("requests/<int:request_id>/fail/", MarkBookRequestFailedView.as_view(), name="mark-request-failed"),
    path("quotes/<int:quote_id>/accept/", AcceptQuoteView.as_view(), name="accept-quote"),
    path("mine/", MyOrdersView.as_view(), name="my-orders"),
    path("all/", AdminOrderListView.as_view(), name="admin-order-list"),
    path("buy/stock/<int:book_id>/", BuyInStockView.as_view(), name="buy-in-stock"),
    path("buy/edition/<int:edition_id>/", BuyEditionView.as_view(), name="buy-edition"),
    path("<int:order_id>/start-sourcing/", StartOrderSourcingView.as_view(), name="start-order-sourcing"),
    path("<int:order_id>/mark-sourced/", MarkOrderSourcedView.as_view(), name="mark-order-sourced"),
]
