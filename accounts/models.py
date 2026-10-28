import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models

from core.models import TimeStampedModel


class UserManager(BaseUserManager):
    def create_user(self, phone, role="buyer", **extra_fields):
        if not phone:
            raise ValueError("Phone is required")
        user = self.model(phone=phone, role=role, **extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password, **extra_fields):
        user = self.model(phone=phone, role="creator", is_staff=True, is_superuser=True, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        BUYER = "buyer", "Buyer"
        CREATOR = "creator", "Creator"

    phone = models.CharField(max_length=15, unique=True)
    email = models.EmailField(blank=True, null=True)       # Optional contact address; never used for login.
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.BUYER)
    full_name = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return f"{self.phone} ({self.role})"


class OTPCode(TimeStampedModel):
    phone = models.CharField(max_length=15, db_index=True)
    code = models.CharField(max_length=128)
    challenge_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)  # wrong guesses against THIS code

    class Meta:
        indexes = [models.Index(fields=["phone", "is_used"])]
