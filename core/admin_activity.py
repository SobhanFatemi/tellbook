"""Per-admin, section-level unread markers for the existing work queues."""
from datetime import datetime, timezone as datetime_timezone

from django.core import signing
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AdminSectionRead, StoreSettings
from .permissions import IsCreator

SECTIONS = ('requests', 'orders', 'shipments', 'refunds', 'reviews', 'prices', 'imports')
SALT = 'admin-section-read-v1'


def queues():
    from catalog.models import Book
    from requests_orders.models import BookRequest, Order
    from shipping.models import Shipment
    from refunds.models import Refund
    from publisher_catalog.models import PublisherImportBatch
    from publisher_catalog.price_review import flagged
    store = StoreSettings.current()
    return {
        'requests': (BookRequest.objects.exclude(status__in=['failed', 'ready']), ['updated_at', 'quote__updated_at']),
        'orders': (Order.objects.exclude(status__in=['shipped', 'cancelled', 'failed', 'refunded']), ['updated_at', 'payment__updated_at']),
        'shipments': (Shipment.objects.exclude(status__in=['shipped', 'delivered', 'cancelled']), ['updated_at', 'payment__updated_at']),
        'refunds': (Refund.objects.filter(status='pending'), ['updated_at']),
        'reviews': (Book.objects.filter(needs_review=True), ['updated_at']),
        'prices': (flagged(store.price_review_threshold).filter(is_active=True), ['updated_at']),
        'imports': (PublisherImportBatch.objects.filter(status__in=['pending', 'processing', 'review', 'applying', 'failed']), ['updated_at']),
    }, store.updated_at


class AdminActivity(APIView):
    permission_classes = [IsCreator]

    def get(self, request):
        as_of = timezone.now()
        markers = dict(AdminSectionRead.objects.filter(user=request.user).values_list('section', 'seen_through'))
        sources, price_settings_changed = queues()
        counts = {}
        for section, (queryset, fields) in sources.items():
            since = markers.get(section, datetime.min.replace(tzinfo=datetime_timezone.utc))
            changes = Q()
            for field in fields:
                changes |= Q(**{f'{field}__gt': since, f'{field}__lte': as_of})
            if section == 'prices' and since < price_settings_changed <= as_of:
                changes = Q(updated_at__lte=as_of)
            counts[section] = queryset.filter(changes).distinct().count()
        from payments.models import Payment
        since = markers.get('orders', datetime.min.replace(tzinfo=datetime_timezone.utc))
        counts['orders'] += Payment.objects.filter(order__isnull=True, status='pending_verification', updated_at__gt=since, updated_at__lte=as_of).count()
        token = signing.dumps({'user': request.user.pk, 'through': as_of.isoformat()}, salt=SALT)
        return Response({'counts': counts, 'snapshot': token})

    def post(self, request):
        section = serializers.ChoiceField(choices=SECTIONS).run_validation(request.data.get('section'))
        try:
            payload = signing.loads(request.data.get('snapshot', ''), salt=SALT, max_age=300)
            if payload['user'] != request.user.pk:
                raise ValueError
            through = datetime.fromisoformat(payload['through'])
        except (signing.BadSignature, ValueError, KeyError, TypeError):
            raise serializers.ValidationError('بازه بازدید معتبر نیست. صفحه را تازه‌سازی کنید.')
        with transaction.atomic():
            marker, _ = AdminSectionRead.objects.get_or_create(user=request.user, section=section, defaults={'seen_through': through})
            marker = AdminSectionRead.objects.select_for_update().get(pk=marker.pk)
            if marker.seen_through < through:
                marker.seen_through = through
                marker.save(update_fields=['seen_through'])
        return Response({'section': section})
