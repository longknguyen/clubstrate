from django.contrib import admin
from .models import CIO, Membership, JoinRequest

admin.site.register(CIO)
admin.site.register(Membership)
admin.site.register(JoinRequest)