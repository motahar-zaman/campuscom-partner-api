from rest_framework import serializers
from shared_models.models import Payment, Notification
from rest_framework_mongoengine.fields import ReferenceField


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ('amount', 'currency_code', 'transaction_reference', 'auth_code', 'payment_type', 'bank', 'status',
                  'transaction_time', 'account_number', 'card_type', 'card_number', 'reason_code', 'reason_description',
                  'customer_ip')


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ('id', 'creation_time', 'status')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['type'] = instance.data['type']

        return data
