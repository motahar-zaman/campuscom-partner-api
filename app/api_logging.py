from campuslibs.loggers.mongo import save_to_mongo


class ApiLogging:
    def store_logging_data(self, request, data, action, type, status_code=200, erp='site', collection=None):
        data = {
            'course_provider': {
                'id': str(request.course_provider.id),
                'name': request.course_provider.name,
            },
            'data': data,
            'action': action,
            'status_code': status_code,
            'type': type,
            'ERP': erp
        }

        if not collection:
            collection = 'erp_request_response'

        save_to_mongo(data=data, collection=collection)
