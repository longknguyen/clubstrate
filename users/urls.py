from django.urls import path
from django.contrib.auth import views as auth_views
from .views import LoginView, ProfileView, LogoutView, RegisterView, ChangeRoleView, RoleAdminView

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("logout/", auth_views.LogoutView.as_view(next_page="/"), name="logout"),
    path("register/", RegisterView.as_view(), name="register"),
    path("role-admin/", RoleAdminView.as_view(), name="role-admin"),
    path("update-role/<int:user_id>/", ChangeRoleView.as_view(), name="update-role"),
]