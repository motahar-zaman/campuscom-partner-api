from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK

from publish.permissions import HasStoreAPIKey

from shared_models.models import Cart, StudentProfile, Course, Certificate, CourseEnrollment, CertificateEnrollment


def handle_enrollment_event(payload, cart, store):
    for item in payload['products']:
        try:
            course = Course.objects.get(external_id=payload['external_id'])
        except Course.DoesNotExist:
            try:
                certificate = Certificate.objects.get(external_id=payload['external_id'])
            except Certificate.DoesNotExist:
                pass
            else:
                enrollment = CertificateEnrollment.objects.create(
                    profile=cart.profile,
                    certificate=certificate,
                    store=store,
                    application_time=timezone.now(),
                    enrollment_time=timezone.now(),
                    status='success'
                )

        else:
            enrollment = CourseEnrollment.objects.create(
                profile=cart.profile,
                course=course,
                enrollment_time=timezone.now(),
                application_time=timezone.now(),
                status='success',
                store=store
            )

    return enrollment


def handle_student_event(payload, cart, store):
    try:
        student_profile = StudentProfile.objects.get(profile=cart.profile, store=store)
    except StudentProfile.DoesNotExist:
        pass
    else:
        student_profile.external_profile_id = str(payload['school_student_id'])
        student_profile.save()


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
