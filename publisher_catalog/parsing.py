"""
Reads a raw publisher Excel/CSV file and turns it into the plain list of
dicts that sync_publisher_rows() expects, using a saved PublisherImportProfile.

Two modes:
  - single: every row belongs to one fixed Publisher (profile.publisher set).
    A 'publisher' column in the mapping, if present, is ignored.
  - multi: the file itself contains many publishers (a rich distributor-style
    export). column_mapping MUST map "publisher_name" to a real column, and
    each row's own value decides which Publisher it belongs to.

Real-world lessons from the actual files tested against:
- The workbook's physical first sheet is not always the data sheet -- always
  read profile.sheet_name explicitly.
- Numbers can arrive with stray formatting -- cleaned defensively.
"""
import re
import math
from decimal import Decimal

import pandas as pd

REQUIRED_FIELDS = ("title", "price")
INT_FIELDS = ("print_year", "page_count", "volume_count", "print_run")


class WorksheetNotFound(ValueError):
    def __init__(self, sheet, available_sheets):
        self.available_sheets = available_sheets
        super().__init__(
            f"برگه «{sheet}» داخل این فایل اکسل وجود ندارد. "
            "«نام برگه» باید نام زبانه داخل اکسل باشد، نه نام فایل یا قالب. "
            "آن را خالی بگذارید تا اولین برگه خوانده شود، یا یکی از این نام‌ها را وارد کنید: "
            + "، ".join(available_sheets)
        )


def parse_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return None if pd.isna(value) else float(value)
    text = str(value).strip().replace("٫", ".").replace("٬", "")
    if not text:
        return None
    text = re.sub(r"[^\d.\-]", "", text)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def clean_cell(field, value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if field in {"category", "subcategory"}:
        from catalog.categories import normalize_category
        return normalize_category(value)
    if field in {"price", "cost_price", "weight"}:
        return parse_number(value)
    if field in INT_FIELDS:
        n = parse_number(value)
        return int(n) if n is not None and math.isfinite(n) and n.is_integer() else str(value)
    if field in {"isbn", "national_barcode", "sku"} and isinstance(value, (int, float)) and float(value).is_integer():
        return str(int(value))
    return str(value).strip()


def read_publisher_rows(file_obj, profile, include_invalid=False):
    if profile.price_unit not in {"toman", "rial"}:
        raise ValueError("واحد قیمت فایل را پیش از واردکردن روی ریال یا تومان تنظیم کنید.")
    df = pd.read_excel(file_obj, sheet_name=profile.sheet_name or 0, header=profile.header_row_index, nrows=100001)
    df.columns = df.columns.map(str)
    if len(df) > 100000:
        raise ValueError("فایل بیش از ۱۰۰ هزار ردیف دارد؛ آن را به فایل‌های کوچک‌تر تقسیم کنید.")
    mapping = profile.column_mapping
    missing = [column for column in mapping.values() if column not in df.columns]
    if missing:
        raise ValueError("ستون‌های قالب در فایل وجود ندارند: " + "، ".join(missing))
    if not all(field in mapping for field in REQUIRED_FIELDS):
        raise ValueError("ستون عنوان و قیمت باید مشخص شوند.")
    rows, skipped = [], 0
    for index, (_, raw) in enumerate(df.iterrows()):
        row = {field: clean_cell(field, raw[column]) for field, column in mapping.items()}
        row["source_row"] = profile.header_row_index + index + 2
        row["source_price"] = str(raw[mapping["price"]])
        error = ""
        if not row.get("title"):
            error = "عنوان کتاب خالی است."
        elif row.get("price") is None:
            error = "قیمت معتبر نیست."
        elif profile.mode == "multi" and not row.get("publisher_name"):
            error = "نام ناشر خالی است."
        else:
            for field in ["price", "cost_price"]:
                if row.get(field) is None:
                    continue
                amount = Decimal(str(row[field]))
                if profile.price_unit == "rial":
                    amount /= 10
                if not amount.is_finite() or amount < 0 or amount > 999999999999 or amount != amount.to_integral_value():
                    error = "قیمت پس از تبدیل باید عدد صحیح، نامنفی و حداکثر ۱۲رقمی به تومان باشد."
                    break
                row[field] = str(amount.to_integral_value()) if include_invalid else amount
            for field in INT_FIELDS:
                if row.get(field) is not None and (not isinstance(row[field], int) or row[field] < 0 or row[field] > 2147483647):
                    error = "مشخصات عددی کتاب معتبر نیست."
            weight = row.get('weight')
            if weight is not None and (not math.isfinite(weight) or weight < 0 or weight > 99999.999 or Decimal(str(weight)).as_tuple().exponent < -3):
                error = "وزن باید عدد نامنفی با حداکثر سه رقم اعشار و کمتر از ۱۰۰ هزار باشد."
            for field, limit in {"title":500,"author":300,"translator":300,"publisher_name":300,"category":200,"subcategory":200,"isbn":20,"national_barcode":30,"sku":100,"cover_type":100}.items():
                if row.get(field) and len(str(row[field])) > limit:
                    error = f"متن ستون {mapping.get(field, field)} بیش از حد طولانی است."
        if error:
            skipped += 1
            if not include_invalid:
                if row.get("title") and row.get("price") is not None:
                    raise ValueError(error)
                continue
            row["error"] = error
            # Keep invalid source values inspectable without NaN/Decimal JSON values.
            row = {key: str(value) if isinstance(value, Decimal) or (isinstance(value, float) and not math.isfinite(value)) else value for key, value in row.items()}
        rows.append(row)
    return rows, skipped


def preview_columns(file_obj, sheet_name=None, header_row_index=0, num_preview_rows=5):
    xl = pd.ExcelFile(file_obj)
    sheet = sheet_name or xl.sheet_names[0]
    if sheet not in xl.sheet_names:
        raise WorksheetNotFound(sheet, xl.sheet_names)
    header_df = pd.read_excel(file_obj, sheet_name=sheet, header=header_row_index, nrows=num_preview_rows)
    return {
        "available_sheets": xl.sheet_names,
        "selected_sheet": sheet,
        "columns": list(map(str, header_df.columns)),
        "preview_rows": header_df.fillna("").astype(str).values.tolist(),
    }
