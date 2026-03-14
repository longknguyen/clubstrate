from django.urls import path
from .views import LoginView, ProfileView, LogoutView

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("logout/", LogoutView.as_view(), name="logout"),
]