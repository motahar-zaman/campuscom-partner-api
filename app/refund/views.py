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
        try:
            erp = request.course_provider.configuration.get('erp', '')
        except:
            erp = ''
        log_data = {
            'request': {
                'headers': request.headers,
                'body': request.data.copy()
            },
            'response': {
                'headers': {},
                'body': {}
            }
        }

        status, data, message = self.refund.validate_refund_data(request)
        if not status:
            response = Response({
                "error": {
                    'message': message
                },
                "status_code": 400,
            }, status=HTTP_400_BAD_REQUEST)

            log_data['response']['body'] = response.data
            log_data['response']['headers'] = response.headers
            log.store_logging_data(request, log_data, 'refund request-response', status_code=HTTP_400_BAD_REQUEST, erp=erp)
            return response

        status, refund_response = self.refund.refund(request, data, requested_by='partner')
        if status:
            response = Response({'message': 'refund request placed successfully'}, status=HTTP_200_OK)
            log_data['response']['body'] = response.data
            log_data['response']['headers'] = response.headers
            log.store_logging_data(request, log_data, 'refund request-response', status_code=HTTP_200_OK, erp=erp)
            return response

        else:
            try:
                errors = refund_response['transactionResponse']['errors']
            except Exception:
                response = Response(
                    {
                        "error": {
                            "message": "something went wrong, please try again with correct information"
                        },
                        "status_code": 400,
                    },
                    status=HTTP_400_BAD_REQUEST,
                )
                log_data['response']['body'] = response.data
                log_data['response']['headers'] = response.headers
                log.store_logging_data(request, log_data, 'refund request-response', status_code=HTTP_400_BAD_REQUEST, erp=erp)
                return response
            else:
                for error in errors:
                    if error['errorCode'] == '54':
                        response =  Response(
                            {
                                "error": {
                                    "message": "Might not match required criteria for issuing a refund."
                                },
                                "status_code": 400,
                            },
                            status=HTTP_400_BAD_REQUEST,
                        )
                        log_data['response']['body'] = response.data
                        log_data['response']['headers'] = response.headers
                        log.store_logging_data(request, log_data, 'refund request-response', status_code=HTTP_400_BAD_REQUEST, erp=erp)
                        return response
                    elif error['errorCode'] == '11':
                        response =  Response(
                            {
                                "error": {
                                    "message": error['errorText']
                                },
                                "status_code": 400,
                            },
                            status=HTTP_400_BAD_REQUEST,
                        )
                        log_data['response']['body'] = response.data
                        log_data['response']['headers'] = response.headers
                        log.store_logging_data(request, log_data, 'refund request-response', status_code=HTTP_400_BAD_REQUEST, erp=erp)
                        return response

                else:
                    response =  Response(
                        {
                            "error": {
                                "message": errors[0]['errorText']
                            },
                            "status_code": 400,
                        },
                        status=HTTP_400_BAD_REQUEST,
                    )
                    log_data['response']['body'] = response.data
                    log_data['response']['headers'] = response.headers
                    log.store_logging_data(request, log_data, 'refund request-response', status_code=HTTP_400_BAD_REQUEST, erp=erp)
                    return response