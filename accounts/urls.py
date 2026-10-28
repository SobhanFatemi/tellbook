from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import CurrentUserView, RequestOTPView, VerifyOTPView

urlpatterns = [
    path("me/", CurrentUserView.as_view(), name="current-user"),
    path("otp/request/", RequestOTPView.as_view(), name="request-otp"),
    path("otp/verify/", VerifyOTPView.as_view(), name="verify-otp"),
    # Access tokens last 7 days, but there was no way to silently renew one
    # without re-doing the whole OTP flow -- standard SimpleJWT view, no
    # custom logic needed.
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
]
