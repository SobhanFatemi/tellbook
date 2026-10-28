from django.urls import path
from .api import ProductList, ProductDetail, AdminProducts, AdminProduct, AdminImages, EditionChoices, Checkout, Fulfill
urlpatterns = [
    path('', ProductList.as_view()),
    path('<int:pk>/', ProductDetail.as_view()),
    path('checkout/', Checkout.as_view()),
    path('admin/', AdminProducts.as_view()),
    path('admin/<int:pk>/', AdminProduct.as_view()),
    path('admin/<int:pk>/images/', AdminImages.as_view()),
    path('admin/<int:pk>/images/<int:image_id>/', AdminImages.as_view()),
    path('admin/editions/', EditionChoices.as_view()),
    path('admin/orders/<int:pk>/ready/', Fulfill.as_view()),
]
