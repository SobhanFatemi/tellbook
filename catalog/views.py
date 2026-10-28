from django.db.models import Min, Max, Q, Case, When, Value, IntegerField
from rest_framework.pagination import PageNumberPagination
from rest_framework import serializers
from .search import normalized_field, normalized_text
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import ListAPIView, RetrieveAPIView, UpdateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsCreator
from publisher_catalog.models import Edition, Publisher
from .models import Book, FeaturedBook
from .serializers import BookDetailSerializer, BookSerializer, BookSuggestionSerializer, BookUpdateSerializer, FeaturedBookSerializer
from .services import suggest_similar_books
from .querysets import with_card_data


class CatalogPagination(PageNumberPagination):
    page_size = 24


class SearchParameters(serializers.Serializer):
    publisher_id = serializers.IntegerField(min_value=1, required=False)
    min_price = serializers.IntegerField(min_value=0, required=False)
    max_price = serializers.IntegerField(min_value=0, required=False)
    print_year = serializers.IntegerField(min_value=1, max_value=9999, required=False)

    def validate(self, attrs):
        if attrs.get('min_price', 0) > attrs.get('max_price', float('inf')):
            raise serializers.ValidationError('حداقل قیمت نباید بیشتر از حداکثر باشد.')
        return attrs


@extend_schema(
    parameters=[
        OpenApiParameter("q", str, description="Title/author text search"),
        OpenApiParameter("category", str, description="Exact match on Book.category"),
        OpenApiParameter("subcategory", str, description="Exact match on Book.subcategory"),
        OpenApiParameter("publisher_id", int, description="Only books with an active edition from this publisher"),
        OpenApiParameter("min_price", int, description="Minimum price across active editions"),
        OpenApiParameter("max_price", int, description="Maximum price across active editions"),
        OpenApiParameter("print_year", int, description="Filter by an active edition's print year"),
    ]
)
class BookSearchView(ListAPIView):
    """
    Database-only search (no external API calls) with filtering support:
      q            -- title/author text search
      category     -- exact match on Book.category
      subcategory  -- exact match on Book.subcategory (also where age-group values like children's/young-adult live)
      publisher_id -- only books with an active edition from this publisher
      min_price / max_price -- filters against any active edition's price
      print_year   -- filters against any active edition's print year
    """
    serializer_class = BookSerializer
    pagination_class = CatalogPagination
    permission_classes = [AllowAny]

    def get_queryset(self):
        params = self.request.query_params
        validated = SearchParameters(data={key: value for key, value in params.items() if value != ''})
        validated.is_valid(raise_exception=True)
        numeric = validated.validated_data
        qs = Book.objects.filter(needs_review=False)

        query = params.get("q", "").strip()
        ordering = ['title', 'pk']
        if query:
            qs = qs.alias(search_title=normalized_field('title'), search_author=normalized_field('book_contributions__person__name'))
            for token in query.split():
                token = normalized_text(token)
                if token:
                    qs = qs.filter(Q(search_title__contains=token) | Q(search_author__contains=token))
            text = normalized_text(query)
            qs = qs.annotate(search_rank=Case(When(search_title=text, then=Value(0)), When(search_title__startswith=text, then=Value(1)), default=Value(2), output_field=IntegerField())).distinct()
            ordering = ['search_rank', 'title', 'pk']

        category = params.get("category")
        if category:
            from .categories import normalize_category
            qs = qs.filter(category=normalize_category(category))

        subcategory = params.get("subcategory")
        if subcategory:
            from .categories import normalize_category
            qs = qs.filter(subcategory=normalize_category(subcategory))

        edition_filters = {}
        publisher_id = numeric.get("publisher_id")
        if publisher_id:
            edition_filters["publisher_id"] = publisher_id

        min_price = numeric.get("min_price")
        if min_price is not None:
            edition_filters["price__gte"] = min_price

        max_price = numeric.get("max_price")
        if max_price is not None:
            edition_filters["price__lte"] = max_price

        print_year = numeric.get("print_year")
        if print_year:
            edition_filters["print_year"] = print_year

        if edition_filters:
            edition_filters["is_active"] = True
            matching_book_ids = Edition.objects.filter(**edition_filters).values_list("book_id", flat=True)
            qs = qs.filter(id__in=matching_book_ids)

        return with_card_data(qs.order_by(*ordering))


class BookDetailView(RetrieveAPIView):
    """Full book page -- every active edition, so a buyer can choose publisher/translator/cover."""
    serializer_class = BookDetailSerializer
    permission_classes = [AllowAny]
    queryset = Book.objects.all()


class BookUpdateView(UpdateAPIView):
    """Staff-only edit -- title, category, description, and clearing needs_review
    once a human has confirmed a match/mismatch from the review queue."""
    serializer_class = BookUpdateSerializer
    permission_classes = [IsCreator]
    queryset = Book.objects.all()


class BookSearchFilterOptionsView(APIView):
    """
    Public: the distinct values worth offering as search filters. Category
    and subcategory are free-text and exact-matched in BookSearchView, so
    without this a buyer has no way to know what to type -- and
    PublisherListCreateView is creator-only, so it can't back a buyer-facing
    dropdown either.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        visible_books = Book.objects.filter(needs_review=False)
        categories = visible_books.exclude(category="").values_list("category", flat=True).distinct().order_by("category")
        subcategories = visible_books.exclude(subcategory="").values_list("subcategory", flat=True).distinct().order_by("subcategory")
        publishers = Publisher.objects.filter(editions__is_active=True).distinct().order_by("name").values("id", "name")
        price_bounds = Edition.objects.filter(is_active=True, book__needs_review=False, price__gte=0).aggregate(min_price=Min("price"), max_price=Max("price"))
        return Response({
            "price_bounds": {key: int(value) if value is not None else None for key, value in price_bounds.items()},
            "categories": list(categories),
            "subcategories": list(subcategories),
            "publishers": list(publishers),
        })


class FeaturedBookListView(ListAPIView):
    serializer_class = FeaturedBookSerializer
    permission_classes = [AllowAny]
    queryset = FeaturedBook.objects.filter(is_active=True)


@extend_schema(parameters=[OpenApiParameter("q", str, description="Partial/misspelled title to match against")])
class BookSuggestView(APIView):
    """
    "Did you mean...?" -- used by the book-request form as the buyer types a
    title, so a book that's already in the catalog gets linked directly
    instead of buyer entering a duplicate blind request for it.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get("q", "")
        matches = suggest_similar_books(query, limit=3)
        data = [
            {
                "id": book.id,
                "title": book.title,
                "authors": [bc.person.name for bc in book.book_contributions.filter(role="author")],
                "score": score,
            }
            for book, score in matches
        ]
        return Response(BookSuggestionSerializer(data, many=True).data)
