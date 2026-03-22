from django.conf import settings
from django.db import models


class CIO(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    MEMBER = "member"
    OFFICER = "officer"
    ROLE_CHOICES = [
        (MEMBER, 'Member'),
        (OFFICER, 'Officer'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    cio = models.ForeignKey(CIO, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    class Meta: # can only have one membership per CIO
        unique_together = ('user', 'cio')

    def __str__(self):
        return f'{self.user.username} - {self.cio.name} - {self.get_role_display()}'