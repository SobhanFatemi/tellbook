from django.core.validators import RegexValidator
from rest_framework import serializers

from .models import User

iranian_mobile_validator = RegexValidator(
    regex=r"^09\d{9}$",
    message="Enter a valid Iranian mobile number, e.g. 09121234567.",
)


class RequestOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15, validators=[iranian_mobile_validator])


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "phone", "email", "full_name", "role"]
        read_only_fields = ["id", "role"]


class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15, validators=[iranian_mobile_validator])
    code = serializers.RegexField(r"^[0-9]{6}$")
    challenge_id = serializers.UUIDField()
