from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class StoreSettings(TimeStampedModel):
    """One staff-managed store configuration. Fees are snapshotted on shipments."""
    logo = models.ImageField(upload_to='branding/', blank=True, null=True)
    price_review_threshold = models.DecimalField(max_digits=12, decimal_places=0, default=100000)
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=0, default=175000, null=True, blank=True)
    shipping_fee_over_six = models.DecimalField(max_digits=12, decimal_places=0, default=250000)
    support_telegram = models.CharField(max_length=32, blank=True)
    transfer_recipient = models.CharField(max_length=200, blank=True)
    transfer_account = models.CharField(max_length=100, blank=True)
    transfer_instructions = models.TextField(blank=True)

    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]


class AdminSectionRead(models.Model):
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='admin_section_reads')
    section = models.CharField(max_length=24)
    seen_through = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'section'], name='unique_admin_section_read')]
