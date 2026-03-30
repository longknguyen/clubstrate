from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('home/', views.home, name='home'),
    path('create/', views.create_cio, name='create_cio'),
    path('<int:cio_id>/', views.cio_detail, name='cio_detail'),
]