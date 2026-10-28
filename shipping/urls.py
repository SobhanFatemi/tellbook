from django.urls import path

from .views import (
    MarkDeliveredView,
    MarkShippedView,
    ShipMyShelfView,
    ShipmentQueueView,
    ShippingAddressListCreateView, ShippingAddressDetailView, MyShipmentsView, CancelUnpaidShipmentView,
)

urlpatterns = [
    path("ship-shelf/", ShipMyShelfView.as_view(), name="ship-shelf-inline"),
    path("mine/", MyShipmentsView.as_view(), name="my-shipments"),
    path("addresses/<int:pk>/", ShippingAddressDetailView.as_view(), name="address-detail"),
    path("<int:shipment_id>/cancel/", CancelUnpaidShipmentView.as_view(), name="cancel-unpaid-shipment"),
    path("addresses/", ShippingAddressListCreateView.as_view(), name="shipping-addresses"),
    path("ship-shelf/<int:address_id>/", ShipMyShelfView.as_view(), name="ship-my-shelf"),
    path("queue/", ShipmentQueueView.as_view(), name="shipment-queue"),
    path("<int:shipment_id>/mark-shipped/", MarkShippedView.as_view(), name="mark-shipped"),
    path("<int:shipment_id>/mark-delivered/", MarkDeliveredView.as_view(), name="mark-delivered"),
]
