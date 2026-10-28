from django.conf import settings
from django.db import models
from core.models import TimeStampedModel


class Product(TimeStampedModel):
    title = models.CharField(max_length=250)
    category = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    specifications = models.TextField(blank=True)
    price = models.PositiveBigIntegerField(default=0)
    is_active = models.BooleanField(default=False)
    sold_separately = models.BooleanField(default=True)
    is_bundle = models.BooleanField(default=False)
    fulfillment = models.CharField(max_length=10, choices=[('stock', 'Ready stock'), ('source', 'Source after payment')], default='stock')
    quantity = models.PositiveIntegerField(default=0)  # Unreserved units; shared by bundles and standalone sales.
    lead_days = models.PositiveSmallIntegerField(default=0)
    featured = models.BooleanField(default=False)
    priority = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['priority', '-id']


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    caption = models.CharField(max_length=250, blank=True)

    class Meta:
        ordering = ['id']


class BundleComponent(models.Model):
    bundle = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='components')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True, related_name='used_in')
    edition = models.ForeignKey('publisher_catalog.Edition', on_delete=models.PROTECT, null=True, blank=True)
    quantity = models.PositiveSmallIntegerField(default=1)

    class Meta:
        constraints = [models.CheckConstraint(condition=(models.Q(product__isnull=False, edition__isnull=True) | models.Q(product__isnull=True, edition__isnull=False)), name='component_one_source'), models.CheckConstraint(condition=models.Q(quantity__gte=1), name='component_positive_quantity')]


class Purchase(models.Model):
    order = models.OneToOneField('requests_orders.Order', on_delete=models.CASCADE, related_name='merchandise')
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    key = models.UUIDField()
    units = models.JSONField(default=list)  # Immutable names, prices, contents and stock allocations at checkout.
    requires_sourcing = models.BooleanField(default=False)
    released = models.BooleanField(default=False)
    fulfilled = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['buyer', 'key'], name='unique_cart_checkout')]


class FulfillmentUnit(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='fulfillment_units')
    index = models.PositiveSmallIntegerField()
    stock_item = models.OneToOneField('stock.StockItem', null=True, blank=True, on_delete=models.PROTECT)
    failed = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['purchase', 'index'], name='unique_purchase_unit')]
