import logging

from django.conf import settings
from django.core.mail import send_mail

from .models import NotificationLog

logger = logging.getLogger(__name__)


class NotificationService:
    @staticmethod
    def active_channel():
        return getattr(settings, "NOTIFICATION_CHANNEL", "email")  # "email" now, "sms" once Kavenegar is bought

    @classmethod
    def _send(cls, message, phone=None, email=None, related_user=None, sensitive=False):
        channel = cls.active_channel()
        success = False
        error_detail = ""

        if channel == "email" and email:
            try:
                send_mail(
                    subject="Your verification code" if "verification" in message.lower() else "Notification",
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                )
                success = True
            except Exception as exc:
                success = False
                error_detail = str(exc)
                # this used to be swallowed silently -- now it's both logged
                # (visible in `docker-compose logs web`) and returned to the
                # caller so a real SMTP failure isn't reported as "sent"
                logger.error("Failed to send email to %s: %s", email, exc)
        elif channel == "sms" and phone:
            error_detail = "SMS delivery is not configured yet."

        NotificationLog.objects.create(
            recipient_phone=phone or "", recipient_email=email, channel=channel,
            message="Verification code delivery" if sensitive else message, related_user=related_user,
            sent_successfully=success, error_detail=error_detail,
        )
        return success

    @classmethod
    def notify_creator_new_order(cls, order):
        creator = cls._get_creator()
        if creator:
            cls._send(f"New order #{order.id} — {order.total_price} Toman.", phone=creator.phone, email=creator.email)

    @classmethod
    def notify_creator_order_update(cls, order):
        creator = cls._get_creator()
        if creator:
            cls._send(f"Order #{order.id} status changed to {order.status}.", phone=creator.phone, email=creator.email)

    @classmethod
    def notify_creator_payment_uploaded(cls, payment):
        creator = cls._get_creator()
        if creator:
            cls._send(
                f"Receipt uploaded for payment #{payment.id}, needs verification.",
                phone=creator.phone, email=creator.email,
            )

    @classmethod
    def notify_buyer_quote_sent(cls, buyer, book_request, quote):
        cls._send(
            f"Your quote for '{book_request.title or book_request.book}' is ready: {quote.total_price} Toman.",
            phone=buyer.phone, email=buyer.email, related_user=buyer,
        )

    @classmethod
    def notify_buyer_request_failed(cls, buyer, book_request, refunded=False):
        title = book_request.title or (book_request.book and book_request.book.title) or "your book"
        message = f"We couldn't source '{title}': {book_request.failure_reason}."
        if refunded:
            message += " A refund has been issued and will be processed shortly."
        cls._send(message, phone=buyer.phone, email=buyer.email, related_user=buyer)

    @staticmethod
    def _get_creator():
        from accounts.models import User
        return User.objects.filter(role=User.Role.CREATOR).first()