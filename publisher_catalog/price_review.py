"""Staff-only screening of base edition prices, with stale-safe bulk disabling."""
import hashlib
import json
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from catalog.admin_api import AdminPagination
from catalog.locking import lock_catalog
from core.permissions import IsCreator
from core.models import StoreSettings
from .models import Edition

DEFAULT_LOW_PRICE_THRESHOLD = 100000


class ReviewParameters(serializers.Serializer):
    threshold = serializers.DecimalField(max_digits=12, decimal_places=0, min_value=1, required=False)
    status = serializers.ChoiceField(choices=['active','inactive','all'], default='active')


def configured_threshold():
    return StoreSettings.objects.filter(pk=1).values_list("price_review_threshold",flat=True).first() or DEFAULT_LOW_PRICE_THRESHOLD


def flagged(threshold):
    return Edition.objects.filter(Q(price__lt=threshold) | ~Q(price_review_note="")).select_related('book','publisher').order_by('price','pk')


def proposal(threshold):
    rows = list(flagged(threshold).filter(is_active=True).values_list('pk','price','updated_at'))
    token = hashlib.sha256(json.dumps([str(threshold),rows],default=str).encode()).hexdigest()
    return rows, token


class LowPriceReview(APIView):
    permission_classes = [IsCreator]

    def get(self, request):
        params=ReviewParameters(data=request.query_params)
        params.is_valid(raise_exception=True)
        threshold=params.validated_data.get('threshold', configured_threshold())
        qs=flagged(threshold)
        status=params.validated_data['status']
        if status != 'all':
            qs=qs.filter(is_active=status=='active')
        pager=AdminPagination()
        page=pager.paginate_queryset(qs,request)
        response=pager.get_paginated_response([{
            'id':ed.pk,'book':ed.book_id,'title':ed.book.title,'publisher':ed.publisher.name,
            'price':str(ed.price),'is_active':ed.is_active,'isbn':ed.isbn,
            'print_year':ed.print_year,'page_count':ed.page_count,'review_note':ed.price_review_note,
        } for ed in page])
        active,token=proposal(threshold)
        response.data.update(threshold=str(threshold),active_count=len(active),confirmation_token=token)
        return response

    @transaction.atomic
    def patch(self,request):
        field=serializers.DecimalField(max_digits=12,decimal_places=0,min_value=1)
        threshold=field.run_validation(request.data.get('threshold'))
        lock_catalog()
        config=StoreSettings.current()
        config.price_review_threshold=threshold
        config.save(update_fields=['price_review_threshold','updated_at'])
        return Response({'threshold':str(threshold)})

    @transaction.atomic
    def post(self,request):
        params=ReviewParameters(data=request.data)
        params.is_valid(raise_exception=True)
        threshold=params.validated_data.get('threshold', configured_threshold())
        lock_catalog()
        active,token=proposal(threshold)
        if request.data.get('confirmation_token') != token:
            return Response({'detail':'فهرست قیمت‌ها تغییر کرده است؛ صفحه را تازه‌سازی و دوباره بررسی کنید.'},status=409)
        ids=[row[0] for row in active]
        count=Edition.objects.filter(pk__in=ids).update(is_active=False,updated_at=timezone.now())
        return Response({'disabled_count':count})
