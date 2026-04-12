from django.shortcuts import render, redirect
from django.contrib.auth import logout, authenticate, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.db.models import Q
from django.shortcuts import get_object_or_404
#from django.contrib.auth.models import Group


from .models import Profile


# See https://docs.djangoproject.com/en/6.0/ref/class-based-views/base/ to grab request/return http responses using Django abstractions
class LoginView(View):
    def get(self, request):
        return render(request, 'users/login.html')

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            if user.profile.user_type == "user_admin":
                return redirect('home')   # admins go to home

            next_url = request.POST.get('next')
            if next_url:
                return redirect(next_url)  # others go to profile

            return redirect('profile')
        # if login fails
        return render(request, 'users/login.html', {
            'error': 'Invalid username or password'
        })

class ProfileView(LoginRequiredMixin, View):
    login_url = '/users/login/'

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)

        # Block profile view from admins
        if request.user.profile.user_type == "user_admin":
            return redirect('home')

        context = {
            "profile_image": profile.image.url,
            "username": request.user.username,
            "email": request.user.email,
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "role": "officer" if request.user.groups.filter(name='Officer').exists() else "member",
        }
        return render(request, 'users/profile.html', context)

class HomeView(View):
    def get(self, request):
        if request.user.is_authenticated and request.user.profile.user_type == "user_admin":
            return redirect("/users/role-admin/")
        return render(request, "home.html")

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

        if request.user.profile.user_type != "user_admin":
            return redirect("/")

        query = request.GET.get("q", "")
        role = request.GET.get("role", "")

        users = Profile.objects.exclude(user_type="user_admin")

        if query:
            users = users.filter(
                Q(user__username__icontains=query) |
                Q(user__email__icontains=query)
            )

        if role:
            users = users.filter(user_type=role)

        return render(request, "users/role_admin.html", {
            "users": users,
            "query": query,
            "role": role
        })

class ChangeRoleView(LoginRequiredMixin, View):
    login_url = '/users/login/'

    def post(self, request, user_id):

        if request.user.profile.user_type != "user_admin":
            return redirect('/users/profile/')

        target_profile = get_object_or_404(Profile, user_id=user_id)

        # block editing admin accounts
        if target_profile.user_type == "user_admin":
            return redirect('/users/role-admin/')

        new_role = request.POST.get("user_type")

        # block assigning admin role
        if new_role == "user_admin":
            return redirect('/users/role-admin/')

        if new_role in ["student", "president"]:
            target_profile.user_type = new_role
            target_profile.save()

        return redirect('/users/role-admin/')

"""def profile(request):
    user = User.objects.get(username="Any")  # This user for now, until login is implemented
    return render(request, "users/profile.html", {"user": user})"""
