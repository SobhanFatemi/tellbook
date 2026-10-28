from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import APIException
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsCreator
from core.services import lock_buyer
from publisher_catalog.models import Edition
from requests_orders.models import Order
from requests_orders.serializers import ApplyDiscountSerializer, OrderSerializer
from .models import Product, ProductImage, BundleComponent
from .services import product_state, checkout, fulfill_purchase


def catalog():
    return Product.objects.prefetch_related('images', 'components__product', 'components__edition__book', 'components__edition__publisher')


class StaleProduct(APIException):
    status_code = 409
    default_detail = 'اطلاعات محصول تغییر کرده است. فهرست را تازه کنید و دوباره ویرایش کنید.'


class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'caption']


class ComponentSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    book_id = serializers.IntegerField(source='edition.book_id', read_only=True, default=None)
    price = serializers.SerializerMethodField()
    sold_separately = serializers.SerializerMethodField()

    def get_title(self, obj):
        return obj.product.title if obj.product_id else f'{obj.edition.book.title} — {obj.edition.publisher.name}'

    def get_price(self, obj):
        return obj.product.price if obj.product_id else obj.edition.book.apply_discount(obj.edition.price)

    def get_sold_separately(self, obj):
        return obj.product.sold_separately if obj.product_id else True

    class Meta:
        model = BundleComponent
        fields = ['product', 'edition', 'quantity', 'title', 'book_id', 'price', 'sold_separately']


class ProductSerializer(serializers.ModelSerializer):
    images = ImageSerializer(many=True, read_only=True)
    components = ComponentSerializer(many=True, read_only=True)
    available = serializers.SerializerMethodField()
    needs_sourcing = serializers.SerializerMethodField()
    estimated_days = serializers.SerializerMethodField()

    def get_available(self, obj): return product_state(obj)[0]
    def get_needs_sourcing(self, obj): return product_state(obj)[1]
    def get_estimated_days(self, obj): return product_state(obj)[2]

    class Meta:
        model = Product
        fields = ['id', 'title', 'category', 'description', 'specifications', 'price', 'is_active', 'sold_separately', 'is_bundle', 'lead_days', 'featured', 'priority', 'images', 'components', 'available', 'needs_sourcing', 'estimated_days', 'updated_at']


class ComponentInput(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.filter(is_bundle=False), required=False, allow_null=True)
    edition = serializers.PrimaryKeyRelatedField(queryset=Edition.objects.all(), required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1, max_value=100)

    def validate(self, data):
        if bool(data.get('product')) == bool(data.get('edition')):
            raise serializers.ValidationError('یک محصول یا یک نسخه کتاب انتخاب کنید.')
        return data


class ProductInput(serializers.ModelSerializer):
    components = ComponentInput(many=True, required=False, max_length=50)
    price = serializers.IntegerField(min_value=1, max_value=99999999999)
    lead_days = serializers.IntegerField(min_value=0, max_value=365)

    class Meta:
        model = Product
        fields = ['title', 'category', 'description', 'specifications', 'price', 'is_active', 'sold_separately', 'is_bundle', 'lead_days', 'featured', 'priority', 'components']

    def validate(self, data):
        bundle = data.get('is_bundle', self.instance.is_bundle if self.instance else False)
        if self.instance and bundle != self.instance.is_bundle:
            raise serializers.ValidationError('نوع محصول پس از ساخت قابل تغییر نیست؛ محصول تازه بسازید.')
        components = data.get('components')
        if components is not None:
            if components and not bundle:
                raise serializers.ValidationError('فقط پک می‌تواند محتویات داشته باشد.')
            keys = [(c.get('product').pk if c.get('product') else None, c.get('edition').pk if c.get('edition') else None) for c in components]
            if len(set(keys)) != len(keys):
                raise serializers.ValidationError('هر قلم را یک بار اضافه کنید و تعدادش را تغییر دهید.')
        active = data.get('is_active', self.instance.is_active if self.instance else False)
        if bundle and active and not (components if components is not None else self.instance and self.instance.components.exists()):
            raise serializers.ValidationError('پیش از انتشار، محتویات پک را انتخاب کنید.')
        return data

    def create(self, data):
        components = data.pop('components', [])
        obj = Product.objects.create(**data)
        for row in components: BundleComponent.objects.create(bundle=obj, **row)
        return obj

    def update(self, obj, data):
        components = data.pop('components', None)
        obj = super().update(obj, data)
        if components is not None:
            obj.components.all().delete()
            for row in components: BundleComponent.objects.create(bundle=obj, **row)
        return obj


