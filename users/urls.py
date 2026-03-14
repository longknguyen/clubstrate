from django.urls import path
from .views import LoginView, ProfileView, LogoutView, ChangeRoleView

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("change-role/", ChangeRoleView.as_view(), name="change-role"),
]