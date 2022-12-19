from django.db.models.signals import post_save
from django.dispatch import receiver
from shared_models.models import QuestionBank


@receiver(post_save, sender=QuestionBank)
def create_checkout_login_user(sender, instance, created, **kwargs):
    if created:
        print("Question Created")


# post_save.connect(create_checkout_login_user, sender=QuestionBank)


@receiver(post_save, sender=QuestionBank)
def update_checkout_login_user(sender, instance, created, **kwargs):
    if not created:
        print("Question Updated")

# post_save.connect(update_checkout_login_user, sender=QuestionBank)
