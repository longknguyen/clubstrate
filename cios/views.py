from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db.models import Count, Exists, OuterRef
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta
import random
from urllib.parse import quote
import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from discussions.models import Post
from image_utils import convert_upload_to_webp
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


def _send_cio_request_event_to_user(user_id, event_type, payload):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    async_to_sync(channel_layer.group_send)(
        f"cio_requests_user_{user_id}",
        {
            "type": "cio.request.event",
            "event_type": event_type,
            "payload": payload,
        },
    )


def _send_cio_request_event_to_officers(cio_id, event_type, payload):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    async_to_sync(channel_layer.group_send)(
        f"cio_requests_officers_{cio_id}",
        {
            "type": "cio.request.event",
            "event_type": event_type,
            "payload": payload,
        },
    )


def _join_request_row_context(join_request):
    return {
        "id": join_request.id,
        "cio_id": join_request.cio_id,
        "display_name": _display_name_for_user(join_request.user),
        "username": join_request.user.username,
        "image_url": join_request.user.profile.image.url,
        "created_label": timezone.localtime(join_request.created_at).strftime("%-d %B %Y"),
    }


def _send_join_request_created(join_request):
    html = render_to_string(
        "cios/partials/join_request_row.html",
        {"join_request": _join_request_row_context(join_request)},
    )
    pending_count = JoinRequest.objects.filter(cio_id=join_request.cio_id, status="pending").count()

    _send_cio_request_event_to_user(
        join_request.user_id,
        "request_state",
        {
            "cio_id": join_request.cio_id,
            "pending": True,
            "joined": False,
        },
    )
    _send_cio_request_event_to_officers(
        join_request.cio_id,
        "request_created",
        {
            "cio_id": join_request.cio_id,
            "request_id": join_request.id,
            "pending_requests_count": pending_count,
            "html": html,
        },
    )


def _send_join_request_removed(join_request, *, approved=False):
    pending_count = JoinRequest.objects.filter(cio_id=join_request.cio_id, status="pending").count()

    _send_cio_request_event_to_user(
        join_request.user_id,
        "request_state",
        {
            "cio_id": join_request.cio_id,
            "pending": False,
            "joined": approved,
        },
    )
    _send_cio_request_event_to_officers(
        join_request.cio_id,
        "request_removed",
        {
            "cio_id": join_request.cio_id,
            "request_id": join_request.id,
            "pending_requests_count": pending_count,
        },
    )


CHAT_GROUP_GAP = timedelta(minutes=5)
DEFAULT_CIO_PALETTES = [
    {
        'icon_start': '#fecaca',
        'icon_end': '#fca5a5',
        'banner_start': '#fee2e2',
        'banner_mid': '#fecaca',
        'banner_end': '#fca5a5',
    },
    {
        'icon_start': '#fde68a',
        'icon_end': '#fcd34d',
        'banner_start': '#fef3c7',
        'banner_mid': '#fde68a',
        'banner_end': '#fbbf24',
    },
    {
        'icon_start': '#bbf7d0',
        'icon_end': '#86efac',
        'banner_start': '#dcfce7',
        'banner_mid': '#bbf7d0',
        'banner_end': '#4ade80',
    },
    {
        'icon_start': '#bfdbfe',
        'icon_end': '#93c5fd',
        'banner_start': '#dbeafe',
        'banner_mid': '#bfdbfe',
        'banner_end': '#60a5fa',
    },
    {
        'icon_start': '#ddd6fe',
        'icon_end': '#c4b5fd',
        'banner_start': '#ede9fe',
        'banner_mid': '#ddd6fe',
        'banner_end': '#a78bfa',
    },
    {
        'icon_start': '#fbcfe8',
        'icon_end': '#f9a8d4',
        'banner_start': '#fce7f3',
        'banner_mid': '#fbcfe8',
        'banner_end': '#f472b6',
    },
]


def _build_default_cio_icon_svg(palette):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{palette['icon_start']}"/>
      <stop offset="100%" stop-color="{palette['icon_end']}"/>
    </linearGradient>
  </defs>
  <rect x="0" y="0" width="128" height="128" rx="26" fill="url(#g)"/>
  <circle cx="64" cy="48" r="22" fill="#ffffff" opacity="0.92"/>
  <path d="M24 108c7-22 24-33 40-33s33 11 40 33" fill="#ffffff" opacity="0.92"/>
