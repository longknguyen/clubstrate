from django.urls import path
from .views import LoginView, ProfileView, LogoutView, RegisterView, ChangeRoleView

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("change-role/", ChangeRoleView.as_view(), name="change-role"),
    path("register/", RegisterView.as_view(), name="register"),
]