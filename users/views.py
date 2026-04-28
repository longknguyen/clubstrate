from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import logout, get_user_model, login, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib.auth.models import Group
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta
from urllib.parse import quote_plus
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from image_utils import convert_upload_to_webp
from .forms import (
    PROFILE_FIRST_NAME_MAX_LENGTH,
    PROFILE_LAST_NAME_MAX_LENGTH,
    PasswordChangePopupForm,
    UserUpdateForm,
    ProfileUpdateForm,
)
import uuid

from .models import Profile, Friendship, FriendRequest, DirectMessage
from cios.models import Membership, CIO


User = get_user_model()
DM_GROUP_GAP = timedelta(minutes=5)
FRIEND_LIMIT = 100

def login_redirect(request):
    if request.user.profile.user_type == "user_admin":
        return redirect("/users/role-admin/")
    return redirect("/home/")

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


def _create_friendship(user, other_user):
    user_one_id, user_two_id = sorted([user.id, other_user.id])
    friendship, _ = Friendship.objects.get_or_create(user_one_id=user_one_id, user_two_id=user_two_id)
    return friendship


def _pending_friend_requests_for_user(user):
    return FriendRequest.objects.filter(
        recipient=user,
        status=FriendRequest.PENDING,
    ).select_related('sender', 'sender__profile')


def _sent_pending_friend_request(user, target_user):
    return FriendRequest.objects.filter(
        sender=user,
        recipient=target_user,
        status=FriendRequest.PENDING,
    ).first()


def _received_pending_friend_request(user, sender_user):
    return FriendRequest.objects.filter(
        sender=sender_user,
        recipient=user,
        status=FriendRequest.PENDING,
    ).first()


def _friend_request_row_context(friend_request):
    sender = friend_request.sender
    return {
        'id': friend_request.id,
        'display_name': _display_name_for_user(sender),
        'username': sender.username,
        'image_url': sender.profile.image.url,
        'created_at': friend_request.created_at,
    }


def _friend_row_context(user):
    return {
        'id': user.id,
        'display_name': _display_name_for_user(user),
        'username': user.username,
        'image_url': user.profile.image.url,
    }


def _friend_sidebar_item_context(friendship, viewer):
    other_user = friendship.other_user(viewer)
    return {
        'friend_id': other_user.id,
        'display_name': _display_name_for_user(other_user),
        'image_url': other_user.profile.image.url,
    }


def _send_friend_request_event(user_id, event_type, payload):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    async_to_sync(channel_layer.group_send)(
        f"friend_requests_{user_id}",
        {
            'type': 'friend.request.event',
            'event_type': event_type,
            'payload': payload,
        },
    )


def _send_friend_request_created(friend_request):
    request_item = _friend_request_row_context(friend_request)
    html = render_to_string(
        'users/partials/friend_request_row.html',
        {'request_item': request_item},
    )
    _send_friend_request_event(
        friend_request.recipient_id,
        'request_created',
        {
            'request_id': friend_request.id,
            'html': html,
        },
    )


def _send_friend_request_removed(user_id, request_id):
    _send_friend_request_event(
        user_id,
        'request_removed',
        {
            'request_id': request_id,
        },
    )


def _send_friend_added(user, other_user):
    friendship = _friendship_for_users(user, other_user)
    if not friendship:
        return

    friend_item = _friend_row_context(other_user)
    friend_html = render_to_string(
        'users/partials/friend_list_row.html',
        {'friend': friend_item},
    )
    sidebar_html = render_to_string(
        'users/partials/friend_sidebar_item.html',
        {'item': _friend_sidebar_item_context(friendship, user)},
    )
    _send_friend_request_event(
        user.id,
        'friend_added',
        {
            'friend_id': other_user.id,
            'friend_html': friend_html,
            'sidebar_html': sidebar_html,
        },
    )


def _send_friend_removed(user_id, friend_id):
    _send_friend_request_event(
        user_id,
        'friend_removed',
        {
            'friend_id': friend_id,
        },
    )


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

        user = None
        if user_obj:
            user = authenticate(request, username=user_obj.username, password=password)

        if user:
            login(request, user)

            if user.profile.user_type == "user_admin":
                return redirect('/users/role-admin/')

            return redirect('/home/')

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


