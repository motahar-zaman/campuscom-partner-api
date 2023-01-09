from publish.permissions import HasCourseProviderAPIKey
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
)
from rest_framework import viewsets
from datetime import datetime
from django_scopes import scopes_disabled
from rest_framework.decorators import permission_classes
from rest_framework.status import (
    HTTP_200_OK,
)
from campuslibs.refund.refund import Refund
from api_logging import ApiLogging


# Create your views here.
@permission_classes([HasCourseProviderAPIKey])
class RefundViewSet(viewsets.ModelViewSet):
    refund = Refund()
    http_method_names = ['post', 'head',]

    def get_queryset(self):
        fields = self.request.GET.copy()
        try:
            fields.pop("limit")
            fields.pop("page")
        except KeyError:
            pass

        return self.model.objects.filter(**fields.dict())

    def create(self, request, *args, **kwargs):
        log = ApiLogging()

        status, data, message = self.refund.validate_refund_data(request)
        if not status:
            log.store_logging_data(request, request.data.copy(), 'refund', 'request', status_code=HTTP_400_BAD_REQUEST)
            return Response(
                {
                    "error": message,
                    "status_code": 400,
                },
                status=HTTP_400_BAD_REQUEST,
            )
        else:
            log.store_logging_data(request, request.data.copy(), 'refund', 'request', status_code=HTTP_200_OK)

        status, response = self.refund.refund(request, data, requested_by='partner')
        if status:
            log_data = {
                'refund_id': str(response.id),
                'payment_id': str(response.payment.id),
                'payment_amount': float(response.payment.amount),
                'refund_amount': response.amount,
                'note': response.note,
                'status': response.status,
                'requested_by': response.requested_by,
                'message': 'refund request placed successfully'
            }
            log.store_logging_data(request, log_data, 'refund', 'response', status_code=HTTP_200_OK)
            return Response({'message': 'refund request placed successfully'}, status=HTTP_200_OK)

        else:
            log.store_logging_data(request, response, 'refund', 'response', status_code=HTTP_400_BAD_REQUEST)
            try:
                errors = response['transactionResponse']['errors']
            except Exception:
                return Response(
                    {
                        "error": {
                            "message": "something went wrong, please try again with correct information"
                        },
                        "status_code": 400,
                    },
                    status=HTTP_400_BAD_REQUEST,
                )
            else:
                for error in errors:
                    if error['errorCode'] == '54':
                        return Response(
                            {
                                "error": {
                                    "message": "Might not match required criteria for issuing a refund."
                                },
                                "status_code": 400,
                            },
                            status=HTTP_400_BAD_REQUEST,
                        )
                    elif error['errorCode'] == '11':
                        return Response(
                            {
                                "error": {
                                    "message": error['errorText']
                                },
                                "status_code": 400,
                            },
                            status=HTTP_400_BAD_REQUEST,
                        )

                else:
                    return Response(
                        {
                            "error": {
                                "message": errors[0]['errorText']
                            },
                            "status_code": 400,
                        },
                        status=HTTP_400_BAD_REQUEST,
                    )