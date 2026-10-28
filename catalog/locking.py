from django.db import connection


def lock_catalog():
    """Serialize staff edits and staged import commits within a transaction."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [84271033])