class ProductList(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer

    def get_queryset(self):
        qs = catalog().filter(is_active=True, sold_separately=True)
        q = self.request.query_params.get('q', '').strip()[:200]
        if q: qs = qs.filter(Q(title__icontains=q) | Q(category__icontains=q))
        if self.request.query_params.get('featured') == '1':
            return [p for p in qs.filter(featured=True, is_bundle=True) if product_state(p)[0]][:6]
        return qs


class ProductDetail(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer
    queryset = catalog().filter(is_active=True, sold_separately=True)


class AdminProducts(APIView):
    permission_classes = [IsCreator]

    def get(self, request):
        return Response(ProductSerializer(catalog(), many=True, context={'request': request}).data)

    @transaction.atomic
    def post(self, request):
        serializer = ProductInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(ProductSerializer(obj, context={'request': request}).data, status=201)


class AdminProduct(APIView):
    permission_classes = [IsCreator]

    @transaction.atomic
    def patch(self, request, pk):
        # Same lock ordering as checkout, including components of edited bundles.
        locked = list(Product.objects.select_for_update().order_by('pk'))
        obj = next((p for p in locked if p.pk == pk), None)
        if obj is None: obj = get_object_or_404(Product, pk=pk)
        expected = serializers.DateTimeField().run_validation(request.data.get('expected_updated_at'))
        if expected != obj.updated_at:
            raise StaleProduct()
        serializer = ProductInput(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProductSerializer(catalog().get(pk=pk), context={'request': request}).data)


class AdminImages(APIView):
    permission_classes = [IsCreator]

    @transaction.atomic
    def post(self, request, pk):
        product = get_object_or_404(Product.objects.select_for_update(), pk=pk)
        serializer = ImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = serializer.validated_data['image']
        if image.size > 8 * 1024 * 1024 or image.content_type not in ['image/jpeg', 'image/png', 'image/webp']:
            raise serializers.ValidationError('تصویر JPG، PNG یا WebP تا ۸ مگابایت انتخاب کنید.')
        if product.images.count() >= 12:
            raise serializers.ValidationError('برای هر محصول حداکثر ۱۲ تصویر ثبت کنید.')
        serializer.save(product=product)
        return Response(serializer.data, status=201)

    def delete(self, request, pk, image_id):
        image = get_object_or_404(ProductImage, pk=image_id, product_id=pk)
        image.delete()
        return Response(status=204)


class EditionChoices(APIView):
    permission_classes = [IsCreator]

    def get(self, request):
        q = request.query_params.get('q', '').strip()[:200]
        if len(q) < 2: return Response([])
        editions = Edition.objects.filter(Q(book__title__icontains=q) | Q(isbn__icontains=q), is_active=True).select_related('book', 'publisher')[:30]
        return Response([{'id': e.pk, 'title': f'{e.book.title} — {e.publisher.name}', 'price': e.book.apply_discount(e.price)} for e in editions])


class CartLine(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1, required=False)
    edition_id = serializers.IntegerField(min_value=1, required=False)
    quantity = serializers.IntegerField(min_value=1, max_value=20)
    expected_price = serializers.IntegerField(min_value=1, max_value=99999999999)

    def validate(self, data):
        if bool(data.get('product_id')) == bool(data.get('edition_id')):
            raise serializers.ValidationError('یک محصول یا نسخه کتاب انتخاب کنید.')
        return data


class CheckoutInput(ApplyDiscountSerializer):
    key = serializers.UUIDField()
    lines = CartLine(many=True, allow_empty=False, max_length=30)

    def validate(self, data):
        data = super().validate(data)
        if sum(line['quantity'] for line in data['lines']) > 100:
            raise serializers.ValidationError('در هر خرید حداکثر ۱۰۰ قلم انتخاب کنید.')
        return data


class Checkout(APIView):
    def post(self, request):
        serializer = CheckoutInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = checkout(request.user, serializer.validated_data)
        return Response(OrderSerializer(order).data, status=201)


class Fulfill(APIView):
    permission_classes = [IsCreator]

    @transaction.atomic
    def post(self, request, pk):
        ref = get_object_or_404(Order, pk=pk)
        lock_buyer(ref.buyer_id)
        order = Order.objects.select_for_update().get(pk=pk)
        if not hasattr(order, 'merchandise') or order.status not in ['paid', 'sourcing'] or order.payment.status != 'verified':
            raise serializers.ValidationError('فقط سفارش پرداخت‌شده در انتظار تهیه قابل آماده‌سازی است.')
        selection = serializers.ListField(child=serializers.IntegerField(min_value=0), allow_empty=False)
        indices = selection.run_validation(request.data.get('indices'))
        if len(set(indices)) != len(indices) or not set(indices).issubset(set(order.merchandise.fulfillment_units.filter(stock_item=None, failed=False).values_list('index', flat=True))):
            raise serializers.ValidationError('فهرست اقلام تغییر کرده است؛ سفارش را تازه کنید.')
        fulfill_purchase(order, indices=indices)
        return Response(OrderSerializer(order).data)
