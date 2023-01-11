from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK
from publish.permissions import HasCourseProviderAPIKey
from shared_models.models import Cart, StudentProfile, CourseEnrollment, CertificateEnrollment, ProfileStore
from django_scopes import scopes_disabled
from campuslibs.loggers.mongo import save_to_mongo
from campuslibs.enrollment.common import Common
from .utils import payment_transaction
from django.utils import timezone
from api_logging import ApiLogging


def handle_enrollment_event(payload, cart, course_provider):
    to_dict = Common()
    with scopes_disabled():
        cart_items = cart.cart_items.all()
    void_payment_status = True
    course_enrollment = False
    for item in payload['enrollments']:
        try:
            enrollment = CourseEnrollment.objects.get(ref_id=item['enrollment_id'], cart_item__in=cart_items, course__course_provider=course_provider)
        except CourseEnrollment.DoesNotExist:
            pass
        else:
            course_enrollment = True
            enrollment.status = CourseEnrollment.STATUS_FAILED
            with scopes_disabled():
                payment = enrollment.cart_item.cart.payment_set.first()

            # admin = False
            # affiliate_payment_info = payment.affiliate_payment_info
            # if affiliate_payment_info and affiliate_payment_info.get('reference', None) and affiliate_payment_info.get('note', None):
            #     admin = True

            if item['status'] == 'success':
                void_payment_status = False

                if payment.amount > 0.0 and payment.store_payment_gateway and payment.status == 'authorized':
                    # log before and after payment capture request
                    data = {
                        'data': {
                            'payment': {
                                'id': str(payment.id),
                                'cart_id': str(payment.cart.id),
                                'order_ref': payment.cart.order_ref
                            },
                            'store_payment_gateway': {
                                'id': str(payment.store_payment_gateway.id),
                                'name': payment.store_payment_gateway.name
                            }
                        },
                        'cart': {
                            'id': str(payment.cart.id),
                            'order_ref': payment.cart.order_ref
                        },
                        'created_at': timezone.now(),
                        'summary': 'capture request of order ' + str(payment.cart.order_ref)
                    }
                    save_to_mongo(data, 'payment_request_response')

                    capture, response = payment_transaction(payment, payment.store_payment_gateway, 'priorAuthCaptureTransaction')

                    data = {
                        'data': {
                            'response': to_dict.objectified_element_to_dict(response),
                            'capture': capture,
                            'payment_id': str(payment.id),
                        },
                        'cart': {
                            'id': str(payment.cart.id),
                            'order_ref': payment.cart.order_ref,
                        },
                        'created_at': timezone.now(),
                        'summary': 'capture response of order ' + str(payment.cart.order_ref)
                    }
                    save_to_mongo(data, 'payment_request_response')

                    if capture:
                        enrollment.status = CourseEnrollment.STATUS_SUCCESS
                else:
                    enrollment.status = CourseEnrollment.STATUS_SUCCESS
            elif item['status'] == 'cancel':
                enrollment.status = CourseEnrollment.STATUS_CANCELED

                # maintain inventory
                with scopes_disabled():
                    try:
                        cart_item = enrollment.cart_item
                        product = cart_item.product
                        product.quantity_sold -= cart_item.quantity
                        product.available_quantity += cart_item.quantity
                        product.save()
                    except Exception:
                        pass
            else:
                void_payment_status = False
            enrollment.save()
    if void_payment_status and course_enrollment:
        with scopes_disabled():
            payment = cart.payment_set.first()
        if payment.amount > 0.0 and payment.store_payment_gateway and payment.status == 'authorized':
            data = {
                'data': {
                    'payment': {
                        'id': str(payment.id),
                        'cart_id': str(payment.cart.id),
                        'order_ref': payment.cart.order_ref,
                    },
                    'store_payment_gateway': {
                        'id': str(payment.store_payment_gateway.id),
                        'name': payment.store_payment_gateway.name
                    }
                },
                'cart': {
                    'id': str(payment.cart.id),
                    'order_ref': payment.cart.order_ref,
                },
                'created_at': timezone.now(),
                'summary': 'voidTransaction request of order ' + str(payment.cart.order_ref)
            }
            save_to_mongo(data, 'payment_request_response')
            capture, response = payment_transaction(payment, payment.store_payment_gateway, 'voidTransaction')
            data = {
                'data': {
                    'response': to_dict.objectified_element_to_dict(response),
                    'capture': capture,
                    'payment_id': str(payment.id)
                },
                'cart': {
                    'id': str(payment.cart.id),
                    'order_ref': payment.cart.order_ref,
                },
                'created_at': timezone.now(),
                'summary': 'voidTransaction response of order ' + str(payment.cart.order_ref)
            }
            save_to_mongo(data, 'payment_request_response')
            if capture:
                payment.status = payment.STATUS_VOID
                payment.save()

    return True