@login_required
def change_password(request):
    if request.method != 'POST':
        return redirect('profile')

    form = PasswordChangePopupForm(request.user, request.POST)
    if form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        return JsonResponse({
            'ok': True,
            'message': 'Password changed successfully.',
        })

    return JsonResponse({
        'ok': False,
        'errors': form.errors.get_json_data(),
        'non_field_errors': form.non_field_errors(),
    }, status=400)


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

    def post(self, request, membership_id):
        profile, _ = Profile.objects.get_or_create(user=request.user)

        if profile.user_type != "user_admin":
            return redirect('/')

        membership = get_object_or_404(Membership, id=membership_id)

        redirect_type = request.POST.get("redirect_type", "users")

        new_role = request.POST.get("role")

        # Allow role changes including viewer
        if new_role in ["member", "officer", "viewer"]:
            membership.role = new_role
            membership.save()

        return self._redirect_back(redirect_type, membership)

    def _redirect_back(self, redirect_type, membership):
        if redirect_type == "cio":
            return redirect(f'/users/role-admin/cios/{membership.cio.id}/')
        return redirect(f'/users/role-admin/users/{membership.user.id}/')

@method_decorator(never_cache, name='dispatch')
class RoleAdminView(LoginRequiredMixin, View):
    login_url = '/users/login/'

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)

        if profile.user_type != "user_admin":
            return redirect('/')

        query = request.GET.get("q", "")

        # USERS
        users = User.objects.exclude(profile__user_type="user_admin")

        # CIOS
        cios = CIO.objects.all()

        if query:
            users = users.filter(
                Q(username__icontains=query) |
                Q(email__icontains=query)
            )
            cios = cios.filter(name__icontains=query)

        return render(request, "users/user_search.html", {
            "users": users,
            "cios": cios,
            "query": query,
        })

class UserRoleListView(LoginRequiredMixin, View):
    login_url = '/users/login/'

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)

        if profile.user_type != "user_admin":
            return redirect('/')

        query = request.GET.get("q", "")

        users = User.objects.exclude(id=request.user.id).exclude(profile__user_type="user_admin")

        if query:
            users = users.filter(
                username__icontains=query
            ) | users.filter(
                first_name__icontains=query
            ) | users.filter(
                last_name__icontains=query
            )

        return render(request, "users/user_search.html", {
            "users": users,
            "query": query,
        })

class UserRoleDetailView(LoginRequiredMixin, View):
    login_url = '/users/login/'

    def get(self, request, user_id):
        profile, _ = Profile.objects.get_or_create(user=request.user)

        if profile.user_type != "user_admin":
            return redirect('/')

        target_user = get_object_or_404(User, id=user_id)

        memberships = Membership.objects.filter(
            user=target_user
        ).select_related("cio")

        return render(request, "users/user_role_detail.html", {
            "target_user": target_user,
            "memberships": memberships,
        })

class CIORoleDetailView(LoginRequiredMixin, View):
    def get(self, request, cio_id):
        cio = get_object_or_404(CIO, id=cio_id)

        memberships = Membership.objects.filter(
            cio=cio
        ).exclude(
            role="viewer"
        ).select_related("user")

        return render(request, "users/cio_role_detail.html", {
            "cio": cio,
            "memberships": memberships,
        })

