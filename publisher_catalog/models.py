from django.db import models

from catalog.models import Book, Person
from core.models import TimeStampedModel


class Publisher(TimeStampedModel):
    """A publisher. Each publisher's upload is scoped to just them --
    no separate 'ignored publisher' concept needed since a publisher's own
    file inherently only contains their own books."""
    name = models.CharField(max_length=300, unique=True, db_index=True)
    typical_lead_days = models.PositiveSmallIntegerField(default=5)

    def __str__(self):
        return self.name


class Edition(TimeStampedModel):
    """
    One specific printing of a Book by one Publisher. Cover, translator,
    ISBN, and price all live here rather than on Book, since two publishers
    of the same title can genuinely differ on every one of these.
    """

    class ContributionRole(models.TextChoices):
        TRANSLATOR = "translator", "Translator"
        EDITOR = "editor", "Editor"

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="editions")
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE, related_name="editions")

    contributors = models.ManyToManyField(Person, through="EditionContribution", related_name="editions")

    isbn = models.CharField(max_length=20, blank=True, db_index=True)
    national_barcode = models.CharField(max_length=30, blank=True)
    sku = models.CharField(max_length=100, blank=True)  # publisher's own item code

    cover_image_url = models.URLField(blank=True, null=True)
    cover_image_override = models.ImageField(upload_to="edition_covers/", blank=True, null=True)

    price = models.DecimalField(max_digits=12, decimal_places=0)
    cost_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)  # her cost, internal only

    cover_type = models.CharField(max_length=100, blank=True)   # e.g. paperback, hardcover
    print_year = models.PositiveIntegerField(null=True, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    volume_count = models.PositiveIntegerField(null=True, blank=True)  # how many physical volumes this edition spans
    print_run = models.PositiveIntegerField(null=True, blank=True)  # which printing/run number
    weight = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)

    is_active = models.BooleanField(default=True)  # no exact quantity tracked -- just available-or-not
    last_synced_at = models.DateTimeField(auto_now=True)
    import_locked_fields = models.JSONField(default=list, blank=True)
    price_review_note = models.TextField(blank=True)

    @property
    def display_cover(self):
        return self.cover_image_override.url if self.cover_image_override else self.cover_image_url

    class Meta:
        unique_together = ("book", "publisher")
        indexes = [models.Index(fields=["isbn"]), models.Index(fields=["is_active"])]


class EditionContribution(TimeStampedModel):
    """Edition-level credits (translator, ...) -- varies per printing,
    unlike author which stays on Book since it's the same across editions."""
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE, related_name="edition_contributions")
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="edition_contributions")
    role = models.CharField(max_length=20, choices=Edition.ContributionRole.choices, default=Edition.ContributionRole.TRANSLATOR)

    class Meta:
        unique_together = ("edition", "person", "role")


class PublisherImportProfile(TimeStampedModel):
    """
    Saved column mapping for a publisher's spreadsheet, set once, reused on
    every future upload -- this is what lets one generic importer handle
    every publisher's different file format without a new parser each time.

    mode="single": every row in the file belongs to THIS profile's publisher
      (a normal single-publisher export -- one publisher, no publisher column needed
      in the mapping, though one may still be present and ignored).
    mode="multi": the file itself contains many publishers (a rich distributor-
      style export) -- column_mapping MUST include a "publisher" entry, and
      each row's own value decides which Publisher it belongs to.
    """

    class Mode(models.TextChoices):
        SINGLE = "single", "Single publisher"
        MULTI = "multi", "Multi-publisher file"

    publisher = models.ForeignKey(
        Publisher, on_delete=models.CASCADE, related_name="import_profiles",
        null=True, blank=True, help_text="Required for mode=single. Ignored for mode=multi.",
    )
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.SINGLE)
    price_unit = models.CharField(max_length=7, choices=[("unknown", "Unconfirmed"), ("toman", "Toman"), ("rial", "Rial")], default="unknown")
    column_mapping = models.JSONField()
    header_row_index = models.PositiveSmallIntegerField(default=0)
    sheet_name = models.CharField(max_length=100, blank=True, null=True)
    label = models.CharField(max_length=200, blank=True, help_text="e.g. 'Publisher X full catalog export'")


class PublisherImportBatch(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        REVIEW = "review", "Awaiting review"
        APPLYING = "applying", "Applying approved changes"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    profile = models.ForeignKey(PublisherImportProfile, on_delete=models.SET_NULL, null=True, related_name="batches")
    publisher = models.ForeignKey(
        Publisher, on_delete=models.SET_NULL, null=True, blank=True, related_name="import_batches",
        help_text="Null for multi-publisher batches -- see per-row results instead.",
    )
    file = models.FileField(upload_to="publisher_imports/")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    total_rows = models.PositiveIntegerField(default=0)
    processed_rows = models.PositiveIntegerField(default=0)
    matched_rows = models.PositiveIntegerField(default=0)
    needs_review_rows = models.PositiveIntegerField(default=0)
    skipped_rows = models.PositiveIntegerField(default=0)
    deactivated_rows = models.PositiveIntegerField(default=0)
    profile_snapshot = models.JSONField(default=dict)
    complete_catalog = models.BooleanField(default=False)
    catalog_fingerprint = models.CharField(max_length=64, blank=True)
    deactivations = models.JSONField(default=list)
    error_message = models.TextField(blank=True)
    revision = models.PositiveIntegerField(default=0)
    applied_at = models.DateTimeField(null=True, blank=True)



class PublisherImportRow(models.Model):
    batch = models.ForeignKey(PublisherImportBatch, on_delete=models.CASCADE, related_name="rows")
    row_number = models.PositiveIntegerField()
    data = models.JSONField(default=dict)
    decision = models.CharField(max_length=12, choices=[("pending", "Needs decision"), ("match", "Use existing book"), ("new", "Create book"), ("skip", "Skip")])
    book = models.ForeignKey(Book, on_delete=models.SET_NULL, null=True, blank=True)
    candidates = models.JSONField(default=list)
    before = models.JSONField(default=dict)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["row_number", "pk"]
        constraints = [models.UniqueConstraint(fields=["batch", "row_number"], name="import_batch_row_unique")]
