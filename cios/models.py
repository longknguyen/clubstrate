from django.conf import settings
from django.db import models


class CIO(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    # About page fields
    description = models.TextField(blank=True)
    dues = models.CharField(max_length=100, blank=True)
    commitment_level = models.CharField(max_length=100, blank=True)
    time_expectations = models.CharField(max_length=200, blank=True)
    about_image = models.ImageField(upload_to='cio_about_images/', blank=True, null=True)

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


class JoinRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    cio = models.ForeignKey(CIO, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'cio')

    def __str__(self):
        return f'{self.user.username} - {self.cio.name} - {self.status}'