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
from django.contrib.auth.models import User


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(default='default.jpg', upload_to='profile_pics')

    def __str__(self):
        return f'{self.user.username} Profile'