from django.db import models

from core.models import TimeStampedModel


class Person(TimeStampedModel):
    """
    A real human who can be credited as an author, translator, illustrator,
    etc. One row per person, reused across every book/edition they're
    credited on -- never duplicated just because they play different roles
    in different places.
    """
    name = models.CharField(max_length=300, db_index=True)

    def __str__(self):
        return self.name


class Book(TimeStampedModel):
    """
    The abstract work -- title, category. Deliberately does NOT hold
    publisher, translator, cover, ISBN, or price: those vary per printing
    and live on Edition instead, since two publishers of the same title can
    have different covers and different translators.
    """

    class Source(models.TextChoices):
        MANUAL = "manual", "Manually entered"
        PUBLISHER_IMPORT = "publisher_import", "Publisher Excel/CSV import"

    class ContributionRole(models.TextChoices):
        AUTHOR = "author", "Author"
        ILLUSTRATOR = "illustrator", "Illustrator"
        EDITOR = "editor", "Editor"

    class DiscountType(models.TextChoices):
        NONE = "none", "None"
        PERCENTAGE = "percentage", "Percentage"
        FIXED_AMOUNT = "fixed_amount", "Fixed amount"

    title = models.CharField(max_length=500, db_index=True)
    category = models.CharField(max_length=200, blank=True)      # main category, from the source file
    subcategory = models.CharField(max_length=200, blank=True)   # subcategory -- also carries age-group values (e.g. children's, young-adult)
    description = models.TextField(blank=True)

    contributors = models.ManyToManyField(Person, through="BookContribution", related_name="books")

    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    needs_review = models.BooleanField(default=False)
    homepage_selected = models.BooleanField(default=False)
    import_locked_fields = models.JSONField(default=list, blank=True)

    # book-level automatic markdown -- applies across all editions unless a
    # specific edition/stock item overrides it with its own price
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices, default=DiscountType.NONE)
    discount_value = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    discount_active = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["title"]), models.Index(fields=["category", "subcategory"])]

    def __str__(self):
        return self.title

    @property
    def is_available(self):
        """Books are sourced from active publisher editions."""
        if hasattr(self, "_card_editions"):
            return bool(self._card_editions)
        return self.editions.filter(is_active=True).exists()

    def apply_discount(self, base_price):
        if base_price is None or not self.discount_active:
            return base_price
        if self.discount_type == self.DiscountType.PERCENTAGE:
            return base_price - (base_price * self.discount_value / 100)
        if self.discount_type == self.DiscountType.FIXED_AMOUNT:
            return max(base_price - self.discount_value, 0)
        return base_price


class BookContribution(TimeStampedModel):
    """Book-level credits (author, illustrator, ...) -- same across every
    edition/publisher, unlike translator which is edition-specific."""
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="book_contributions")
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="book_contributions")
    role = models.CharField(max_length=20, choices=Book.ContributionRole.choices, default=Book.ContributionRole.AUTHOR)

    class Meta:
        unique_together = ("book", "person", "role")


class FeaturedBook(TimeStampedModel):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="featured_entries")
    caption = models.TextField()
    cover_override = models.ImageField(upload_to="featured_covers/", blank=True, null=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "-created_at"]


class BookPost(TimeStampedModel):
    title = models.CharField(max_length=200)
    body = models.TextField()
    books = models.ManyToManyField(Book, blank=True, related_name="introduction_posts")
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at", "-pk"]


class BookPostImage(TimeStampedModel):
    post = models.ForeignKey(BookPost, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="book_posts/")
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "pk"]
