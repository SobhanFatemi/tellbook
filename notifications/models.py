from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class NotificationLog(TimeStampedModel):
    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"

    recipient_phone = models.CharField(max_length=15, blank=True)
    recipient_email = models.EmailField(blank=True, null=True)
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.SMS)
    message = models.TextField()
    related_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    sent_successfully = models.BooleanField(default=False)
    error_detail = models.TextField(blank=True)  # the actual exception message, if sending failed
