from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core.store_settings import PublicStoreSettingsView

urlpatterns = [
    path("api/store/", PublicStoreSettingsView.as_view(), name="public-store-settings"),
    path("django-admin/" if getattr(settings, "STAGING_TEST_MODE", False) else "admin/", admin.site.urls),

    path("api/accounts/", include("accounts.urls")),
    path("api/admin/", include("core.urls")),
    path("api/products/", include("merchandise.urls")),
    path("api/catalog/", include("catalog.urls")),
    path("api/publishers/", include("publisher_catalog.urls")),
    path("api/orders/", include("requests_orders.urls")),
    path("api/payments/", include("payments.urls")),
    path("api/stock/", include("stock.urls")),
    path("api/shipping/", include("shipping.urls")),
    path("api/discounts/", include("discounts.urls")),
    path("api/refunds/", include("refunds.urls")),

    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
