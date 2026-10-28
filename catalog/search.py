"""Equivalent Persian spellings for database search, without changing catalog text."""
import re
from django.db.models import CharField, Func, Value
from django.db.models.functions import Lower

SOURCE = 'يكى۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩'
TARGET = 'یکی01234567890123456789'
IGNORED = r'[\s\u200c\u200dـًٌٍَُِّْ]'


def normalized_text(value):
    return re.sub(IGNORED, '', value.translate(str.maketrans(SOURCE, TARGET))).lower()


def normalized_field(field):
    translated = Func(field, Value(SOURCE), Value(TARGET), function='TRANSLATE', output_field=CharField())
    return Lower(Func(translated, Value('[[:space:]‌‍ـًٌٍَُِّْ]'), Value(''), Value('g'), function='REGEXP_REPLACE', output_field=CharField()))
