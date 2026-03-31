# Source / AI Citation
# Description: Django Profile model extending the built-in User model with profile image support.
# Source: Adapted from Corey Schafer's YouTube tutorial
#   "Python Django Tutorial: Full-Featured Web App Part 8 - User Profile and Picture"
#   (https://www.youtube.com/)
#   and GitHub code repository by Corey Schafer
#   (https://github.com/CoreyMSchafer/code_snippets/blob/master/Django_Blog/08-Profile-And-Images/django_project/users/models.py)
# AI Use: None
# Notes: Modified to fit this project's users app and file organization.

from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver

# Used https://docs.djangoproject.com/en/6.0/topics/auth/customizing/#django.contrib.auth.models.AbstractUser to subclass Django's abstractions
class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    def __str__(self):
        return self.username

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    # role_choices = [ ('member', 'Club Member'), ('officer', 'Club Officer')]
    # role = models.CharField(max_length=20, choices=role_choices, default='member')

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    image = models.ImageField(default='default.jpg', upload_to='profile_pics')

    def __str__(self):
        return f'{self.user.username} Profile'

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