</svg>"""


def _build_default_cio_banner_gradient(palette):
    return (
        f"linear-gradient(135deg, {palette['banner_start']} 0%, "
        f"{palette['banner_mid']} 55%, {palette['banner_end']} 100%)"
    )


def _build_default_cio_icon_data_uri(palette):
    return f"data:image/svg+xml;utf8,{quote(_build_default_cio_icon_svg(palette))}"


def _assign_default_cio_branding(cio):
    palette = random.choice(DEFAULT_CIO_PALETTES)
    cio.gradient = _build_default_cio_banner_gradient(palette)
    cio.banner_type = 'default'

    if not cio.icon:
        icon_svg = _build_default_cio_icon_svg(palette)
        cio.icon.save(
            f"cio-default-{uuid.uuid4().hex[:12]}.svg",
            ContentFile(icon_svg.encode('utf-8')),
            save=False,
        )


def _get_default_cio_palette_index(raw_index=None):
    try:
        palette_index = int(raw_index)
    except (TypeError, ValueError):
        palette_index = random.randrange(len(DEFAULT_CIO_PALETTES))

    if palette_index < 0 or palette_index >= len(DEFAULT_CIO_PALETTES):
        palette_index = random.randrange(len(DEFAULT_CIO_PALETTES))

    return palette_index


def _assign_default_cio_branding_with_palette(cio, palette_index):
    palette = DEFAULT_CIO_PALETTES[palette_index]
    cio.gradient = _build_default_cio_banner_gradient(palette)
    cio.banner_type = 'default'

    if not cio.icon:
        icon_svg = _build_default_cio_icon_svg(palette)
        cio.icon.save(
            f"cio-default-{uuid.uuid4().hex[:12]}.svg",
            ContentFile(icon_svg.encode('utf-8')),
            save=False,
        )


def _get_cio_default_palette_index(cio):
    for idx, palette in enumerate(DEFAULT_CIO_PALETTES):
        if cio.gradient == _build_default_cio_banner_gradient(palette):
            return idx
    seed = f"{cio.pk or ''}:{cio.created_by_id or ''}:{cio.name or ''}"
    return sum(ord(char) for char in seed) % len(DEFAULT_CIO_PALETTES)


def _attach_cio_branding_display(cio):
    palette = DEFAULT_CIO_PALETTES[_get_cio_default_palette_index(cio)]
    cio.default_gradient = _build_default_cio_banner_gradient(palette)
    cio.default_icon_data_uri = _build_default_cio_icon_data_uri(palette)
    cio.display_icon_url = cio.icon.url if cio.icon else cio.default_icon_data_uri

    if cio.banner_type == 'image' and cio.banner_image:
        cio.display_banner_kind = 'image'
        cio.display_banner_value = cio.banner_image.url
    else:
        cio.display_banner_kind = 'gradient'
        cio.display_banner_value = cio.gradient or cio.default_gradient

    return cio


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


def _relative_time_label(created_at):
    delta = timezone.now() - created_at
    total_seconds = max(0, int(delta.total_seconds()))

    if total_seconds < 45:
        return "a few seconds ago"
    if total_seconds < 3600:
        minutes = max(1, total_seconds // 60)
        return f"{minutes} min{'s' if minutes != 1 else ''} ago"
    if total_seconds < 86400:
        hours = max(1, total_seconds // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"

    days = max(1, total_seconds // 86400)
    return f"{days} day{'s' if days != 1 else ''} ago"


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
    for cio in cios:
        _attach_cio_branding_display(cio)
    return render(request, 'cios/home.html', {'cios': cios})

@login_required
def create_cio(request):
    form = CIOCreateForm(request.POST or None, request.FILES or None)
    palette_index = _get_default_cio_palette_index(request.POST.get('default_palette_index'))
    default_icon_data_uri = _build_default_cio_icon_data_uri(DEFAULT_CIO_PALETTES[palette_index])

    if request.method == 'POST' and form.is_valid():
        cio = form.save(commit=False)
        cio.created_by = request.user
        if request.FILES.get('icon'):
            cio.icon = convert_upload_to_webp(request.FILES['icon'], stem='cio-icon')
        _assign_default_cio_branding_with_palette(cio, palette_index)
        cio.save()
        Membership.objects.create(
            user=request.user,
            cio=cio,
            role='officer',
        )
        return redirect('cio_detail', cio_id=cio.id)
    return render(
        request,
        'cios/create_cio.html',
        {
            'form': form,
            'default_palette_index': palette_index,
            'default_icon_data_uri': default_icon_data_uri,
        },
    )

@login_required
def cio_detail(request, cio_id):
    cio = get_object_or_404(CIO, pk=cio_id)
    _attach_cio_branding_display(cio)

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
    for post in announcement_posts:
        post.comment_count = post.comments.count()
        post.relative_created_label = _relative_time_label(post.created_at)
        post.announcement_tags_list = list(post.announcement_tags or [])[:3]

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
    _attach_cio_branding_display(cio)

    if not _get_cio_officer_membership(request.user, cio):
        return redirect(f'/{cio.id}/')

    form = CIOAboutForm(request.POST or None, request.FILES or None, instance=cio)

    if request.method == 'POST' and form.is_valid():
        cio = form.save(commit=False)
        default_palette_index = _get_cio_default_palette_index(cio)

        if form.cleaned_data.get('remove_icon'):
            cio.icon.delete(save=False)
            cio.icon = None
            _assign_default_cio_branding_with_palette(cio, default_palette_index)
        elif request.FILES.get('icon'):
            cio.icon = convert_upload_to_webp(request.FILES['icon'], stem='cio-icon')

        if form.cleaned_data.get('remove_banner'):
            cio.banner_image = None
            cio.banner_type = 'default'
        elif request.FILES.get('banner_image'):
            cio.banner_image = convert_upload_to_webp(request.FILES['banner_image'], stem='cio-banner')
            cio.banner_type = 'image'

        cio.save()
        return redirect(f'/{cio.id}/')
    context = _settings_sidebar_context(cio)
    context['form'] = form
    default_palette_index = _get_cio_default_palette_index(cio)
    context['default_icon_data_uri'] = _build_default_cio_icon_data_uri(DEFAULT_CIO_PALETTES[default_palette_index])
    return render(request, 'cios/edit_cio_about.html', context)


@login_required
def edit_cio_members(request, cio_id):
    cio = get_object_or_404(CIO, pk=cio_id)
    _attach_cio_branding_display(cio)

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
    _attach_cio_branding_display(cio)

    if not _get_cio_officer_membership(request.user, cio):
        return redirect(f'/{cio.id}/')

    join_requests = list(
        JoinRequest.objects.filter(cio=cio, status='pending')
        .select_related('user', 'user__profile')
        .order_by('created_at')
    )
    for join_request in join_requests:
        join_request.display_name = _display_name_for_user(join_request.user)
        join_request.username = join_request.user.username
        join_request.image_url = join_request.user.profile.image.url
        join_request.created_label = timezone.localtime(join_request.created_at).strftime("%-d %B %Y")

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
                join_request = JoinRequest.objects.create(
                    user=request.user,
                    cio=cio,
                    status='pending'
                )
                _send_join_request_created(join_request)
                pending = True
            elif join_request.status == 'pending':
                pending = True
            else:
                join_request.status = 'pending'
                join_request.save(update_fields=['status'])
                _send_join_request_created(join_request)
                pending = True

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'ok': True,
                'joined': membership is not None,
                'pending': pending,
            })

    return redirect(f'/{cio.id}/')


@login_required
def cancel_join_request(request, cio_id):
    cio = get_object_or_404(CIO, pk=cio_id)

    if request.method == 'POST':
        join_request = JoinRequest.objects.filter(
            user=request.user,
            cio=cio,
            status='pending',
        ).first()

        if join_request is not None:
            join_request.status = 'denied'
            join_request.save(update_fields=['status'])
            _send_join_request_removed(join_request, approved=False)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'ok': True,
                'joined': False,
                'pending': False,
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
        join_request.save(update_fields=['status'])
        _send_join_request_removed(join_request, approved=True)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'ok': True,
                'request_id': join_request.id,
                'cio_id': join_request.cio_id,
            })

    return redirect('discussions:edit_cio_requests', cio_id=join_request.cio.id)


@login_required
def deny_request(request, request_id):
    join_request = get_object_or_404(JoinRequest, pk=request_id)

    if request.method == 'POST' and _get_cio_officer_membership(request.user, join_request.cio):
        join_request.status = 'denied'
        join_request.save(update_fields=['status'])
        _send_join_request_removed(join_request, approved=False)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'ok': True,
                'request_id': join_request.id,
                'cio_id': join_request.cio_id,
            })

    return redirect('discussions:edit_cio_requests', cio_id=join_request.cio.id)
