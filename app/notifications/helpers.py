from notifications.serializers import PaymentSerializer
from models.course.course import Course as CourseModel
from shared_models.models import Payment, CourseEnrollment, QuestionBank, StudentProfile, RelatedProduct, CartItem, \
    StoreConfiguration, Section
from django.core.exceptions import ValidationError


def format_notification_response(cart, course_enrollment=[]):
    data = {}
    enrollment_data = []
    payment_data = None
    agreement_details = {}

    # create the notification details with necessary information
    additional_products, associated_products, enable_standalone_product_checkout, enable_registration_product_checkout \
        = format_related_products_data(cart)
    try:
        payment = Payment.objects.get(cart=cart)
    except Payment.DoesNotExist:
        pass
    else:
        payment_data = PaymentSerializer(payment).data

        for key, val in cart.agreement_details.items():
            try:
                question = QuestionBank.objects.get(id=key)
            except (QuestionBank.DoesNotExist, ValidationError):
                continue
            agreement_details[question.external_id] = val

    if not course_enrollment:
        try:
            course_enrollment = CourseEnrollment.objects.filter(cart_item__cart=cart)
        except CourseEnrollment.DoesNotExist:
            pass

    for enrollment in course_enrollment:
        formatted_enrollment_data = format_course_enrollment_data(enrollment, payment, cart.profile)

        # append registration type related products' information with the related student(enrollment)
        if enable_registration_product_checkout:
            formatted_enrollment_data['associated_products'] = []
            for associated_product in associated_products:
                if str(associated_product['parent']) == str(formatted_enrollment_data['product_id']):
                    product_data = associated_product.copy()
                    product_data.pop('parent')
                    formatted_enrollment_data['associated_products'].append(product_data)
        enroll_data = formatted_enrollment_data.copy()
        enroll_data.pop('product_id')
        enrollment_data.append(enroll_data)

    data['order_id'] = str(cart.order_ref)
    data['enrollments'] = enrollment_data
    data['payment'] = payment_data
    data['agreement_details'] = agreement_details
    if enable_standalone_product_checkout:
        data['additional_products'] = additional_products

    return data


def format_course_enrollment_data(course_enrollment, payment, profile):
    data = {}

    # getting section external_id from mongo section data
    external_id = None
    try:
        course_model = CourseModel.objects.get(pk=course_enrollment.course.content_db_reference)  # mongo course data
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

    data['product_id'] = course_enrollment.cart_item.product.id
    data['external_id'] = external_id
    data['enrollment_id'] = course_enrollment.ref_id
    data['enrollment_status'] = course_enrollment.status
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


def format_related_products_data(cart):
    additional_products = []
    associated_products = []

    enable_standalone_product_checkout = False
    enable_registration_product_checkout = False

    # find store configuration to get if the store is enabled for related products
    try:
        store_config = StoreConfiguration.objects.get(
            store=cart.store,
            external_entity__entity_type='enrollment_config',
            external_entity__entity_name='Checkout Configuration'
        )
    except Exception:
        pass
    else:
        enable_standalone_product_checkout = store_config.config_value['enable_standalone_product_checkout']
        enable_registration_product_checkout = store_config.config_value['enable_registration_product_checkout']

        # if enabled, then find out the related products necessary information
        if enable_standalone_product_checkout or enable_registration_product_checkout:
            for product in cart.cart_details:
                if product['is_related']:
                    relation_type = ''
                    if product['student_email']:
                        relation_type = 'registration'
                    else:
                        relation_type = 'standalone'
                    try:
                        cart_item = CartItem.objects.filter(
                            cart=cart,
                            product=product['product_id'],
                            parent_product=product['related_to']
                        )
                        item = cart_item[0]
                    except Exception:
                        continue
                    else:
                        related_product_info = {
                            'external_id': item.product.external_id,
                            'quantity': product['quantity'],
                            'product_type': item.product.product_type,
                            'unit_price': item.unit_price,
                            'discount': item.discount_amount,
                            'sales_tax': item.sales_tax
                        }

                        if relation_type == 'standalone':
                            additional_products.append(related_product_info)
                        else:
                            related_product_info['student_email'] = product['student_email']
                            related_product_info['parent'] = product['related_to']
                            associated_products.append(related_product_info)

    return additional_products, associated_products, enable_standalone_product_checkout, \
           enable_registration_product_checkout
