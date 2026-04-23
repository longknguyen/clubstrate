from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout, get_user_model, login, authenticate
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib.auth.models import Group
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from image_utils import convert_upload_to_webp
from .forms import (
    PROFILE_FIRST_NAME_MAX_LENGTH,
    PROFILE_LAST_NAME_MAX_LENGTH,
    UserUpdateForm,
    ProfileUpdateForm,
)
import uuid

from .models import Profile

User = get_user_model()


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

            # ✅ NEW: admin redirect
            if user.profile.user_type == "user_admin":
                return redirect('/users/role-admin/')

            return redirect('/')
        else:
            return render(request, 'users/login.html', {
                'error': 'Invalid credentials',
                'identifier': identifier
            })

def mask_email(email):
    name, domain = email.split("@")
    return "*" * len(name) + "@" + domain

@method_decorator(never_cache, name='dispatch')
class ProfileView(LoginRequiredMixin, View):
    login_url = '/users/login/'

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)


        if profile.user_type == "user_admin":
            return redirect('/users/role-admin/')

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
            "section": "profile",
        }
        return render(request, 'users/profile.html', context)

    def post(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        if 'image' in request.FILES:
            profile.image = convert_upload_to_webp(request.FILES['image'], stem='profile')
            profile.save()
        return redirect('/users/profile/')


@method_decorator(never_cache, name='dispatch')
class LogoutView(View):
    def post(self, request):
        logout(request)
        return redirect('/')

class RegisterView(View):
    def get(self, request):
        return render(request, 'users/register.html')

    def post(self, request):
        name = request.POST.get('name', '').strip()
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

        if len(first_name) > PROFILE_FIRST_NAME_MAX_LENGTH or len(last_name) > PROFILE_LAST_NAME_MAX_LENGTH:
            return render(request, 'users/register.html', {
                'error': f'Please keep first and last names under {PROFILE_FIRST_NAME_MAX_LENGTH} characters each.',
                'name': name,
                'email': email,
                'password': password
            })

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
        return redirect('/')

@method_decorator(never_cache, name='dispatch')
class ChangeRoleView(LoginRequiredMixin, View):
    login_url = '/users/login/'

    def post(self, request, user_id):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        if profile.user_type != "user_admin":
            return redirect('/users/profile/')

        target_profile = get_object_or_404(Profile, user_id=user_id)

        if target_profile.user_type == "user_admin":
            return redirect('/users/role-admin/')

        new_role = request.POST.get("user_type")

        if new_role in ["student", "officer"]:
            target_profile.user_type = new_role
            target_profile.save()

        return redirect('/users/role-admin/')


@method_decorator(never_cache, name='dispatch')
class RoleAdminView(LoginRequiredMixin, View):
    login_url = '/users/login/'

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        if profile.user_type != "user_admin":
            return redirect('/')

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
            "role": role,
        })


@method_decorator(never_cache, name='dispatch')
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
            'first_name': user_form['first_name'].value() or '',
            'last_name': user_form['last_name'].value() or '',
            'username': user_form['username'].value() or '',
            'pronouns': user_form['pronouns'].value() or '',
            'banner_colour': user_form['banner_colour'].value() or request.user.banner_colour,
        }
        return render(request, 'users/profile_edit.html', context)

    def post(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()
            if request.POST.get("remove_image") == "1":
                profile.image = "profile_pics/default.jpg"
            elif "image" in request.FILES:
                profile.image = convert_upload_to_webp(request.FILES["image"], stem='profile')

            profile.save()
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
