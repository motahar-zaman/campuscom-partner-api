from campuslibs.loggers.mongo import save_to_mongo
from django.utils import timezone


class ApiLogging:
    def store_logging_data(self, request, data, summary, status_code=200, erp='site', collection=None):
        data = {
            'course_provider': {
                'id': str(request.course_provider.id),
                'name': request.course_provider.name,
            },
            'data': data,
            'status_code': status_code,
            'summary': summary,
            'ERP': erp,
            'created_at': timezone.now()
        }

        if not collection:
            collection = 'erp_request_response'

        save_to_mongo(data=data, collection=collection)
