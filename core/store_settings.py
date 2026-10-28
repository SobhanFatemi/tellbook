import re

from rest_framework import serializers
from rest_framework.generics import RetrieveAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny

from .models import StoreSettings
from .permissions import IsCreator


class StoreSettingsSerializer(serializers.ModelSerializer):
    shipping_fee = serializers.DecimalField(max_digits=12, decimal_places=0, min_value=1, allow_null=True, required=False)

    shipping_fee_over_six = serializers.DecimalField(max_digits=12, decimal_places=0, min_value=1, required=False)

    def validate_support_telegram(self, value):
        value = value.strip().removeprefix('@')
        if value and not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{4,31}', value):
            raise serializers.ValidationError('نام کاربری تلگرام را بدون لینک وارد کنید؛ مانند dayana_books.')
        return value

    class Meta:
        model = StoreSettings
        fields = ['logo', 'shipping_fee', 'shipping_fee_over_six', 'support_telegram', 'transfer_recipient', 'transfer_account', 'transfer_instructions']

    def validate_logo(self, value):
        if value is not None and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError('Logo must be no larger than 5 MB.')
        return value


class PublicStoreSettingsView(RetrieveAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = StoreSettingsSerializer

    def get_object(self):
        # Reading the public endpoint must not create database rows.
        return StoreSettings.objects.filter(pk=1).first() or StoreSettings(pk=1)


class AdminStoreSettingsView(RetrieveUpdateAPIView):
    permission_classes = [IsCreator]
    serializer_class = StoreSettingsSerializer

    def get_object(self):
        return StoreSettings.current()
