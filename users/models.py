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
    pronouns = models.CharField(max_length=50, blank=True)
    banner_colour = models.CharField(max_length=7, default='#000000')
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.username

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    # role_choices = [ ('member', 'Club Member'), ('officer', 'Club Officer')]
    # role = models.CharField(max_length=20, choices=role_choices, default='member')


class Profile(models.Model):
    USER_TYPES = (
        ('viewer', 'Viewer'),
        ('member', 'Member'),
        ('officer', 'CIO Officer'),
        ('user_admin', 'User Administrator'),
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    image = models.ImageField(default='profile_pics/default.jpg', upload_to='profile_pics')
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='viewer')

    def __str__(self):
        return f'{self.user.username} Profile'


class Friendship(models.Model):
    user_one = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='friendships_started',
    )
    user_two = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='friendships_received',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user_one', 'user_two'], name='unique_friendship_pair'),
        ]

    def save(self, *args, **kwargs):
        if self.user_one_id and self.user_two_id and self.user_one_id > self.user_two_id:
            self.user_one_id, self.user_two_id = self.user_two_id, self.user_one_id
        super().save(*args, **kwargs)

    def other_user(self, user):
        if user.id == self.user_one_id:
            return self.user_two
        return self.user_one

    def includes(self, user):
        return user.id in {self.user_one_id, self.user_two_id}

    def __str__(self):
        return f'{self.user_one.username} ↔ {self.user_two.username}'


class FriendRequest(models.Model):
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    DECLINED = 'declined'
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (ACCEPTED, 'Accepted'),
        (DECLINED, 'Declined'),
    ]

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_friend_requests',
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_friend_requests',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['sender', 'recipient'], name='unique_friend_request_pair'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.sender.username} → {self.recipient.username} ({self.status})'


class DirectMessage(models.Model):
    friendship = models.ForeignKey(Friendship, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_direct_messages')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender.username}: {self.content[:40]}'


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(sender, instance, **kwargs):
    # instance.profile.save()
    Profile.objects.get_or_create(user=instance)
