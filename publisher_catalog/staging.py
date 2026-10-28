"""Preview and commit are separate transactions. Only confirmed batches write catalog data."""
import hashlib
import json
from types import SimpleNamespace
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rapidfuzz import process, fuzz
from rest_framework.exceptions import ValidationError
from catalog.locking import lock_catalog
from catalog.models import Book
from .models import Publisher, Edition, PublisherImportBatch as Batch, PublisherImportRow as Row
from .parsing import read_publisher_rows
from .services import normalize_persian, clean_title_and_extract_author, set_book_author, set_edition_translator

BOOK_FIELDS = ["title", "category", "subcategory", "description"]
EDITION_FIELDS = ["isbn", "national_barcode", "sku", "cover_type", "print_year", "page_count", "volume_count", "print_run", "weight", "cost_price"]


def fingerprint():
    payload = []
    for model in [Book, Edition, Publisher]:
        payload.append(list(model.objects.order_by("pk").values_list("pk", "updated_at")))
    return hashlib.sha256(json.dumps(payload, default=str).encode()).hexdigest()


def normalize_identifier(value):
    return str(value or "").removesuffix(".0").replace("-", "").replace(" ", "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def before_values(book, edition):
    return {"title": book.title, "authors": list(book.book_contributions.filter(role="author").values_list("person__name", flat=True)), "price": str(edition.price) if edition else None, "is_active": edition.is_active if edition else None, "edition_id": edition.pk if edition else None, "protected_fields": sorted(set(book.import_locked_fields) | (set(edition.import_locked_fields) if edition else set()))} if book else {}


def refresh_deactivations(batch):
    if not batch.complete_catalog:
        batch.deactivations = []
        return
    publisher_names = set()
    represented = set()
    for row in batch.rows.all():
        name = row.data.get("publisher_name", "")
        publisher_names.add(normalize_persian(name))
        if row.book_id:
            represented.add((row.book_id, normalize_persian(name)))
    # A fixed publisher is authoritative even when a file is empty (apply rejects empty).
    if batch.profile_snapshot.get("publisher_name"):
        publisher_names.add(normalize_persian(batch.profile_snapshot["publisher_name"]))
    batch.deactivations = [{"id": edition.pk, "title": edition.book.title, "publisher": edition.publisher.name, "price": str(edition.price)} for edition in Edition.objects.filter(is_active=True).select_related("book", "publisher") if normalize_persian(edition.publisher.name) in publisher_names and (edition.book_id, normalize_persian(edition.publisher.name)) not in represented]


def prepare_batch(batch_id):
    batch = Batch.objects.get(pk=batch_id)
    snapshot = batch.profile_snapshot
    with batch.file.open("rb") as source:
        rows, invalid = read_publisher_rows(source, SimpleNamespace(**snapshot), include_invalid=True)
    with transaction.atomic():
        lock_catalog()
        batch = Batch.objects.select_for_update().get(pk=batch_id)
        if batch.status != Batch.Status.PROCESSING:
            return
        books = list(Book.objects.prefetch_related("book_contributions__person"))
        titles = {book.pk: normalize_persian(book.title) for book in books}
        by_id = {book.pk: book for book in books}
        exact_titles = {}
        for book in books:
            exact_titles.setdefault(normalize_persian(book.title), []).append(book)
        editions = list(Edition.objects.select_related("publisher", "book"))
        edition_map = {(edition.book_id, normalize_persian(edition.publisher.name)): edition for edition in editions}
        identifiers = {}
        for edition in editions:
            pub = normalize_persian(edition.publisher.name)
            for key in ["isbn", "sku"]:
                if getattr(edition, key):
                    identifiers.setdefault((pub, key, normalize_identifier(getattr(edition, key))), set()).add(edition.book_id)
        planned = []
        for raw in rows:
            data = dict(raw)
            publisher_name = snapshot.get("publisher_name") if snapshot["mode"] == "single" else data.get("publisher_name", "")
            data["publisher_name"] = publisher_name or ""
            data["raw_title"] = data.get("title") or ""
            title, author = clean_title_and_extract_author(data.get("title") or "", publisher_hint=publisher_name or "", known_author=data.get("author") or "")
            data.update(title=title, author=author)
            error = data.pop("error", "")
            if not title or not publisher_name:
                error = error or "عنوان کتاب یا نام ناشر خالی است."
            book, candidates = None, []
            decision = "skip" if error else "new"
            if not error:
                matches = set()
                for key in ["isbn", "sku"]:
                    if data.get(key):
                        matches |= identifiers.get((normalize_persian(publisher_name), key, normalize_identifier(data[key])), set())
                exact = exact_titles.get(normalize_persian(title), [])
                if len(matches) == 1:
                    book = by_id[next(iter(matches))]
                    decision = "match"
                elif not matches and len(exact) == 1:
                    known = [normalize_persian(c.person.name) for c in exact[0].book_contributions.all() if c.role == "author"]
                    if not author or not known or normalize_persian(author) in known:
                        book, decision = exact[0], "match"
                if book is None:
                    suggestions = process.extract(normalize_persian(title), titles, scorer=fuzz.token_set_ratio, limit=5, score_cutoff=80)
                    numbers = set(__import__('re').findall(r'\d+', normalize_identifier(title)))
                    for _, score, pk in suggestions:
                        other_numbers = set(__import__('re').findall(r'\d+', normalize_identifier(by_id[pk].title)))
                        if numbers and other_numbers and numbers != other_numbers:
                            continue
                        candidates.append({"id": pk, "title": by_id[pk].title, "authors": [c.person.name for c in by_id[pk].book_contributions.all() if c.role == "author"], "score": round(score)})
                    if candidates or matches or exact:
                        decision = "pending"
            before = before_values(book, edition_map.get((book.pk, normalize_persian(publisher_name)))) if book else {}
            planned.append(Row(batch=batch, row_number=data["source_row"], data=data, decision=decision, book=book, before=before, candidates=candidates, error=error))
        batch.rows.all().delete()
        Row.objects.bulk_create(planned, batch_size=1000)
        batch.total_rows = len(planned)
        batch.skipped_rows = invalid
        batch.needs_review_rows = sum(row.decision == "pending" for row in planned)
        batch.processed_rows = 0
        batch.catalog_fingerprint = fingerprint()
        batch.error_message = ""
        batch.status = Batch.Status.REVIEW
        batch.revision += 1
        refresh_deactivations(batch)
        batch.save()


def validate_ready(batch):
    if batch.status != Batch.Status.REVIEW:
        raise ValidationError("این فایل اکنون آماده تأیید نیست.")
    if not batch.rows.exclude(decision="skip").exists():
        raise ValidationError("هیچ ردیف قابل اعمالی انتخاب نشده است.")
    if batch.rows.filter(decision="pending").exists():
        raise ValidationError("ابتدا ردیف‌های نیازمند تصمیم را بررسی کنید.")
    if batch.complete_catalog and batch.rows.exclude(error="").exists():
        raise ValidationError("فایل کامل ردیف نامعتبر دارد؛ آن را اصلاح کنید یا به‌صورت به‌روزرسانی وارد کنید تا کتابی اشتباهی غیرفعال نشود.")
    if fingerprint() != batch.catalog_fingerprint:
        raise ValidationError("فهرست از زمان پیش‌نمایش تغییر کرده است؛ پیش‌نمایش را دوباره بسازید.")
    targets = set()
    for row in batch.rows.exclude(decision="skip"):
        key = (normalize_persian(row.data["publisher_name"]), row.book_id if row.decision == "match" else (normalize_persian(row.data["title"]), normalize_persian(row.data.get("author") or "")))
        if key in targets:
            raise ValidationError("دو ردیف برای یک کتاب و ناشر انتخاب شده‌اند؛ یکی را کنار بگذارید.")
        targets.add(key)


def apply_batch(batch_id):
    with transaction.atomic():
        lock_catalog()
        batch = Batch.objects.select_for_update().get(pk=batch_id)
        if batch.status != Batch.Status.APPLYING:
            return
        batch.status = Batch.Status.REVIEW  # validate immutable staged state under the same lock
        validate_ready(batch)
        publishers = {normalize_persian(pub.name): pub for pub in Publisher.objects.all()}
        created_books, count, new_count = {}, 0, 0
        for row in batch.rows.exclude(decision="skip").select_related("book"):
            data = row.data
            pub_key = normalize_persian(data["publisher_name"])
            publisher = publishers.get(pub_key)
            if publisher is None:
                publisher = Publisher.objects.create(name=data["publisher_name"])
                publishers[pub_key] = publisher
            book = row.book
            if row.decision == "new":
                new_key = (normalize_persian(data["title"]), normalize_persian(data.get("author") or ""))
                book = created_books.get(new_key)
                if book is None:
                    book = Book.objects.create(title=data["title"], source=Book.Source.PUBLISHER_IMPORT)
                    created_books[new_key] = book
                    new_count += 1
            if book is None:
                raise ValidationError("کتاب انتخاب‌شده دیگر وجود ندارد؛ پیش‌نمایش را دوباره بسازید.")
            for field in BOOK_FIELDS:
                if data.get(field) and field not in book.import_locked_fields:
                    setattr(book, field, data[field])
            book.save()
            if data.get("author") and "authors" not in book.import_locked_fields:
                book.book_contributions.filter(role="author").delete()
                set_book_author(book, data["author"])
            edition, _ = Edition.objects.get_or_create(book=book, publisher=publisher, defaults={"price": Decimal(data["price"])})
            for field in EDITION_FIELDS:
                if data.get(field) is not None and data[field] != "" and field not in edition.import_locked_fields:
                    setattr(edition, field, data[field])
            edition.price = Decimal(data["price"])
            edition.price_review_note = ""
            edition.is_active = True
            edition.save()
            if data.get("translator") and "translator" not in edition.import_locked_fields:
                edition.edition_contributions.filter(role="translator").delete()
                set_edition_translator(edition, data["translator"])
            row.book = book
            row.save(update_fields=["book"])
            count += 1
        ids = [item["id"] for item in batch.deactivations]
        # Selection was explicitly previewed and approved; pending/invalid/changed batches cannot reach this point.
        batch.deactivated_rows = Edition.objects.filter(pk__in=ids).update(is_active=False, updated_at=timezone.now())
        batch.processed_rows = count
        batch.matched_rows = count - new_count
        batch.skipped_rows = batch.rows.filter(decision="skip").count()
        batch.needs_review_rows = 0
        batch.status = Batch.Status.DONE
        batch.applied_at = timezone.now()
        batch.save()
