from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('home/', views.home, name='home'),
    path('create/', views.create_cio, name='create_cio'),
    path('<int:cio_id>/', views.cio_detail, name='cio_detail'),
    path('<int:cio_id>/request-to-join/', views.request_to_join, name='request-to-join'),
    path('<int:cio_id>/cancel-request/', views.cancel_join_request, name='cancel-join-request'),
    path('request/<int:request_id>/accept/', views.accept_request, name='accept-request'),
    path('request/<int:request_id>/deny/', views.deny_request, name='deny-request'),
]
