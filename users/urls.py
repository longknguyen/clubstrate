from django.urls import path
from .views import *

# Redirect role-admin to role-admin/users
def role_admin_root(request):
    return redirect('user_list')

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("login-redirect/", login_redirect, name="login_redirect"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("friends/", friends_page, name="friends"),
    path("friends/add/", add_friend, name="add_friend"),
    path("friends/dm/<int:friendship_id>/send/", send_direct_message, name="send_direct_message"),
    path("friends/<int:friend_id>/remove/", remove_friend, name="remove_friend"),
    path("friends/requests/<int:request_id>/accept/", accept_friend_request, name="accept_friend_request"),
    path("friends/requests/<int:request_id>/decline/", decline_friend_request, name="decline_friend_request"),
    path("profile/password/", change_password, name="change_password"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("change-role/<int:user_id>/", ChangeRoleView.as_view(), name="change-role"),
    path("register/", RegisterView.as_view(), name="register"),
    path('profile/edit/', ProfileEditView.as_view(), name='profile_edit'),
    path('role-admin/', RoleAdminView.as_view(), name='role_admin'),
    path("role-admin/users/", UserRoleListView.as_view(), name="user_list"),
    path("role-admin/users/<int:user_id>/", UserRoleDetailView.as_view(), name="user_detail"),
    path("role-admin/cios/", CIORoleListView.as_view(), name="cio_list"),
    path("role-admin/cios/<int:cio_id>/", CIORoleDetailView.as_view(), name="role_admin_cio_detail"),
    path('role-admin/membership/<int:membership_id>/change/', ChangeRoleView.as_view(), name='change_role'),
]
