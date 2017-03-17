import logging

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save

log = logging.getLogger()


class UserProfile(models.Model):
    user = models.OneToOneField(User, related_name="profile")
    dolibarr_token = models.CharField(max_length=100)
    cyclos_token = models.CharField(max_length=100)
    firstname = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    companyname = models.CharField(max_length=100)


def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

post_save.connect(create_user_profile, sender=User)
