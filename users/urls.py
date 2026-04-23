from django.urls import path
from .views import *

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("friends/", friends_page, name="friends"),
    path("friends/add/", add_friend, name="add_friend"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("change-role/<int:user_id>/", ChangeRoleView.as_view(), name="change-role"),
    path("register/", RegisterView.as_view(), name="register"),
    path('profile/edit/', ProfileEditView.as_view(), name='profile_edit'),
    path("role-admin/", RoleAdminView.as_view(), name="role-admin"),
]
