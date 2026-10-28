from django.db import transaction
from rest_framework import serializers, generics
from rest_framework.permissions import AllowAny
from core.permissions import IsCreator
from .models import Book, BookPost, BookPostImage


class PostImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookPostImage
        fields = ["id", "image"]


class PostSerializer(serializers.ModelSerializer):
    images = PostImageSerializer(many=True, read_only=True)
    books = serializers.SerializerMethodField()
    class Meta:
        model = BookPost
        fields = ["id", "title", "body", "books", "images", "is_published", "created_at"]

    def get_books(self, obj):
        return list(obj.books.values("id", "title"))


class PostWriteSerializer(PostSerializer):
    book_ids = serializers.JSONField(write_only=True, required=False)
    uploads = serializers.ListField(child=serializers.ImageField(), write_only=True, required=False, max_length=10)
    keep_image_ids = serializers.JSONField(write_only=True, required=False)

    class Meta(PostSerializer.Meta):
        fields = PostSerializer.Meta.fields + ["book_ids", "uploads", "keep_image_ids"]

    def validate(self, attrs):
        if "book_ids" in attrs:
            ids = attrs.pop("book_ids")
            if not isinstance(ids, list) or any(type(pk) is not int for pk in ids) or len(ids) > 50:
                raise serializers.ValidationError({"book_ids": "فهرست کتاب‌ها معتبر نیست."})
            books = list(Book.objects.filter(pk__in=ids, needs_review=False))
            if len(books) != len(set(ids)):
                raise serializers.ValidationError({"book_ids": "یکی از کتاب‌ها در فهرست عمومی وجود ندارد."})
            attrs["books"] = books
        if "keep_image_ids" in attrs and (not isinstance(attrs["keep_image_ids"], list) or any(type(pk) is not int for pk in attrs["keep_image_ids"])):
            raise serializers.ValidationError({"keep_image_ids": "فهرست تصاویر معتبر نیست."})
        uploads = attrs.get("uploads", [])
        for image in uploads:
            if image.size > 5 * 1024 * 1024 or image.image.format not in {"JPEG", "PNG", "WEBP"}:
                raise serializers.ValidationError({"uploads": "تصویر باید PNG، JPG یا WebP و حداکثر ۵ مگابایت باشد."})
        existing = set(self.instance.images.values_list("id", flat=True)) if self.instance else set()
        keep = set(attrs.get("keep_image_ids", existing))
        if not keep.issubset(existing):
            raise serializers.ValidationError({"keep_image_ids": "تصویر انتخاب‌شده متعلق به این نوشته نیست."})
        count = len(keep) + len(uploads)
        if count > 10:
            raise serializers.ValidationError({"uploads": "هر نوشته حداکثر ۱۰ تصویر دارد."})
        if attrs.get("is_published", getattr(self.instance, "is_published", False)) and not count:
            raise serializers.ValidationError({"uploads": "برای انتشار، دست‌کم یک تصویر اضافه کنید."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        uploads = validated_data.pop("uploads", [])
        validated_data.pop("keep_image_ids", None)
        post = super().create(validated_data)
        for index, image in enumerate(uploads):
            BookPostImage.objects.create(post=post, image=image, display_order=index)
        return post

    @transaction.atomic
    def update(self, instance, validated_data):
        uploads = validated_data.pop("uploads", [])
        keep = validated_data.pop("keep_image_ids", None)
        post = super().update(instance, validated_data)
        if keep is not None:
            for image in post.images.exclude(pk__in=keep):
                storage, name = image.image.storage, image.image.name
                image.delete()
                transaction.on_commit(lambda storage=storage, name=name: storage.delete(name))
        start = max(post.images.values_list("display_order", flat=True), default=-1) + 1
        for index, image in enumerate(uploads, start):
            BookPostImage.objects.create(post=post, image=image, display_order=index)
        return post


class PublicPostList(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PostSerializer
    queryset = BookPost.objects.filter(is_published=True).prefetch_related("images", "books")


class AdminPostList(generics.ListCreateAPIView):
    permission_classes = [IsCreator]
    serializer_class = PostWriteSerializer
    queryset = BookPost.objects.all().prefetch_related("images", "books")


class AdminPostDetail(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsCreator]
    serializer_class = PostWriteSerializer
    queryset = BookPost.objects.all().prefetch_related("images", "books")

    @transaction.atomic
    def perform_destroy(self, instance):
        images = [(image.image.storage, image.image.name) for image in instance.images.all()]
        instance.delete()
        for storage, name in images:
            transaction.on_commit(lambda storage=storage, name=name: storage.delete(name))
