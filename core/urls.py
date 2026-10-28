from django.urls import path

from .views import AdminDashboardView
from .admin_activity import AdminActivity

from .store_settings import AdminStoreSettingsView

urlpatterns = [
    path("activity/", AdminActivity.as_view(), name="admin-activity"),
    path("store-settings/", AdminStoreSettingsView.as_view(), name="admin-store-settings"),
    path("dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),
]
