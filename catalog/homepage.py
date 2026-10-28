from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from core.permissions import IsCreator
from .models import Book
from .serializers import BookSerializer
from .querysets import with_card_data
from .locking import lock_catalog


class HomepageBooks(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        eligible = Book.objects.filter(needs_review=False)
        chosen = eligible.filter(homepage_selected=True)
        manual = chosen.exists()
        books = chosen.order_by('title','pk') if manual else eligible.order_by('?')[:12]
        response = Response({'mode':'manual' if manual else 'random', 'books':BookSerializer(with_card_data(books),many=True).data})
        response['Cache-Control'] = 'no-store'
        return response


class HomepageSelection(APIView):
    permission_classes = [IsCreator]

    def get(self, request):
        return Response({'selected_count':Book.objects.filter(homepage_selected=True,needs_review=False).count()})

    @transaction.atomic
    def patch(self, request):
        lock_catalog()
        book_id=serializers.IntegerField(min_value=1).run_validation(request.data.get('book_id'))
        selected=serializers.BooleanField().run_validation(request.data.get('selected'))
        book=get_object_or_404(Book.objects.select_for_update(),pk=book_id)
        if selected and book.needs_review:
            raise serializers.ValidationError('ابتدا بازبینی این کتاب را تکمیل کنید.')
        book.homepage_selected=selected
        book.save(update_fields=['homepage_selected','updated_at'])
        return Response({'selected':selected})

    @transaction.atomic
    def delete(self, request):
        lock_catalog()
        Book.objects.filter(homepage_selected=True).update(homepage_selected=False,updated_at=timezone.now())
        return Response({'selected_count':0})
