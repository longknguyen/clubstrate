from django.conf import settings
from django.db import models
from cios.models import CIO

class Post(models.Model):
    ANNOUNCEMENT = 'announcement'
    DISCUSSION = 'discussion'
    KIND_CHOICES = [
        (ANNOUNCEMENT, 'Announcement'),
        (DISCUSSION, 'Discussion'),
    ]

    cio = models.ForeignKey(CIO, on_delete=models.CASCADE, related_name='posts')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    title = models.CharField(max_length=200, blank=True, default='')
    content = models.TextField()
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=ANNOUNCEMENT)
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='liked_posts', blank=True)

    image = models.ImageField(upload_to='post_images/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or self.content[:40]

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    content = models.TextField()
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='liked_comments', blank=True)
    image = models.ImageField(upload_to='comment_images/', blank=True, null=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    created_at = models.DateTimeField(auto_now_add=True)
