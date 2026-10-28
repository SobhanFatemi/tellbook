"""
Publisher Excel/CSV sync logic.

Rules:
- Never hard-delete an Edition. A row missing from a new upload just means
  that publisher doesn't currently offer it -> deactivate that ONE edition.
- Book matching is title-only now (translator moved to Edition, so the old
  "translator conflict" false-merge risk is gone by construction -- two
  publishers of the same title always attach as two Editions under ONE Book).
- Author is essential -- extracted from a combined title string if the
  supplier didn't give a separate author column, never silently dropped.
- Translator lives on Edition (via EditionContribution), never on Book.
- No quantity tracking -- Edition.is_active is the only availability signal.
- Person/Publisher are matched by normalized name, reused rather than duplicated.
"""
import re

from django.utils import timezone
from rapidfuzz import fuzz

from catalog.models import Book, BookContribution, Person
from .models import Edition, EditionContribution, Publisher

HIGH_CONFIDENCE = 92  # auto-match, reuse the existing Book
LOW_CONFIDENCE = 80    # below this -> treat as a genuinely different/new book
# Tuned against a real 377-row file: LOW=60 flagged 89 books (24%) for review,
# most of them false positives from short titles sharing one common word
# (e.g. "باد ويرانگر" vs "ایرانی تر" scored 60 purely by coincidence). Raising
# to 80 cut that to 9, all genuinely ambiguous. Re-tune if real usage shows
# either too many false positives or too many missed real duplicates.
STALE_AFTER_DAYS = 30


def normalize_persian(text):
    """Collapse Arabic/Persian character variants and invisible formatting
    marks so two spellings of the same word compare equal. Used for
    COMPARISON only -- collapses the Arabic-style and Persian-style forms of
    the letters yeh and kaf, which would alter the actual spelling if applied
    to stored values."""
    if not text:
        return ""
    text = text.replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")  # Arabic yeh/kaf -> Persian yeh/kaf
    text = strip_invisible_marks(text)
    return text


def strip_invisible_marks(text):
    """Removes ZWNJ/LRM/RLM/ZWJ without changing letter spelling -- safe to
    apply to values that get STORED, not just compared. Real publisher files
    were found to have these trailing publisher/author names (e.g. a name
    stored with an invisible mark on the end), which would otherwise persist as
    garbage in the database."""
    if not text:
        return ""
    text = text.replace("\u200c", " ")
    text = text.replace("\u200e", "")
    text = text.replace("\u200f", "")
    text = text.replace("\u200d", "")
    return re.sub(r"\s+", " ", text).strip()


def clean_title_and_extract_author(raw_title, publisher_hint="", known_author=""):
    """
    Splits a combined 'Title/Author/Publisher'-style title string into a
    clean title and a best-guess author. Only guesses when no separate
    author column was given -- never overwrites a trusted known_author.
    """
    raw_title = strip_invisible_marks(raw_title)
    known_author = strip_invisible_marks(known_author)
    parts = [p.strip() for p in raw_title.split("/") if p.strip()]
    if not parts:
        return raw_title.strip(), known_author

    clean_title = parts[0]
    if known_author:
        return clean_title, known_author

    publisher_norm = normalize_persian(publisher_hint)
    guessed_author = ""
    for segment in parts[1:]:
        if normalize_persian(segment) == publisher_norm:
            continue
        guessed_author = strip_invisible_marks(segment)
        break
    return clean_title, guessed_author


def get_or_create_person(name):
    name = strip_invisible_marks(name)
    if not name:
        return None
    name_norm = normalize_persian(name)

    best_person, best_score = None, 0
    for person in Person.objects.all():
        score = fuzz.ratio(name_norm, normalize_persian(person.name))
        if score > best_score:
            best_person, best_score = person, score

    if best_score >= 92:  # names need a tighter threshold than titles -- less room for "superset" matches
        return best_person
    return Person.objects.create(name=name)


def get_or_create_publisher(name):
    name = strip_invisible_marks(name)
    if not name:
        return None
    name_norm = normalize_persian(name)

    for publisher in Publisher.objects.all():
        if normalize_persian(publisher.name) == name_norm:
            return publisher
    return Publisher.objects.create(name=name)


def find_matching_book(title):
    """
    Book matching is title-only -- author/translator differences never block
    a match here, since a Book is the abstract work, not one printing of it.
    Searches the WHOLE Book table.

    Numbered-series guard: titles like 'X4(Author A)' vs 'X7(Author B)' share
    almost every word except the number, which makes token_set_ratio score
    them as near-duplicates even though they are genuinely different books.
    If both titles contain digits and those digits differ, that candidate is
    skipped entirely rather than scored -- confirmed necessary against real
    data (a 20th-century-French-writers series volume set).
    """
    title_norm = normalize_persian(title)
    title_numbers = set(re.findall(r"\d+", title_norm))

    best_book, best_score = None, 0

    for book in Book.objects.all():
        book_title_norm = normalize_persian(book.title)
        book_numbers = set(re.findall(r"\d+", book_title_norm))

        if title_numbers and book_numbers and title_numbers != book_numbers:
            continue  # conflicting numbers -- different volume/edition, never a candidate

        score = fuzz.token_set_ratio(title_norm, book_title_norm)
        if score > best_score:
            best_book, best_score = book, score

    if best_score >= HIGH_CONFIDENCE:
        return best_book, "matched"
    elif best_score >= LOW_CONFIDENCE:
        return best_book, "needs_review"
    return None, "new"


