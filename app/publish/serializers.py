from rest_framework import serializers
from shared_models.models import Product


class ProductSerializer(serializers.ModelSerializer):

    class Meta:
        model = Product
        fields = (
            'id', 'store', 'external_id', 'product_type',
            'title', 'content', 'image', 'limit_applicable',
            'total_quantity', 'quantity_sold', 'available_quantity',
            'is_active', 'tax_code', 'fee', 'currency_code'
        )
