from rest_framework import serializers

from publisher_catalog.serializers import EditionSerializer
from .models import Book, FeaturedBook


class BookUpdateSerializer(serializers.ModelSerializer):
    authors = serializers.ListField(child=serializers.CharField(max_length=300), required=False, write_only=True)

    def validate_category(self, value):
        from .categories import normalize_category
        return normalize_category(value)

    validate_subcategory = validate_category

    def update(self, instance, validated_data):
        from django.db import transaction
        from .models import Person, BookContribution
        protected = set(validated_data) - {"needs_review"}
        authors = validated_data.pop("authors", None)
        with transaction.atomic():
            from .locking import lock_catalog
            lock_catalog()
            instance = Book.objects.select_for_update().get(pk=instance.pk)
            instance.import_locked_fields = sorted(set(instance.import_locked_fields) | protected)
            instance = super().update(instance, validated_data)
            if authors is not None:
                instance.book_contributions.filter(role="author").delete()
                for name in dict.fromkeys(name.strip() for name in authors if name.strip()):
                    person = Person.objects.filter(name=name).first() or Person.objects.create(name=name)
                    BookContribution.objects.create(book=instance, person=person, role="author")
        return instance

    class Meta:
        model = Book
        fields = ["title", "category", "subcategory", "description", "needs_review", "authors"]
        extra_kwargs = {field: {"required": False} for field in fields}


class BookSerializer(serializers.ModelSerializer):
    authors = serializers.SerializerMethodField()
    translators = serializers.SerializerMethodField()
    credit_publisher = serializers.SerializerMethodField()
    price_info = serializers.SerializerMethodField()
    in_stock = serializers.SerializerMethodField()
    cover = serializers.SerializerMethodField()
    is_available = serializers.ReadOnlyField()

    class Meta:
        model = Book
        fields = [
            "id", "title", "authors", "translators", "credit_publisher", "category", "subcategory", "description",
            "price_info", "in_stock", "cover", "is_available", "needs_review",
        ]

    def get_authors(self, obj):
        return [bc.person.name for bc in (obj._card_authors if hasattr(obj, "_card_authors") else obj.book_contributions.filter(role="author").select_related("person"))]

    def preferred_edition(self, obj):
        if hasattr(obj, "_card_editions"):
            return next(iter(obj._card_editions), None)
        if not hasattr(obj, "_display_edition"):
            obj._display_edition = obj.editions.filter(is_active=True).select_related("publisher").order_by("price", "pk").first()
        return obj._display_edition

    def get_translators(self, obj):
        edition = self.preferred_edition(obj)
        if edition and hasattr(edition, "_card_translators"):
            return [item.person.name for item in edition._card_translators]
        return list(edition.edition_contributions.filter(role="translator").values_list("person__name", flat=True)) if edition else []

    def get_credit_publisher(self, obj):
        edition = self.preferred_edition(obj)
        return edition.publisher.name if edition else ""

    def get_price_info(self, obj):
        from .pricing import get_display_price
        info = get_display_price(obj)
        return {
            "price": info.price,
            "original_price": info.original_price,
            "source": info.source,   # "stock_override" | "stock" | "edition" | "none"
            "has_discount": info.has_discount,
        }

    def get_in_stock(self, obj):
        return False  # Compatibility field; pre-owned stock is no longer sold.

    def get_cover(self, obj):
        # Cheapest active edition's cover -- same ordering BookDetailSerializer
        # uses for its edition list, so the list-view thumbnail matches
        # whichever edition is shown/priced first on the detail page.
        # Mirrors EditionSerializer.get_cover exactly (obj.display_cover)
        # rather than reimplementing the override-vs-url fallback.
        edition = self.preferred_edition(obj)
        return edition.display_cover if edition else None


class BookDetailSerializer(BookSerializer):
    """Full detail view -- includes every active edition, not just the cheapest,
    so a buyer can pick a publisher/translator/cover explicitly."""
    editions = serializers.SerializerMethodField()

    class Meta(BookSerializer.Meta):
        fields = BookSerializer.Meta.fields + ["editions"]

    def get_editions(self, obj):
        return EditionSerializer(obj.editions.filter(is_active=True).order_by("price"), many=True).data


class FeaturedBookSerializer(serializers.ModelSerializer):
    book = BookSerializer(read_only=True)

    class Meta:
        model = FeaturedBook
        fields = ["id", "book", "caption", "cover_override", "display_order"]


class BookSuggestionSerializer(serializers.Serializer):
    """One "did you mean...?" candidate -- score is 0-100, not shown to the
    buyer, just used by the frontend to decide ordering/visibility."""
    id = serializers.IntegerField()
    title = serializers.CharField()
    authors = serializers.ListField(child=serializers.CharField())
    score = serializers.IntegerField()
