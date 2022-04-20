from notifications.serializers import PaymentSerializer
from models.course.course import Course as CourseModel
from shared_models.models import Payment, CourseEnrollment, QuestionBank, StudentProfile
from django.core.exceptions import ValidationError


def format_notification_response(cart, course_enrollment = None):
    data = {}
    enrollment_data = []
    payment_data = None
    agreement_details = {}

    try:
        payment = Payment.objects.get(cart=cart)
    except Payment.DoesNotExist:
        pass
    else:
        payment_data = PaymentSerializer(payment).data

        for key, val in payment.cart.agreement_details.items():
            try:
                question = QuestionBank.objects.get(id=key)
            except (QuestionBank.DoesNotExist, ValidationError):
                continue
            agreement_details[question.external_id] = val

    if course_enrollment:
        enrollment_data.append(format_course_enrollment_data(course_enrollment, payment, cart.profile))
    else:
        try:
            course_enrollment = CourseEnrollment.objects.filter(cart_item__cart=cart)
        except CourseEnrollment.DoesNotExist:
            pass
        else:
            for enrollment in course_enrollment:
                enrollment_data.append(format_course_enrollment_data(enrollment, payment, cart.profile))

    data['order_id'] = str(cart.order_ref)
    data['enrollments'] = enrollment_data
    data['payment'] = payment_data
    data['agreement_details'] = agreement_details

    return data


def format_course_enrollment_data(course_enrollment, payment, profile):
    data = {}

    # getting section external_id from mongo section data
    external_id = None
    try:
        course_model = CourseModel.objects.get(pk=course_enrollment.course.content_db_reference) #mongo course data
    except CourseModel.DoesNotExist:
        pass
    else:
        for section_model in course_model.sections:
            if section_model.code == course_enrollment.section.name:
                external_id = section_model.external_id
                break

    # getting registration info
    registration_details = {}
    reg_info = {}
    for reg_detail in payment.cart.registration_details:
        try:
            if profile.primary_email == reg_detail['student'] and str(course_enrollment.cart_item.product.id) == \
                    reg_detail['product_id']:
                reg_info = reg_detail['data']
        except KeyError:
            pass

    for key, val in reg_info.items():
        try:
            question = QuestionBank.objects.get(id=key)
        except (QuestionBank.DoesNotExist, ValidationError):
            continue
        registration_details[question.external_id] = val

    # getting student id
    school_student_id = ''
    student_profiles = StudentProfile.objects.filter(profile=profile)
    if student_profiles.exists():
        school_student_id = student_profiles.first().external_profile_id

    # getting profile info
    extra_info = {}
    profile_details = {}

    for profile_data in payment.cart.student_details:
        try:
            if profile.primary_email == profile_data['email'] and str(course_enrollment.cart_item.product.id) == \
                    profile_data['product_id']:
                extra_info = profile_data['extra_info']
        except KeyError:
            pass

    for key, val in extra_info.items():
        try:
            question = QuestionBank.objects.get(id=key)
        except (QuestionBank.DoesNotExist, ValidationError):
            continue
        profile_details[question.external_id] = val

    data['external_id'] = external_id
    data['enrollment_id'] = course_enrollment.ref_id
    data['product_type'] = 'section'
    data['registration_details'] = registration_details
    data['student'] = {
        'school_student_id': school_student_id,
        'email': course_enrollment.profile.primary_email,
        'first_name': course_enrollment.profile.first_name,
        'last_name': course_enrollment.profile.last_name,
        'profile_details': profile_details
    }
    return data
