from django.urls import path

from .views import PaymentVerificationQueueView, UploadPaymentProofView, VerifyPaymentView

from .views import PaymentReceiptView, UploadPaymentByIdView

urlpatterns = [
    path("<int:payment_id>/upload/", UploadPaymentByIdView.as_view(), name="payment-upload"),
    path("<int:payment_id>/receipt/", PaymentReceiptView.as_view(), name="payment-receipt"),
    path("<int:order_id>/proof/", UploadPaymentProofView.as_view(), name="upload-payment-proof"),
    path("verification-queue/", PaymentVerificationQueueView.as_view(), name="payment-verification-queue"),
    path("<int:payment_id>/verify/", VerifyPaymentView.as_view(), name="verify-payment"),
]
