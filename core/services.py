from accounts.models import User


def lock_buyer(buyer_id):
    """First lock for buyer order/payment/stock mutations; requires atomic()."""
    return User.objects.select_for_update().get(pk=buyer_id)
