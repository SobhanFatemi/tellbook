from datetime import timedelta

from django.db import migrations


def reconcile(apps, schema_editor):
    StockItem = apps.get_model('stock', 'StockItem')
    Payment = apps.get_model('payments', 'Payment')
    db = schema_editor.connection.alias
    for item in StockItem.objects.using(db).filter(status__in=['ready_to_ship', 'on_hold'], source_order__status='awaiting_payment').iterator():
        payment = Payment.objects.using(db).filter(order_id=item.source_order_id).first()
        if not payment or payment.status == 'verified':
            continue
        item.status = 'reserved'
        item.expires_at = None
        item.shipment_id = None
        item.save(using=db, update_fields=['status', 'expires_at', 'shipment'])
        payment.auto_cancel_at = None if payment.status == 'pending_verification' else payment.created_at + timedelta(minutes=30)
        payment.save(using=db, update_fields=['auto_cancel_at'])
    Payment.objects.using(db).filter(status='pending_verification').update(auto_cancel_at=None)


class Migration(migrations.Migration):
    dependencies = [('stock', '0002_alter_stockitem_status'), ('payments', '0002_alter_payment_proof_image')]
    operations = [migrations.RunPython(reconcile, migrations.RunPython.noop)]