class CIORoleListView(LoginRequiredMixin, View):
    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)

        if profile.user_type != "user_admin":
            return redirect('/')

        query = request.GET.get("q", "")

        cios = CIO.objects.all()

        if query:
            cios = cios.filter(
                Q(name__icontains=query)
            )

        return render(request, "users/cio_list.html", {
            "cios": cios,
            "query": query,
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
    notice_type = request.GET.get('notice_type', '')

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

    received_requests = [
        _friend_request_row_context(friend_request)
        for friend_request in _pending_friend_requests_for_user(request.user)
    ]

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
        'notice_type': notice_type,
        'friend_count': len(accepted_friends),
        'friend_limit': FRIEND_LIMIT,
        'received_requests': received_requests,
        'requests_count': len(received_requests),
    }
    return render(request, 'users/friends.html', context)


@login_required
def add_friend(request):
    if request.method != 'POST':
        return redirect(f"{reverse('friends')}?section=add")

    username = request.POST.get('username', '').strip().lstrip('@')
    redirect_url = f"{reverse('friends')}?section=add"
    wants_json = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def add_notice(message, notice_type='error'):
        if wants_json:
            status_code = 200 if notice_type == 'success' else 400
            return JsonResponse({'notice': message, 'notice_type': notice_type}, status=status_code)
        return redirect(f"{redirect_url}&notice={quote_plus(message)}&notice_type={notice_type}")

    if not username:
        return add_notice('Enter a username to add.')

    try:
        target_user = User.objects.get(username__iexact=username)
    except User.DoesNotExist:
        return add_notice('No user found with that username.')

    if target_user == request.user:
        return add_notice('You cannot add yourself.')

    if _friendship_for_users(request.user, target_user):
        return add_notice('You are already friends.')

    if _friend_count(request.user) >= FRIEND_LIMIT or _friend_count(target_user) >= FRIEND_LIMIT:
        return add_notice('One of these accounts has reached the 100 friend limit.')

    existing_sent_request = _sent_pending_friend_request(request.user, target_user)
    if existing_sent_request:
        return add_notice('Friend request already sent.')

    reverse_request = _received_pending_friend_request(request.user, target_user)
    if reverse_request:
        reverse_request.status = FriendRequest.ACCEPTED
        reverse_request.save(update_fields=['status', 'updated_at'])
        _create_friendship(request.user, target_user)
        _send_friend_request_removed(request.user.id, reverse_request.id)
        _send_friend_request_removed(target_user.id, reverse_request.id)
        _send_friend_added(request.user, target_user)
        _send_friend_added(target_user, request.user)
        return redirect(f"{reverse('friends')}?section=all&notice={quote_plus('Friend added.')}")

    friend_request, created = FriendRequest.objects.get_or_create(
        sender=request.user,
        recipient=target_user,
        defaults={'status': FriendRequest.PENDING},
    )

    if not created:
        friend_request.status = FriendRequest.PENDING
        friend_request.save(update_fields=['status', 'updated_at'])

    _send_friend_request_created(friend_request)
    return add_notice('Friend request sent.', 'success')


@login_required
def accept_friend_request(request, request_id):
    if request.method != 'POST':
        return redirect(f"{reverse('friends')}?section=requests")

    friend_request = get_object_or_404(
        FriendRequest.objects.select_related('sender', 'recipient'),
        id=request_id,
        recipient=request.user,
        status=FriendRequest.PENDING,
    )

    if _friend_count(request.user) >= FRIEND_LIMIT or _friend_count(friend_request.sender) >= FRIEND_LIMIT:
        return redirect(f"{reverse('friends')}?section=requests&notice={quote_plus('Friend limit reached for one of these accounts.')}")

    friend_request.status = FriendRequest.ACCEPTED
    friend_request.save(update_fields=['status', 'updated_at'])
    _create_friendship(request.user, friend_request.sender)
    _send_friend_request_removed(request.user.id, friend_request.id)
    _send_friend_request_removed(friend_request.sender_id, friend_request.id)
    _send_friend_added(request.user, friend_request.sender)
    _send_friend_added(friend_request.sender, request.user)
    return redirect(f"{reverse('friends')}?section=all&notice={quote_plus('Friend added.')}")


@login_required
def decline_friend_request(request, request_id):
    if request.method != 'POST':
        return redirect(f"{reverse('friends')}?section=requests")

    friend_request = get_object_or_404(
        FriendRequest,
        id=request_id,
        recipient=request.user,
        status=FriendRequest.PENDING,
    )
    friend_request.status = FriendRequest.DECLINED
    friend_request.save(update_fields=['status', 'updated_at'])
    _send_friend_request_removed(request.user.id, friend_request.id)
    _send_friend_request_removed(friend_request.sender_id, friend_request.id)
    return redirect(f"{reverse('friends')}?section=requests")


@login_required
def remove_friend(request, friend_id):
    if request.method != 'POST':
        return redirect(f"{reverse('friends')}?section=all")

    target_user = get_object_or_404(User.objects.select_related('profile'), id=friend_id)
    friendship = _friendship_for_users(request.user, target_user)
    if not friendship:
        return redirect(f"{reverse('friends')}?section=all&notice={quote_plus('Friend not found.')}")

    friendship.delete()
    _send_friend_removed(request.user.id, target_user.id)
    _send_friend_removed(target_user.id, request.user.id)
    return redirect(f"{reverse('friends')}?section=all&notice={quote_plus('Friend removed.')}")
