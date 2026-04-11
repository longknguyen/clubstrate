from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
#from django.contrib.auth.models import Group


from .models import Profile


# See https://docs.djangoproject.com/en/6.0/ref/class-based-views/base/ to grab request/return http responses using Django abstractions
class LoginView(View):
    def get(self, request):
        return render(request, 'users/login.html')


class ProfileView(LoginRequiredMixin, View):
    login_url = '/users/login/'

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        # user = request.user
        context = {
            "profile_image": profile.image.url,
            "username": request.user.username,
            "email": request.user.email,
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "role": "officer" if request.user.groups.filter(name='Officer').exists() else "member",
        }
        return render(request, 'users/profile.html', context)


class LogoutView(View):
    def post(self, request):
        logout(request)
        return redirect('/')

class RegisterView(View):
    def get(self, request):
        return render(request, 'users/register.html')

class RoleAdminView(LoginRequiredMixin, View):
    login_url = '/users/login/'

    def get(self, request):
        profile = request.user.profile

        # Restrict Access
        if profile.user_type != "user_admin":
            return redirect('/users/profile/')

        users = Profile.objects.all()
        return render(request, "users/role_admin.html", {"users": users})

class ChangeRoleView(LoginRequiredMixin, View):
    login_url = '/users/login/'

    def post(self, request, user_id):
        profile = request.user.profile

        # Restrict Access
        if profile.user_type != "user_admin":
            return redirect('/users/profile/')

        target_profile = Profile.objects.get(user_id=user_id)

        new_role = request.POST.get("user_type")

        # Block self-assignment
        if new_role == "user_admin":
            return redirect('/users/role-admin/')

        # Only allow valid roles
        if new_role in ["student", "president"]:
            target_profile.user_type = new_role
            target_profile.save()

        return redirect('/users/role-admin/')

# class ChangeRoleView(LoginRequiredMixin, View):
#     login_url = '/users/login/'
#
#     def post(self, request):
#         user = request.user
#         officer_group = Group.objects.get(name='Officer')
#         member_group = Group.objects.get(name='Member')
#         if user.groups.filter(name='Officer').exists():
#             user.groups.remove(officer_group)
#             user.groups.add(member_group)
#         else:
#             user.groups.remove(member_group)
#             user.groups.add(officer_group)
#         user.save()
#         return redirect('/users/profile/')


"""def profile(request):
    user = User.objects.get(username="Any")  # This user for now, until login is implemented
    return render(request, "users/profile.html", {"user": user})"""
