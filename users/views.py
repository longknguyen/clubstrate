from django.shortcuts import render, redirect
from django.contrib.auth import logout, get_user_model, login, authenticate
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib.auth.models import Group
from .forms import UserUpdateForm, ProfileUpdateForm
import uuid

from .models import Profile

User = get_user_model()


# See https://docs.djangoproject.com/en/6.0/ref/class-based-views/base/ to grab request/return http responses using Django abstractions
class LoginView(View):
    def get(self, request):
        return render(request, 'users/login.html')

    def post(self, request):
        identifier = request.POST.get('email')
        password = request.POST.get('password')

        if '@' in identifier:
            user_obj = User.objects.filter(email=identifier).first()
        else:
            user_obj = User.objects.filter(username=identifier).first()

        if user_obj:
            user = authenticate(request, username=user_obj.username, password=password)
        else:
            user = None

        if user:
            login(request, user)
            return redirect('/users/profile/')
        else:
            return render(request, 'users/login.html', {
                'error': 'Invalid credentials',
                'identifier': identifier
            })

def mask_email(email):
    name, domain = email.split("@")
    return "*" * len(name) + "@" + domain

class ProfileView(LoginRequiredMixin, View):
    login_url = '/users/login/'

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        # user = request.user

        # Get the image URL - ensures S3 URL is properly generated
        profile_image_url = profile.image.url if profile.image else '/media/default.jpg'

        context = {
            "profile_image": profile_image_url,
            "username": request.user.username,
            "email_masked": mask_email(request.user.email),
            "email": request.user.email,
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "banner_colour": request.user.banner_colour,
            "role": "officer" if request.user.groups.filter(name='Officer').exists() else "member",
        }
        return render(request, 'users/profile.html', context)

    def post(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        if 'image' in request.FILES:
            profile.image = request.FILES['image']
            profile.save()
        return redirect('/users/profile/')


class LogoutView(View):
    def post(self, request):
        logout(request)
        return redirect('/')

class RegisterView(View):
    def get(self, request):
        return render(request, 'users/register.html')

    def post(self, request):
        name = request.POST.get('name')
        email = request.POST.get('email')
        password = request.POST.get('password')

        if User.objects.filter(email=email).exists():
            return render(request, 'users/register.html', {
                'error': 'Email already in use',
                'name': name,
                'password': password
            })

        first_name = name.split(' ')[0] if name else ''
        last_name = " ".join(name.split()[1:]) if name and len(name.split()) > 1 else ''

        username = email.split('@')[0]
        if User.objects.filter(username=username).exists():
            username = f"{username}{uuid.uuid4().hex[:5]}"
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('/users/profile/')


class ChangeRoleView(LoginRequiredMixin, View):
    login_url = '/users/login/'

    def post(self, request):
        user = request.user
        officer_group = Group.objects.get(name='Officer')
        member_group = Group.objects.get(name='Member')
        if user.groups.filter(name='Officer').exists():
            user.groups.remove(officer_group)
            user.groups.add(member_group)
        else:
            user.groups.remove(member_group)
            user.groups.add(officer_group)
        user.save()
        return redirect('/users/profile/')

class ProfileEditView(LoginRequiredMixin, View):
    login_url = '/users/login/'

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=profile)

        context = {
            'user_form': user_form,
            'profile_form': profile_form,
            'profile_image': profile.image.url if profile.image else '/media/default.jpg',
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'username': request.user.username,
            'pronouns': request.user.pronouns,
            'banner_colour': request.user.banner_colour,
        }
        return render(request, 'users/profile_edit.html', context)

    def post(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()
            profile_form.save()
            return redirect('/users/profile/')

        context = {
            'user_form': user_form,
            'profile_form': profile_form,
            'profile_image': profile.image.url if profile.image else '/media/default.jpg',
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'username': request.user.username,
            'pronouns': request.user.pronouns,
            'banner_colour': request.user.banner_colour,
        }
        return render(request, 'users/profile_edit.html', context)



"""def profile(request):
    user = User.objects.get(username="Any")  # This user for now, until login is implemented
    return render(request, "users/profile.html", {"user": user})"""
