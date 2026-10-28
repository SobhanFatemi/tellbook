import re

from rapidfuzz import fuzz

from publisher_catalog.services import LOW_CONFIDENCE, normalize_persian
from .models import Book


def suggest_similar_books(title, limit=3):
    """
    "Did you mean...?" suggestions for a buyer typing a title into the
    request form. Reuses the same normalization, numbered-series guard, and
    LOW_CONFIDENCE threshold as the publisher-import matcher (find_matching_book
    in publisher_catalog/services.py), but returns a ranked top-N instead of
    a single best guess -- a buyer choosing needs options, an import pipeline
    deciding auto-match-or-not needs one answer.

    Only suggests already-reviewed books (needs_review=False) -- nothing
    still sitting in the internal review queue should surface to a buyer.
    """
    if not title or not title.strip():
        return []

    title_norm = normalize_persian(title)
    title_numbers = set(re.findall(r"\d+", title_norm))

    scored = []
    for book in Book.objects.filter(needs_review=False):
        book_title_norm = normalize_persian(book.title)
        book_numbers = set(re.findall(r"\d+", book_title_norm))

        if title_numbers and book_numbers and title_numbers != book_numbers:
            continue  # conflicting numbers -- different volume, never a candidate

        score = fuzz.token_set_ratio(title_norm, book_title_norm)
        if score >= LOW_CONFIDENCE:
            scored.append((book, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:limit]
