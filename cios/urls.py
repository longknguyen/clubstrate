from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('home/', views.home, name='home'),
    path('create/', views.create_cio, name='create_cio'),
    path('<int:cio_id>/', views.cio_detail, name='cio_detail'),
    path('<int:cio_id>/request-to-join/', views.request_to_join, name='request-to-join'),
    path('request/<int:request_id>/accept/', views.accept_request, name='accept-request'),
    path('<int:cio_id>/calendar/', views.cio_calendar, name='cio_calendar'),
    path('<int:cio_id>/calendar/add-event/', views.add_event, name='add_event'),
    path('events/<int:event_id>/toggle-reminder/', views.toggle_reminder, name='toggle_reminder'),
]