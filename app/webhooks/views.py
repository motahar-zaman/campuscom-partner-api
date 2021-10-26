from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK

from publish.permissions import HasStoreAPIKey

from shared_models.models import Cart, StudentProfile, Course, Certificate, CourseEnrollment, CertificateEnrollment, CourseSharingContract
from models.course.course import Course as CourseModel
from models.certificate.certificate import Certificate as CertificateModel
from models.courseprovider.course_provider import CourseProvider as CourseProviderModel
from django_scopes import scopes_disabled


def handle_enrollment_event(payload, cart, store):
    contract = CourseSharingContract.objects.filter(store=store, is_active=True).first()
    course_provider = contract.course_provider
    provider = CourseProviderModel.objects.get(id=course_provider.content_db_reference)

    for item in payload['products']:
        try:
            course_model = CourseModel.objects.get(external_id=item['external_id'], provider=provider)
        except CourseModel.DoesNotExist:
            continue
        else:
            with scopes_disabled():
                course = Course.objects.get(content_db_reference=str(course_model.id))

            enrollment, created = CourseEnrollment.objects.get_or_create(
                profile=cart.profile,
                course=course,
                store=store,
                defaults={
                    'enrollment_time': timezone.now(),
                    'application_time': timezone.now(),
                    'status': 'success'
                }
            )

        try:
            certificate_model = CertificateModel.objects.get(external_id=item['external_id'])
        except Certificate.DoesNotExist:
            continue
        else:
            with scopes_disabled():
                certificate = Certificate.objects.get(content_db_reference=str(certificate_model.id))
            enrollment, created = CertificateEnrollment.objects.get_or_create(
                profile=cart.profile,
                certificate=certificate,
                store=store,
                defaults={
                    'application_time': timezone.now(),
                    'enrollment_time': timezone.now(),
                    'status': 'success'
                }
            )

    return True


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
