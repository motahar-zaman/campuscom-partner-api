from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK
from publish.permissions import HasStoreAPIKey
from shared_models.models import Cart, StudentProfile, CourseEnrollment, CertificateEnrollment
from django_scopes import scopes_disabled


def handle_enrollment_event(payload, cart, store):
    for item in payload['enrollments']:
        try:
            enrollment = CourseEnrollment.objects.get(id=item['enrollment_id'])
        except CourseEnrollment.DoesNotExist:
            pass
        else:
            enrollment.status = item['status']
            enrollment.save()

        try:
            enrollment = CertificateEnrollment.objects.get(
                id=item['enrollment_id'])
        except CertificateEnrollment.DoesNotExist:
            pass
        else:
            enrollment.status = item['status']
            enrollment.save()

    return True


def handle_student_event(payload, cart, store):
    for item in payload['students']:
        profile = None
        try:
            enrollment = CourseEnrollment.objects.get(id=item['enrollment_id'])
        except CourseEnrollment.DoesNotExist:
            pass
        else:
            profile = enrollment.profile

        try:
            enrollment = CertificateEnrollment.objects.get(
                id=item['enrollment_id'])
        except CertificateEnrollment.DoesNotExist:
            pass
        else:
            profile = enrollment.profile
        if profile is not None:
            try:
                student_profile = StudentProfile.objects.get(
                    profile=profile, store=store)
            except StudentProfile.DoesNotExist:
                StudentProfile.objects.create(
                    profile=profile,
                    store=store,
                    external_profile_id=str(item['school_student_id'])
                )
            else:
                student_profile.external_profile_id = str(
                    item['school_student_id'])
                student_profile.save()
    return True


@api_view(['POST'])
@permission_classes([HasStoreAPIKey])
def webhooks(request):
    try:
        even_type = request.data['event_type']
    except KeyError:
        return Response({'message': 'event type must be provided'}, status=HTTP_200_OK)

    try:
        cart_id = request.data['order_id']
    except KeyError:
        return Response({'message': 'order_id must be provided'}, status=HTTP_200_OK)

    try:
        payload = request.data['payload']
    except KeyError:
        return Response({'message': 'payload must be provided'}, status=HTTP_200_OK)

    with scopes_disabled():
        try:
            cart = Cart.objects.get(id=cart_id)
        except Cart.DoesNotExist:
            return Response({'message': 'invalid order_id'}, status=HTTP_200_OK)

    if even_type == 'enrollment':
        handle_enrollment_event(payload, cart, request.store)
    elif even_type == 'student':
        handle_student_event(payload, cart, request.store)
    ###
    # and the events goes on and on
    # ....
    ###
    else:
        return Response({'message': 'unrecognized event type'}, status=HTTP_200_OK)

    return Response({'message': 'ok'}, status=HTTP_200_OK)
