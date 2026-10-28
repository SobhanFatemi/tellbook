from django.db import migrations


def protect_existing(apps, schema_editor):
    # Older records have no reliable import/manual provenance. Preserve their
    # metadata; approved imports may still update prices and availability.
    apps.get_model('catalog', 'Book').objects.update(import_locked_fields=[
        'title', 'authors', 'description', 'category', 'subcategory',
    ])
    apps.get_model('publisher_catalog', 'Edition').objects.update(import_locked_fields=[
        'translator', 'isbn', 'national_barcode', 'sku', 'cover_image_url',
        'cover_image_override', 'cover_type', 'print_year', 'page_count',
        'volume_count', 'print_run', 'weight', 'cost_price',
    ])


class Migration(migrations.Migration):
    dependencies = [('publisher_catalog', '0003_edition_import_locked_fields_and_more')]
    operations = [migrations.RunPython(protect_existing, migrations.RunPython.noop)]
