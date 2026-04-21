from django.contrib.auth.decorators import login_required
from django.db.models import Count, Exists, OuterRef
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from datetime import timedelta

from discussions.models import Post
from .forms import CIOAboutForm, CIOCreateForm
from .models import CIO, Membership, JoinRequest


def _display_name_for_user(user):
    full_name = f"{user.first_name} {user.last_name}".strip()
    return full_name or user.username


def _cio_role_label(role_value):
    if role_value == Membership.OFFICER:
        return "Officer"
    if role_value == Membership.MEMBER:
        return "Member"
    return "Viewer"


def _get_cio_officer_membership(user, cio):
    membership = Membership.objects.filter(user=user, cio=cio).first()
    if membership and membership.role == Membership.OFFICER:
        return membership
    return None


def _settings_sidebar_context(cio):
    return {
        'cio': cio,
        'pending_requests_count': JoinRequest.objects.filter(cio=cio, status='pending').count(),
    }


CHAT_GROUP_GAP = timedelta(minutes=5)


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


def _attach_author_metadata(cio, items):
    author_ids = {item.author_id for item in items}
    membership_roles = {
        membership.user_id: membership.role
        for membership in Membership.objects.filter(cio=cio, user_id__in=author_ids)
    }

    for item in items:
        item.display_name = _display_name_for_user(item.author)
        item.cio_role_label = _cio_role_label(membership_roles.get(item.author_id))

    return items


def _attach_chat_grouping(cio, messages):
    messages = _attach_author_metadata(cio, messages)

    for idx, message in enumerate(messages):
        previous_message = messages[idx - 1] if idx > 0 else None
        next_message = messages[idx + 1] if idx + 1 < len(messages) else None

        within_gap_of_previous = (
            previous_message is not None
            and message.created_at - previous_message.created_at <= CHAT_GROUP_GAP
        )
        within_gap_of_next = (
            next_message is not None
            and next_message.created_at - message.created_at <= CHAT_GROUP_GAP
        )

        same_as_previous = (
            previous_message is not None
            and previous_message.author_id == message.author_id
            and previous_message.created_at.date() == message.created_at.date()
            and within_gap_of_previous
        )
        same_as_next = (
            next_message is not None
            and next_message.author_id == message.author_id
            and next_message.created_at.date() == message.created_at.date()
            and within_gap_of_next
        )

        message.show_time_divider = (
            previous_message is None
            or message.created_at.date() != previous_message.created_at.date()
            or message.created_at - previous_message.created_at > CHAT_GROUP_GAP
        )
        message.time_divider_label = _time_divider_label(message.created_at)
        message.show_header = not same_as_previous
        message.show_avatar = not same_as_next

    return messages

def landing(request):
    if request.user.is_authenticated:
        return redirect('home')
    return render(request, 'cios/landing.html')

@login_required
def home(request):
    cios = CIO.objects.annotate(
        member_count=Count('membership'),
        is_joined=Exists(
            Membership.objects.filter(cio=OuterRef('pk'), user=request.user)
        ),
        has_pending_request=Exists(
            JoinRequest.objects.filter(cio=OuterRef('pk'), user=request.user, status='pending')
        ),
    ).order_by('name')
    return render(request, 'cios/home.html', {'cios': cios})

@login_required
def create_cio(request):
    form = CIOCreateForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        cio = form.save(commit=False)
        cio.created_by = request.user
        cio.save()
        Membership.objects.create(
            user=request.user,
            cio=cio,
            role='officer',
        )
        return redirect('home')
    return render(request, 'cios/create_cio.html', {'form': form})

@login_required
def cio_detail(request, cio_id):
    cio = get_object_or_404(CIO, pk=cio_id)

    role = 'viewer'
    join_requests = []
    has_pending_request = False

    if request.user.is_authenticated:
        membership = Membership.objects.filter(user=request.user, cio=cio).first()
        if membership is not None:
            role = membership.role
        else:
            has_pending_request = JoinRequest.objects.filter(
                user=request.user,
                cio=cio,
                status='pending'
            ).exists()

    if role == 'officer':
        join_requests = JoinRequest.objects.filter(cio=cio, status='pending')

    announcement_posts = list(
        cio.posts.filter(kind=Post.ANNOUNCEMENT)
        .select_related('author', 'author__profile')
        .prefetch_related('likes')
        .order_by('-created_at')
    )
    _attach_author_metadata(cio, announcement_posts)

    recent_discussion_messages = list(
        cio.posts.filter(kind=Post.DISCUSSION)
        .select_related('author', 'author__profile')
        .prefetch_related('likes')
        .order_by('-created_at')[:60]
    )
    discussion_messages = _attach_chat_grouping(cio, list(reversed(recent_discussion_messages)))

    members = list(
        Membership.objects.filter(cio=cio)
        .select_related('user', 'user__profile')
        .order_by('created_at', 'user__first_name', 'user__last_name', 'user__username')
    )
    for membership in members:
        membership.display_name = _display_name_for_user(membership.user)

    events = []

    return render(request,
                  'cios/cio_page.html',
                  {
            'cio': cio,
            'role': role,
            'events': events,
            'announcements': announcement_posts,
            'discussion_messages': discussion_messages,
            'join_requests': join_requests,
            'members': members,
            'pending_requests_count': len(join_requests),
            'has_pending_request': has_pending_request,
        },
                  )

