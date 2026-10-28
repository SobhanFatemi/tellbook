from rest_framework import serializers

from .models import Edition, Publisher, PublisherImportBatch, PublisherImportProfile


class EditionUpdateSerializer(serializers.ModelSerializer):
    clear_cover = serializers.BooleanField(write_only=True, required=False, default=False)
    translator_names = serializers.JSONField(write_only=True, required=False)
    price = serializers.DecimalField(max_digits=12, decimal_places=0, min_value=0, required=False)
    cost_price = serializers.DecimalField(max_digits=12, decimal_places=0, min_value=0, allow_null=True, required=False)

    def validate_translator_names(self, value):
        if not isinstance(value, list) or len(value) > 30 or any(not isinstance(name, str) or not name.strip() or len(name) > 300 for name in value):
            raise serializers.ValidationError("نام مترجم‌ها معتبر نیست.")
        return list(dict.fromkeys(name.strip() for name in value))

    def validate_cover_image_override(self, value):
        if value and (value.size > 5 * 1024 * 1024 or value.image.format not in {"PNG", "JPEG", "WEBP"}):
            raise serializers.ValidationError("تصویر جلد باید JPG، PNG یا WebP و حداکثر ۵ مگابایت باشد.")
        return value

    def set_translators(self, instance, names):
        from catalog.models import Person
        from .models import EditionContribution
        instance.edition_contributions.filter(role="translator").delete()
        for name in names:
            person = Person.objects.filter(name=name).first() or Person.objects.create(name=name)
            EditionContribution.objects.create(edition=instance, person=person, role="translator")

    def update(self, instance, validated_data):
        from django.db import transaction
        from catalog.locking import lock_catalog
        clear_cover = validated_data.pop("clear_cover", False)
        if clear_cover:
            validated_data["cover_image_override"] = None
        protected = set(validated_data) - {"price", "is_active", "translator_names"}
        names = validated_data.pop("translator_names", None)
        if names is not None:
            protected.add("translator")
        with transaction.atomic():
            lock_catalog()
            instance = Edition.objects.select_for_update().get(pk=instance.pk)
            instance.import_locked_fields = sorted(set(instance.import_locked_fields) | protected)
            if "price" in validated_data:
                instance.price_review_note = ""
            instance = super().update(instance, validated_data)
            if names is not None:
                self.set_translators(instance, names)
        return instance

    """Staff-editable fields -- cover is the main reason this exists, since
    none of the real supplier files contain cover images at all."""

    class Meta:
        model = Edition
        fields = [
            "clear_cover", "translator_names", "cover_image_url", "cover_image_override", "isbn", "national_barcode", "sku",
            "price", "cost_price", "cover_type", "print_year", "page_count",
            "volume_count", "print_run", "weight", "is_active",
        ]
        extra_kwargs = {field: {"required": False} for field in fields}


class PublisherSerializer(serializers.ModelSerializer):
    edition_count = serializers.SerializerMethodField()
    def get_edition_count(self, obj):
        return obj.editions.count()

    class Meta:
        model = Publisher
        fields = ["id", "name", "typical_lead_days", "edition_count"]


class PublisherImportProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublisherImportProfile
        fields = ["id", "publisher", "mode", "price_unit", "column_mapping", "header_row_index", "sheet_name", "label"]


class PublisherImportBatchSerializer(serializers.ModelSerializer):
    publisher_name = serializers.CharField(source="publisher.name", read_only=True, default="چند ناشر")
    profile_label = serializers.CharField(source="profile.label", read_only=True, default="")
    filename = serializers.SerializerMethodField()
    decision_counts = serializers.SerializerMethodField()
    def get_filename(self, obj):
        return obj.file.name.rsplit("/", 1)[-1]
    def get_decision_counts(self, obj):
        from django.db.models import Count
        return {item["decision"]: item["count"] for item in obj.rows.values("decision").annotate(count=Count("id"))}

    class Meta:
        model = PublisherImportBatch
        fields = [
            "id", "publisher", "publisher_name", "profile", "profile_label", "filename", "profile_snapshot", "complete_catalog", "catalog_fingerprint", "deactivations", "error_message", "revision", "applied_at", "decision_counts", "status", "total_rows", "processed_rows",
            "matched_rows", "needs_review_rows", "skipped_rows", "deactivated_rows", "created_at",
        ]
        read_only_fields = fields


class EditionSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()

    def get_price(self, obj):
        return obj.book.apply_discount(obj.price)

    publisher = PublisherSerializer(read_only=True)
    translator = serializers.SerializerMethodField()
    cover = serializers.SerializerMethodField()

    class Meta:
        model = Edition
        fields = [
            "id", "publisher", "translator", "cover", "price", "isbn", "cover_type",
            "print_year", "page_count", "volume_count", "print_run", "is_active",
        ]

    def get_translator(self, obj):
        names = [ec.person.name for ec in obj.edition_contributions.filter(role="translator")]
        return ", ".join(names) if names else None

    def get_cover(self, obj):
        return obj.display_cover


class PreviewColumnsRequestSerializer(serializers.Serializer):
    def validate_file(self, value):
        return UploadPublisherFileRequestSerializer().validate_file(value)

    file = serializers.FileField()
    sheet_name = serializers.CharField(required=False, allow_blank=True)
    header_row_index = serializers.IntegerField(required=False, default=0, min_value=0, max_value=500)


class SaveImportProfileRequestSerializer(serializers.Serializer):
    def validate(self, attrs):
        from .models import Publisher
        mapping = attrs.get("column_mapping", {})
        supported = {"title", "price", "author", "translator", "publisher_name", "isbn", "sku", "national_barcode", "category", "subcategory", "description", "cover_type", "print_year", "page_count", "volume_count", "print_run", "weight", "cost_price"}
        if not isinstance(mapping, dict) or not {"title", "price"} <= set(mapping) or any(key not in supported or not isinstance(value, str) or not value.strip() for key, value in mapping.items()):
            raise serializers.ValidationError("عنوان، قیمت و ستون‌های معتبر فایل را مشخص کنید.")
        if attrs.get("mode", "single") == "multi" and "publisher_name" not in mapping:
            raise serializers.ValidationError("برای فایل چندناشری، ستون ناشر را مشخص کنید.")
        if attrs.get("mode", "single") == "single" and not Publisher.objects.filter(pk=attrs.get("publisher_id")).exists():
            raise serializers.ValidationError("ناشر را انتخاب کنید.")
        return attrs

    price_unit = serializers.ChoiceField(choices=["toman", "rial"])
    mode = serializers.ChoiceField(choices=["single", "multi"], default="single")
    publisher_id = serializers.IntegerField(required=False, allow_null=True)
    column_mapping = serializers.JSONField(
        help_text='Maps canonical fields to this file\'s real column names, '
                   'e.g. {"title": "Book Name", "price": "Sale Price", "author": "Writer"}'
    )
    header_row_index = serializers.IntegerField(required=False, default=0, min_value=0, max_value=500)
    sheet_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    label = serializers.CharField(required=False, allow_blank=True, default="")


class UploadPublisherFileRequestSerializer(serializers.Serializer):
    price_unit = serializers.ChoiceField(choices=["rial", "toman"])
    file = serializers.FileField()
    complete_catalog = serializers.BooleanField(default=False)

    def validate_file(self, value):
        if value.size > 20 * 1024 * 1024 or not value.name.lower().endswith(".xlsx"):
            raise serializers.ValidationError("فایل اکسل xlsx با حداکثر ۲۰ مگابایت انتخاب کنید؛ فایل‌های قدیمی xls را ابتدا با قالب xlsx ذخیره کنید.")
        return value




class ImportPriceUnitSerializer(serializers.ModelSerializer):
    price_unit = serializers.ChoiceField(choices=["rial", "toman"])

    class Meta:
        model = PublisherImportProfile
        fields = ["id", "price_unit"]
        read_only_fields = ["id"]
