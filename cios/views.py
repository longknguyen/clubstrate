from django.shortcuts import render

def home(request):
    role = None
    if request.user.is_authenticated:
        role = request.user.role
    return render(request, 'cios/home.html', {'role': role})