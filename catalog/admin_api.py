from django.db import transaction
from django.db.models import Q, Count
from rest_framework import serializers, generics
from rest_framework.pagination import PageNumberPagination
from core.permissions import IsCreator
from publisher_catalog.models import Publisher, Edition
from publisher_catalog.serializers import EditionUpdateSerializer
from .models import Book, BookContribution, Person
from .serializers import BookUpdateSerializer
from .locking import lock_catalog


class AdminPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminEditionSerializer(EditionUpdateSerializer):
    publisher_name = serializers.CharField(source="publisher.name", read_only=True)
    translators = serializers.SerializerMethodField()
    cover = serializers.CharField(source="display_cover", read_only=True, allow_null=True)
    class Meta(EditionUpdateSerializer.Meta):
        fields = ["id", "book", "publisher", "publisher_name", "translators", "cover", "import_locked_fields", "price_review_note"] + EditionUpdateSerializer.Meta.fields
        read_only_fields = ["id", "book", "publisher", "import_locked_fields", "price_review_note"]

    def get_translators(self, obj):
        return list(obj.edition_contributions.filter(role="translator").values_list("person__name", flat=True))


class AdminBookSerializer(serializers.ModelSerializer):
    authors = serializers.SerializerMethodField()
    edition_count = serializers.IntegerField(read_only=True)
    editions = AdminEditionSerializer(many=True, read_only=True)
    class Meta:
        model = Book
        fields = ["id", "title", "authors", "category", "subcategory", "description", "needs_review", "homepage_selected", "import_locked_fields", "edition_count", "editions", "updated_at"]

    def get_authors(self, obj):
        return [credit.person.name for credit in obj.book_contributions.all() if credit.role == "author"]


class AdminBookList(generics.ListCreateAPIView):
    permission_classes = [IsCreator]
    pagination_class = AdminPagination

    def get_serializer_class(self):
        return BookCreateSerializer if self.request.method == "POST" else AdminBookSerializer

    def get_queryset(self):
        qs = Book.objects.all()
        query = self.request.query_params.get("q", "").strip()[:200]
        if query:
            qs = qs.filter(Q(title__icontains=query) | Q(book_contributions__person__name__icontains=query) | Q(editions__isbn__icontains=query)).distinct()
        publisher = self.request.query_params.get("publisher_id")
        if publisher:
            if not publisher.isdecimal():
                raise serializers.ValidationError("ناشر معتبر نیست.")
            qs = qs.filter(editions__publisher_id=publisher).distinct()
        if self.request.query_params.get("homepage_only") == "true":
            qs = qs.filter(homepage_selected=True)
        review = self.request.query_params.get("needs_review")
        if review in {"true", "false"}:
            qs = qs.filter(needs_review=review == "true")
        return qs.annotate(edition_count=Count("editions", distinct=True)).prefetch_related("book_contributions__person", "editions__publisher", "editions__edition_contributions__person").order_by("title", "pk")


class BookCreateSerializer(BookUpdateSerializer):
    class Meta(BookUpdateSerializer.Meta):
        fields = ["id"] + BookUpdateSerializer.Meta.fields
        read_only_fields = ["id"]
        extra_kwargs = {"title": {"required": True}}

    @transaction.atomic
    def create(self, validated_data):
        lock_catalog()
        authors = validated_data.pop("authors", [])
        book = Book.objects.create(**validated_data, import_locked_fields=["title", "authors", "description", "category", "subcategory"])
        for name in dict.fromkeys(authors):
            person = Person.objects.filter(name=name).first() or Person.objects.create(name=name)
            BookContribution.objects.create(book=book, person=person)
        return book


class AdminBookDetail(generics.RetrieveAPIView):
    permission_classes = [IsCreator]
    serializer_class = AdminBookSerializer
    queryset = Book.objects.prefetch_related("book_contributions__person", "editions__publisher", "editions__edition_contributions__person")


class EditionCreateSerializer(EditionUpdateSerializer):
    price = serializers.DecimalField(max_digits=12, decimal_places=0, min_value=0)
    book = serializers.PrimaryKeyRelatedField(queryset=Book.objects.all())
    publisher = serializers.PrimaryKeyRelatedField(queryset=Publisher.objects.all())
    class Meta(EditionUpdateSerializer.Meta):
        fields = ["id", "book", "publisher"] + EditionUpdateSerializer.Meta.fields
        read_only_fields = ["id"]
        extra_kwargs = {"price": {"required": True}}
        validators = [serializers.UniqueTogetherValidator(queryset=Edition.objects.all(), fields=["book", "publisher"], message="این ناشر برای این کتاب از قبل نسخه دارد؛ همان نسخه را ویرایش کنید.")]

    @transaction.atomic
    def create(self, validated_data):
        lock_catalog()
        validated_data.pop("clear_cover", None)
        translators = validated_data.pop("translator_names", None)
        instance = super().create(validated_data)
        if translators is not None:
            self.set_translators(instance, translators)
        instance.import_locked_fields = sorted(set(validated_data) - {"price", "is_active", "book", "publisher"} | ({"translator"} if translators is not None else set()))
        instance.save()
        return instance


class AdminEditionCreate(generics.CreateAPIView):
    permission_classes = [IsCreator]
    serializer_class = EditionCreateSerializer
