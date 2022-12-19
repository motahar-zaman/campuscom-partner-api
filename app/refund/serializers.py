from rest_framework import serializers
from shared_models.models import PaymentRefund


class PaymentRefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentRefund
        fields = ('id', 'payment', 'amount', 'note', 'status', 'requested_by', 'transaction_reference',
                  'task_cancel_enrollment', 'task_tax_refund', 'task_crm_update')
