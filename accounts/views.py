import hashlib
import secrets
from contextlib import contextmanager
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import connection, transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import OTPCode, User
from .serializers import RequestOTPSerializer, UserSerializer, VerifyOTPSerializer

OTP_TTL_MINUTES = 5
MAX_OTP_ATTEMPTS = 5


def development_login_enabled(request):
    private_staging = getattr(settings, "STAGING_TEST_MODE", False) and getattr(request, "staging_authorized", False)
    return (settings.DEBUG or private_staging) and getattr(settings, "OTP_DELIVERY_MODE", "sms") == "development"



@contextmanager
def phone_lock(phone):
    """Serialize issuance and redemption even before a user row exists."""
    key = int.from_bytes(hashlib.sha256(phone.encode()).digest()[:8], "big", signed=True)
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [key])
        yield


@extend_schema(request=RequestOTPSerializer)
class RequestOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp-request"

    def post(self, request):
        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        if not development_login_enabled(request):
            return Response({"detail": "Phone sign-in is unavailable until SMS delivery is configured."}, status=503)

        with phone_lock(phone):
            user = User.objects.filter(phone=phone).first()
            if user and not user.is_active:
                return Response({"detail": "Account sign-in is unavailable. Contact support."}, status=403)
            code = f"{secrets.randbelow(1000000):06d}"
            otp = OTPCode.objects.create(
                phone=phone, code=make_password(code),
                expires_at=timezone.now() + timedelta(minutes=OTP_TTL_MINUTES),
            )
            OTPCode.objects.filter(phone=phone, is_used=False).exclude(pk=otp.pk).update(is_used=True)
        response = Response({
            "detail": "Development verification code generated. No SMS was sent.",
            "channel": "development", "challenge_id": str(otp.challenge_id),
            "development_code": code, "expires_in": OTP_TTL_MINUTES * 60,
        })
        response["Cache-Control"] = "no-store"
        return response



@extend_schema(request=VerifyOTPSerializer)
class VerifyOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp-verify"

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        if not development_login_enabled(request):
            return Response({"detail": "Phone sign-in is unavailable until SMS delivery is configured."}, status=503)
        with phone_lock(phone):
            otp = OTPCode.objects.select_for_update().filter(
                phone=phone, challenge_id=serializer.validated_data["challenge_id"],
                is_used=False, expires_at__gt=timezone.now(),
            ).first()
            if not otp or otp.attempts >= MAX_OTP_ATTEMPTS:
                return Response({"detail": "Invalid or expired code. Request a new code."}, status=400)
            if not check_password(serializer.validated_data["code"], otp.code):
                otp.attempts += 1
                otp.is_used = otp.attempts >= MAX_OTP_ATTEMPTS
                otp.save(update_fields=["attempts", "is_used"])
                return Response({"detail": "Invalid or expired code. Request a new code if needed."}, status=400)
            otp.is_used = True
            otp.save(update_fields=["is_used"])
            user = User.objects.filter(phone=phone).first()
            if user and not user.is_active:
                return Response({"detail": "Account sign-in is unavailable. Contact support."}, status=403)
            if user is None:
                user = User.objects.create_user(phone=phone)
            refresh = RefreshToken.for_user(user)
            return Response({"access": str(refresh.access_token), "refresh": str(refresh), "user": UserSerializer(user).data})


class CurrentUserView(RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
