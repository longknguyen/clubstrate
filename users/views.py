from django.shortcuts import render
from django.contrib.auth.models import User

from django.contrib.auth.decorators import login_required

# @login_required
# def dashboard(request):
#     is_officer = request.user.groups.filter(name='Club Officer').exists()
#     return render(request, 'dashboard.html', {'is_officer': is_officer})

def profile(request):
    is_officer = request.user.groups.filter(name='Club Officer').exists()
    # user = User.objects.get(username="Any")  # This user for now, until login is implemented
    return render(request, "users/profile.html", {'is_officer': is_officer})