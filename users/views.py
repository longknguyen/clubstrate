from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout, get_user_model, login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib.auth.models import Group
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from urllib.parse import quote_plus
from image_utils import convert_upload_to_webp
from .forms import (
    PROFILE_FIRST_NAME_MAX_LENGTH,
    PROFILE_LAST_NAME_MAX_LENGTH,
    UserUpdateForm,
    ProfileUpdateForm,
)
import uuid

from .models import Profile, Friendship, DirectMessage

User = get_user_model()
DM_GROUP_GAP = timedelta(minutes=5)


def _display_name_for_user(user):
    full_name = f"{user.first_name} {user.last_name}".strip()
    return full_name or user.username


def _friendship_queryset_for_user(user):
    return Friendship.objects.filter(Q(user_one=user) | Q(user_two=user)).select_related(
        'user_one__profile',
        'user_two__profile',
    )


def _friendship_for_users(user, other_user):
    user_one_id, user_two_id = sorted([user.id, other_user.id])
    return Friendship.objects.filter(user_one_id=user_one_id, user_two_id=user_two_id).first()


def _friend_count(user):
    return _friendship_queryset_for_user(user).count()


def _time_divider_label(created_at):
    local_dt = timezone.localtime(created_at)
    message_date = local_dt.date()
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)

    if message_date == today:
        prefix = "Today"
    elif message_date == yesterday:
        prefix = "Yesterday"
    else:
        prefix = local_dt.strftime("%d %B %Y")

    return f"{prefix} • {local_dt.strftime('%-I:%M %p')}"


def _attach_dm_grouping(messages):
    for idx, message in enumerate(messages):
        previous_message = messages[idx - 1] if idx > 0 else None
        next_message = messages[idx + 1] if idx + 1 < len(messages) else None

        within_gap_of_previous = (
            previous_message is not None
            and message.created_at - previous_message.created_at <= DM_GROUP_GAP
        )
        within_gap_of_next = (
            next_message is not None
            and next_message.created_at - message.created_at <= DM_GROUP_GAP
        )

        same_as_previous = (
            previous_message is not None
            and previous_message.sender_id == message.sender_id
            and previous_message.created_at.date() == message.created_at.date()
            and within_gap_of_previous
        )
        same_as_next = (
            next_message is not None
            and next_message.sender_id == message.sender_id
            and next_message.created_at.date() == message.created_at.date()
            and within_gap_of_next
        )

        message.show_time_divider = (
            previous_message is None
            or message.created_at.date() != previous_message.created_at.date()
            or message.created_at - previous_message.created_at > DM_GROUP_GAP
        )
        message.time_divider_label = _time_divider_label(message.created_at)
        message.show_header = not same_as_previous
        message.show_avatar = not same_as_next
        message.display_name = _display_name_for_user(message.sender)

    return messages


def _friend_sidebar_items(user):
    friendships = list(_friendship_queryset_for_user(user))
    items = []
    for friendship in friendships:
        other_user = friendship.other_user(user)
        latest_message = friendship.messages.select_related('sender').order_by('-created_at').first()
        items.append({
            'friendship': friendship,
            'friend': other_user,
            'display_name': _display_name_for_user(other_user),
            'latest_activity': latest_message.created_at if latest_message else friendship.created_at,
        })
    items.sort(key=lambda item: item['latest_activity'], reverse=True)
    return items


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
            user_form.save()
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


@login_required
def friends_page(request):
    section = request.GET.get('section', 'all')
    dm_user_id = request.GET.get('dm')
    notice = request.GET.get('notice', '')

    friend_items = _friend_sidebar_items(request.user)
    accepted_friends = []
    for item in friend_items:
        friend = item['friend']
        accepted_friends.append({
            'id': friend.id,
            'display_name': item['display_name'],
            'username': friend.username,
            'image_url': friend.profile.image.url,
            'banner_colour': friend.banner_colour,
        })

    selected_friend = None
    selected_friendship = None
    direct_messages = []

    if dm_user_id:
        selected_friend = get_object_or_404(User.objects.select_related('profile'), pk=dm_user_id)
        selected_friendship = _friendship_for_users(request.user, selected_friend)
        if selected_friendship:
            messages = list(
                selected_friendship.messages.select_related('sender', 'sender__profile').order_by('created_at')
            )
            direct_messages = _attach_dm_grouping(messages)
            section = 'dm'
        else:
            selected_friend = None

    context = {
        'accepted_friends': accepted_friends,
        'friend_items': friend_items,
        'section': section,
        'selected_friend': selected_friend,
        'selected_friendship': selected_friendship,
        'direct_messages': direct_messages,
        'notice': notice,
        'friend_count': len(accepted_friends),
        'friend_limit': 100,
    }
    return render(request, 'users/friends.html', context)


@login_required
def add_friend(request):
    if request.method != 'POST':
        return redirect(f"{reverse('friends')}?section=add")

    username = request.POST.get('username', '').strip().lstrip('@')
    redirect_url = f"{reverse('friends')}?section=add"

    if not username:
        return redirect(f"{redirect_url}&notice={quote_plus('Enter a username to add.')}")

    try:
        target_user = User.objects.get(username__iexact=username)
    except User.DoesNotExist:
        return redirect(f"{redirect_url}&notice={quote_plus('No user found with that username.')}")

    if target_user == request.user:
        return redirect(f"{redirect_url}&notice={quote_plus('You cannot add yourself.')}")

    if _friendship_for_users(request.user, target_user):
        return redirect(f"{redirect_url}&notice={quote_plus('You are already friends.')}")

    if _friend_count(request.user) >= 100 or _friend_count(target_user) >= 100:
        return redirect(f"{redirect_url}&notice={quote_plus('One of these accounts has reached the 100 friend limit.')}")

    Friendship.objects.create(user_one=request.user, user_two=target_user)
    return redirect(f"{reverse('friends')}?section=all&notice={quote_plus('Friend added.')}")
