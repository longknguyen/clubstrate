from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View

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
            "role": request.user.role,
        }
        return render(request, 'users/profile.html', context)

class LogoutView(View):
    def post(self, request):
        logout(request)
        return redirect('/')

class ChangeRoleView(LoginRequiredMixin, View):
    login_url = '/users/login/'
    def post(self, request):
        user = request.user
        if user.role == 'member':
            user.role = "officer"
        else:
            user.role = 'member'
        user.save()
        return redirect('/users/profile/')


"""def profile(request):
    user = User.objects.get(username="Any")  # This user for now, until login is implemented
    return render(request, "users/profile.html", {"user": user})"""