def handle_student_event(payload, cart, course_provider):
    with scopes_disabled():
        cart_items = cart.cart_items.all()
    for item in payload['enrollments']:
        if item['status'] == 'success':
            profile = None
            try:
                enrollment = CourseEnrollment.objects.get(
                    ref_id=item['enrollment_id'], cart_item__in=cart_items, course__course_provider=course_provider
                )
            except CourseEnrollment.DoesNotExist:
                pass
            else:
                profile = enrollment.profile
            try:
                enrollment = CertificateEnrollment.objects.get(ref_id=item['enrollment_id'])
            except CertificateEnrollment.DoesNotExist:
                pass
            else:
                profile = enrollment.profile
            if profile is not None:
                # contracts = CourseSharingContract.objects.filter(course_provider=course_provider)
                # for contract in contracts:
                try:
                    student_profile = StudentProfile.objects.get(
                        profile=profile, course_provider=course_provider
                    )
                except StudentProfile.DoesNotExist:
                    StudentProfile.objects.create(
                        profile=profile,
                        course_provider=course_provider,
                        external_profile_id=str(item['school_student_id'])
                    )
                else:
                    student_profile.external_profile_id = str(item['school_student_id'])
                    student_profile.save()

                # tag profile of the purchaser with store
                try:
                    obj, created = ProfileStore.objects.get_or_create(
                        profile=cart.profile,
                        store=cart.store,
                        defaults={'is_primary': False},
                    )
                except Exception:
                    pass

                # tag profile of the student with store
                try:
                    obj, created = ProfileStore.objects.get_or_create(
                        profile=profile,
                        store=cart.store,
                        defaults={'is_primary': False},
                    )
                except Exception:
                    pass
    return True


@api_view(['POST'])
@permission_classes([HasCourseProviderAPIKey])
def webhooks(request):
    log = ApiLogging()
    save_to_mongo(data=request.data.copy(), collection='j1:webhooks')
    try:
        event_type = request.data['event_type']
    except KeyError:
        log.store_logging_data(request, {'payload': request.data.copy(), 'response': {'message': 'event type must be provided'}},
                               'j1_push request-response from provider ' + request.course_provider.name,
                               status_code=HTTP_200_OK)
        return Response({'message': 'event type must be provided'}, status=HTTP_200_OK)

    try:
        cart_id = request.data['order_id']
    except KeyError:
        log.store_logging_data(request,
                               {'payload': request.data.copy(), 'response': {'message': 'order_id must be provided'}},
                               'j1_push request-response from provider ' + request.course_provider.name,
                               status_code=HTTP_200_OK)
        return Response({'message': 'order_id must be provided'}, status=HTTP_200_OK)

    with scopes_disabled():
        try:
            cart = Cart.objects.get(order_ref=cart_id)
        except Cart.DoesNotExist:
            log.store_logging_data(request, {'payload': request.data.copy(),
                                             'response': {'message': 'invalid order_id'}},
                                   'j1_push request-response from provider ' + request.course_provider.name,
                                   status_code=HTTP_200_OK)
            return Response({'message': 'invalid order_id'}, status=HTTP_200_OK)
        else:
            if cart.enrollment_request is None:
                cart.enrollment_request = {}

    try:
        payload = request.data['payload']
    except KeyError:
        cart.enrollment_request['enrollment_notification_response'] = {'message': 'payload must be provided'}
        cart.save()
        log.store_logging_data(request, {'payload': request.data.copy(), 'response': {'message': 'payload must be provided'}},
                               'j1_push request-response from provider ' + request.course_provider.name,
                               status_code=HTTP_200_OK)
        return Response({'message': 'payload must be provided'}, status=HTTP_200_OK)
    else:
        cart.enrollment_request['enrollment_notification'] = payload
        cart.save()

    if event_type == 'enrollment':
        handle_enrollment_event(payload, cart, request.course_provider)
        handle_student_event(payload, cart, request.course_provider)

    else:
        cart.enrollment_request['enrollment_notification_response'] = {'message': 'unrecognized event type'}
        cart.save()
        log.store_logging_data(request,
                               {'payload': request.data.copy(), 'response': {'message': 'unrecognized event type'}},
                               'j1_push request-response from provider ' + request.course_provider.name,
                               status_code=HTTP_200_OK)
        return Response({'message': 'unrecognized event type'}, status=HTTP_200_OK)

    cart.enrollment_request['enrollment_notification_response'] = {'message': 'ok'}
    cart.save()
    log.store_logging_data(request, {'payload': request.data.copy(), 'response': {'message': 'ok'}},
                           'j1_push request-response from provider ' + request.course_provider.name,
                           status_code=HTTP_200_OK)
    return Response({'message': 'ok'}, status=HTTP_200_OK)
