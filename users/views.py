from django.shortcuts import render
from django.contrib.auth.models import User

def profile(request):
    user = User.objects.get(username="Any")  # This user for now, until login is implemented
    return render(request, "users/profile.html", {"user": user})