def set_book_author(book, author_name):
    if normalize_persian(author_name) == "جورج اوورل":
        author_name = "جورج اورول"
    person = get_or_create_person(author_name)
    if not person:
        return
    BookContribution.objects.get_or_create(book=book, person=person, role=Book.ContributionRole.AUTHOR)


def set_edition_translator(edition, translator_name):
    person = get_or_create_person(translator_name)
    if not person:
        return
    EditionContribution.objects.get_or_create(edition=edition, person=person, role=Edition.ContributionRole.TRANSLATOR)


def apply_row_to_book(book, row):
    if row.get("title") and "title" not in book.import_locked_fields and book.title != row["title"]:
        book.title = row["title"]
    if row.get("category") and "category" not in book.import_locked_fields and book.category != row["category"]:
        book.category = row["category"]
    if row.get("subcategory") and "subcategory" not in book.import_locked_fields and book.subcategory != row["subcategory"]:
        book.subcategory = row["subcategory"]
    book.save()


def apply_row_to_edition(edition, row):
    for field in ("isbn", "national_barcode", "sku", "cover_type"):
        value = row.get(field)
        if value and field not in edition.import_locked_fields:
            setattr(edition, field, value)
    for field in ("print_year", "page_count", "volume_count", "print_run", "weight"):
        value = row.get(field)
        if value is not None and field not in edition.import_locked_fields:
            setattr(edition, field, value)
    if row.get("price") is not None:
        edition.price = row["price"]
    edition.is_active = True
    edition.last_synced_at = timezone.now()
    edition.save()


def sync_publisher_rows(parsed_rows, batch, fixed_publisher=None):
    """
    fixed_publisher: set for mode=single uploads (every row belongs to this
    one Publisher). Left None for mode=multi uploads, where each row's own
    'publisher' field decides.

    Deactivates any Edition belonging to a touched publisher that was NOT
    seen in this upload -- scoped per-publisher, so uploading one publisher's
    file never touches another publisher's editions.
    """
    seen_edition_ids = set()
    touched_publisher_ids = set()

    for row in parsed_rows:
        clean_title, resolved_author = clean_title_and_extract_author(
            row.get("title", ""), publisher_hint=fixed_publisher.name if fixed_publisher else row.get("publisher_name", ""), known_author=row.get("author", "")
        )
        row["title"] = clean_title
        row["author"] = resolved_author

        publisher = fixed_publisher or get_or_create_publisher(row.get("publisher_name", ""))
        if not publisher:
            batch.skipped_rows += 1
            continue
        touched_publisher_ids.add(publisher.id)

        book, confidence = find_matching_book(row["title"])

        if confidence == "matched":
            apply_row_to_book(book, row)
        elif confidence == "needs_review":
            book = Book.objects.create(
                title=row["title"], category=row.get("category", ""), subcategory=row.get("subcategory", ""),
                source=Book.Source.PUBLISHER_IMPORT, needs_review=True,
            )
            batch.needs_review_rows += 1
        else:
            book = Book.objects.create(
                title=row["title"], category=row.get("category", ""), subcategory=row.get("subcategory", ""),
                source=Book.Source.PUBLISHER_IMPORT,
            )

        if row.get("author") and "authors" not in book.import_locked_fields:
            set_book_author(book, row["author"])

        edition, created = Edition.objects.get_or_create(
            book=book, publisher=publisher,
            defaults={"price": row.get("price") or 0},
        )
        apply_row_to_edition(edition, row)

        if row.get("translator") and "translator" not in edition.import_locked_fields:
            set_edition_translator(edition, row["translator"])

        seen_edition_ids.add(edition.id)
        batch.matched_rows += 1
        batch.processed_rows += 1

    stale_qs = Edition.objects.filter(
        publisher_id__in=touched_publisher_ids, is_active=True
    ).exclude(id__in=seen_edition_ids)
    deactivated_count = stale_qs.count()
    stale_qs.update(is_active=False)
    batch.deactivated_rows = deactivated_count

    batch.save()
    return {
        "deactivated": deactivated_count,
        "matched": batch.matched_rows,
        "needs_review": batch.needs_review_rows,
        "publishers_touched": len(touched_publisher_ids),
    }


def get_cheapest_edition(book):
    """Only active AND recently-synced editions are considered -- a
    publisher that's gone quiet for over a month drops out of 'cheapest'
    consideration even if still technically active."""
    fresh_cutoff = timezone.now() - timezone.timedelta(days=STALE_AFTER_DAYS)
    if hasattr(book, "_card_editions"):
        return next((edition for edition in book._card_editions if edition.last_synced_at and edition.last_synced_at >= fresh_cutoff), None)
    return (
        book.editions
        .filter(is_active=True, last_synced_at__gte=fresh_cutoff)
        .order_by("price")
        .first()
    )
