from django.shortcuts import render

def home(request):
    role = None
    if request.user.is_authenticated:
        role = "officer" if request.user.groups.filter(name='Officer').exists() else "member"
    return render(request, 'cios/home.html', {'role': role})