@login_required
def edit_cio_about(request, cio_id):
    cio = get_object_or_404(CIO, pk=cio_id)

    if not _get_cio_officer_membership(request.user, cio):
        return redirect(f'/{cio.id}/')

    form = CIOAboutForm(request.POST or None, request.FILES or None, instance=cio)

    if request.method == 'POST' and form.is_valid():
        cio = form.save(commit=False)

        if form.cleaned_data.get('remove_icon'):
            cio.icon = None
        elif request.FILES.get('icon'):
            cio.icon = request.FILES['icon']

        if form.cleaned_data.get('remove_banner'):
            cio.banner_image = None
            cio.banner_type = 'default'
        elif request.FILES.get('banner_image'):
            cio.banner_image = request.FILES['banner_image']
            cio.banner_type = 'image'

        cio.save()
        return redirect(f'/{cio.id}/')
    context = _settings_sidebar_context(cio)
    context['form'] = form
    return render(request, 'cios/edit_cio_about.html', context)


@login_required
def edit_cio_members(request, cio_id):
    cio = get_object_or_404(CIO, pk=cio_id)

    if not _get_cio_officer_membership(request.user, cio):
        return redirect(f'/{cio.id}/')

    members = list(
        Membership.objects.filter(cio=cio)
        .select_related('user', 'user__profile')
        .order_by('created_at', 'user__first_name', 'user__last_name', 'user__username')
    )
    for member in members:
        member.display_name = _display_name_for_user(member.user)
        member.is_self = member.user_id == request.user.id

    context = _settings_sidebar_context(cio)
    context['members'] = members
    return render(request, 'cios/edit_cio_members.html', context)


@login_required
def edit_cio_requests(request, cio_id):
    cio = get_object_or_404(CIO, pk=cio_id)

    if not _get_cio_officer_membership(request.user, cio):
        return redirect(f'/{cio.id}/')

    join_requests = list(
        JoinRequest.objects.filter(cio=cio, status='pending')
        .select_related('user', 'user__profile')
        .order_by('created_at')
    )
    for join_request in join_requests:
        join_request.display_name = _display_name_for_user(join_request.user)

    context = _settings_sidebar_context(cio)
    context['join_requests'] = join_requests
    return render(request, 'cios/edit_cio_requests.html', context)


@login_required
def remove_cio_member(request, cio_id, membership_id):
    cio = get_object_or_404(CIO, pk=cio_id)

    if request.method != 'POST' or not _get_cio_officer_membership(request.user, cio):
        return redirect(f'/{cio.id}/')

    membership = get_object_or_404(Membership, pk=membership_id, cio=cio)
    if membership.user_id != request.user.id:
        membership.delete()

    return redirect('discussions:edit_cio_members', cio_id=cio.id)


@login_required
def delete_cio(request, cio_id):
    cio = get_object_or_404(CIO, pk=cio_id)

    if request.method != 'POST' or not _get_cio_officer_membership(request.user, cio):
        return redirect(f'/{cio.id}/')

    cio.delete()
    return redirect('home')

@login_required
def request_to_join(request, cio_id):
    cio = get_object_or_404(CIO, pk=cio_id)

    if request.method == 'POST':
        membership = Membership.objects.filter(user=request.user, cio=cio).first()
        join_request = JoinRequest.objects.filter(user=request.user, cio=cio).first()
        pending = False

        if membership is None:
            if join_request is None:
                JoinRequest.objects.create(
                    user=request.user,
                    cio=cio,
                    status='pending'
                )
                pending = True
            elif join_request.status == 'pending':
                pending = True
            else:
                join_request.status = 'pending'
                join_request.save(update_fields=['status'])
                pending = True

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'ok': True,
                'joined': membership is not None,
                'pending': pending,
            })

    return redirect(f'/{cio.id}/')

@login_required
def accept_request(request, request_id):
    join_request = get_object_or_404(JoinRequest, pk=request_id)

    if request.method == 'POST' and _get_cio_officer_membership(request.user, join_request.cio):
        membership = Membership.objects.filter(
            user=join_request.user,
            cio=join_request.cio
        ).first()

        if membership is None:
            Membership.objects.create(
                user=join_request.user,
                cio=join_request.cio,
                role='member'
            )

        join_request.status = 'approved'
        join_request.save()

    return redirect('discussions:edit_cio_requests', cio_id=join_request.cio.id)
