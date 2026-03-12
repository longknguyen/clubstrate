from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.views import View


class LoginView(View):
    def get(self, request):
        return render(request, 'users/login.html')

class ProfileView(View):
    @login_required
    def get(self, request):
        user = request.user
        context = {
            "profile_image": user.profile.image.url,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
        }
        return render(request, 'users/profile.html', context)

class LogoutView(View):
    def post(self, request):
        logout(request)
        return redirect('/')

"""def profile(request):
    user = User.objects.get(username="Any")  # This user for now, until login is implemented
    return render(request, "users/profile.html", {"user": user})"""