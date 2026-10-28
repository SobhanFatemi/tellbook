"""Batch the relations needed by public book cards without changing prices."""
from django.db.models import Prefetch
from publisher_catalog.models import Edition, EditionContribution
from .models import BookContribution


def with_card_data(queryset):
    return queryset.prefetch_related(
        Prefetch('book_contributions', queryset=BookContribution.objects.filter(role='author').select_related('person'), to_attr='_card_authors'),
        Prefetch('editions', queryset=Edition.objects.filter(is_active=True).select_related('publisher').order_by('price', 'pk').prefetch_related(
            Prefetch('edition_contributions', queryset=EditionContribution.objects.filter(role='translator').select_related('person'), to_attr='_card_translators')
        ), to_attr='_card_editions'),
    )
