from django.contrib import admin
from .models import CIO, Membership, JoinRequest, Event, Reminder

admin.site.register(CIO)
admin.site.register(Membership)
admin.site.register(JoinRequest)
admin.site.register(Event)
admin.site.register(Reminder)