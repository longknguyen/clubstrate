from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from cios.models import CIO, JoinRequest, Membership
from discussions.models import Comment, Post
from image_utils import convert_upload_to_webp
from rate_limits import get_request_ip, is_rate_limited

CHAT_GROUP_GAP = timedelta(minutes=5)
ANNOUNCEMENT_TAG_LIMIT = 3
ANNOUNCEMENT_TAG_MAX_LENGTH = 24


def _rate_limit_identity(request, *, suffix=""):
    user_part = f"user:{request.user.id}" if request.user.is_authenticated else f"ip:{get_request_ip(request)}"
    return f"{user_part}:{suffix}" if suffix else user_part


def _rate_limit_response(message, retry_after):
    response = JsonResponse({'ok': False, 'error': message}, status=429)
    response['Retry-After'] = str(retry_after)
    return response


def _display_name_for_user(user):
    full_name = f"{user.first_name} {user.last_name}".strip()
    return full_name or user.username


def _cio_role_label(role_value):
    if role_value == Membership.OFFICER:
        return "Officer"
    if role_value == Membership.MEMBER:
        return "Member"
    return "Viewer"


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


def _parse_announcement_tags(raw_tags):
    tokens = []
    for token in (raw_tags or "").split(","):
        cleaned = " ".join(token.strip().split())
        if not cleaned:
            continue
        normalized = cleaned[:ANNOUNCEMENT_TAG_MAX_LENGTH]
        if normalized.lower() in {item.lower() for item in tokens}:
            continue
        tokens.append(normalized)
        if len(tokens) >= ANNOUNCEMENT_TAG_LIMIT:
            break
    return tokens


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


def _attach_chat_metadata(cio, messages):
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


def _attach_announcement_metadata(cio, posts):
    posts = _attach_author_metadata(cio, posts)
    comment_counts = {
        row["post_id"]: row["count"]
        for row in Comment.objects.filter(post__in=posts).values("post_id").annotate(count=Count("id"))
    } if posts else {}

    for post in posts:
        post.comment_count = comment_counts.get(post.id, 0)
        post.relative_created_label = _relative_time_label(post.created_at)
        post.announcement_tags_list = list(post.announcement_tags or [])[:ANNOUNCEMENT_TAG_LIMIT]

    return posts


def _announcement_card_context(post):
    return {
        "post": post,
    }


def _announcement_summary_context(post):
    return {
        "post": post,
        "relative_created_label": _relative_time_label(post.created_at),
        "comment_count": post.comments.count(),
        "announcement_tags_list": list(post.announcement_tags or [])[:ANNOUNCEMENT_TAG_LIMIT],
        "display_name": _display_name_for_user(post.author),
    }


def _broadcast_to_group(group_name, event_type, payload):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "announcement.event",
            "event_type": event_type,
            "payload": payload,
        },
    )


def _broadcast_announcement_created(post):
    post = Post.objects.select_related("author", "author__profile", "cio").get(pk=post.pk)
    post.display_name = _display_name_for_user(post.author)
    post.comment_count = 0
    post.relative_created_label = _relative_time_label(post.created_at)
    post.announcement_tags_list = list(post.announcement_tags or [])[:ANNOUNCEMENT_TAG_LIMIT]
    card_html = render_to_string("discussions/partials/announcement_card.html", _announcement_card_context(post))

    _broadcast_to_group(
        f"cio_announcements_{post.cio_id}",
        "announcement_created",
        {
            "post_id": post.id,
            "html": card_html,
        },
    )


def _broadcast_announcement_updated(post):
    post = Post.objects.select_related("author", "author__profile", "cio").get(pk=post.pk)
    post.display_name = _display_name_for_user(post.author)
    post.comment_count = post.comments.count()
    post.relative_created_label = _relative_time_label(post.created_at)
    post.announcement_tags_list = list(post.announcement_tags or [])[:ANNOUNCEMENT_TAG_LIMIT]
    card_html = render_to_string("discussions/partials/announcement_card.html", _announcement_card_context(post))
    summary_html = render_to_string(
        "discussions/partials/announcement_detail_summary.html",
        {
            "announcement": post,
            "display_name": post.display_name,
            "comment_count": post.comment_count,
            "relative_created_label": post.relative_created_label,
            "announcement_tags_list": post.announcement_tags_list,
        },
    )

    _broadcast_to_group(
        f"cio_announcements_{post.cio_id}",
        "announcement_updated",
        {
            "post_id": post.id,
            "html": card_html,
        },
    )
    _broadcast_to_group(
        f"announcement_thread_{post.id}",
        "announcement_updated",
        {
            "post_id": post.id,
            "summary_html": summary_html,
            "comment_count": post.comment_count,
        },
    )


def _get_role(user, cio):
    membership = Membership.objects.filter(user=user, cio=cio).first()
    return membership.role if membership else "viewer"


def _comment_redirect_url(post):
    if post.kind == Post.ANNOUNCEMENT:
        return f"/discussions/announcements/{post.id}/"
    return f"/{post.cio.id}/?tab=discussions"


@login_required
def create_post(request, cio_id):
    cio = get_object_or_404(CIO, pk=cio_id)
    membership = Membership.objects.filter(user=request.user, cio=cio).first()
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if not membership or membership.role != Membership.OFFICER:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'Officers only.'}, status=403)
        return redirect(f'/{cio.id}/?tab=announcements')

    if request.method == 'POST':
        limited, retry_after = is_rate_limited(
            'create-announcement',
            _rate_limit_identity(request, suffix=str(cio_id)),
            limit=10,
            window_seconds=3600,
        )
        if limited:
            return _rate_limit_response('Too many announcement posts. Please try again later.', retry_after)

        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()[:2000]
        image = request.FILES.get('image')
        if image:
            image_limited, image_retry_after = is_rate_limited(
                'announcement-upload',
                _rate_limit_identity(request),
                limit=8,
                window_seconds=600,
            )
            if image_limited:
                return _rate_limit_response('Too many announcement image uploads. Please try again later.', image_retry_after)
        tags = _parse_announcement_tags(request.POST.get('tags', ''))

        if not title and not content and not image:
            if is_ajax:
                return JsonResponse({'ok': False, 'error': 'Please add a title, description, or image.'}, status=400)
            return redirect(f'/{cio.id}/?tab=announcements')

        post = Post.objects.create(
            cio=cio,
            author=request.user,
            title=title,
            content=content,
            image=convert_upload_to_webp(image, stem='announcement') if image else None,
            kind=Post.ANNOUNCEMENT,
            announcement_tags=tags,
        )
        _broadcast_announcement_created(post)

        if is_ajax:
            return JsonResponse({'ok': True, 'post_id': post.id})
        return redirect(f'/{cio.id}/?tab=announcements')

    return render(request, 'discussions/create_post.html', {'cio': cio})


@login_required
def update_announcement(request, post_id):
    post = get_object_or_404(Post.objects.select_related("cio"), pk=post_id, kind=Post.ANNOUNCEMENT)
    membership = Membership.objects.filter(user=request.user, cio=post.cio).first()
    if request.method != 'POST' or not membership or membership.role != Membership.OFFICER:
        return JsonResponse({'ok': False}, status=403)

    limited, retry_after = is_rate_limited(
        'update-announcement',
        _rate_limit_identity(request, suffix=str(post.cio_id)),
        limit=20,
        window_seconds=3600,
    )
    if limited:
        return _rate_limit_response('Too many announcement edits. Please try again later.', retry_after)

    title = request.POST.get('title', '').strip()
    content = request.POST.get('content', '').strip()[:2000]
    tags = _parse_announcement_tags(request.POST.get('tags', ''))

    if not title and not content:
        return JsonResponse({'ok': False, 'error': 'Please add a title or description.'}, status=400)

    post.title = title
    post.content = content
    post.announcement_tags = tags
    image = request.FILES.get('image')
    if image:
        image_limited, image_retry_after = is_rate_limited(
            'announcement-upload',
            _rate_limit_identity(request),
            limit=8,
            window_seconds=600,
        )
        if image_limited:
            return _rate_limit_response('Too many announcement image uploads. Please try again later.', image_retry_after)
        post.image = convert_upload_to_webp(image, stem='announcement')
    post.save(update_fields=['title', 'content', 'announcement_tags', 'image'] if image else ['title', 'content', 'announcement_tags'])

    _broadcast_announcement_updated(post)
    return JsonResponse({'ok': True})


@login_required
def create_message(request, cio_id):
    cio = get_object_or_404(CIO, pk=cio_id)
    membership = Membership.objects.filter(user=request.user, cio=cio).first()
    if not membership:
        return redirect(f'/{cio.id}/')

    if request.method == 'POST':
        limited, retry_after = is_rate_limited(
            'create-discussion-message',
            _rate_limit_identity(request, suffix=str(cio_id)),
            limit=30,
            window_seconds=60,
        )
        if limited:
            return _rate_limit_response('Too many discussion messages. Please wait a minute and try again.', retry_after)

        content = request.POST.get('content', '').strip()
        image = request.FILES.get('image')
        if image:
            image_limited, image_retry_after = is_rate_limited(
                'discussion-upload',
                _rate_limit_identity(request),
                limit=8,
                window_seconds=600,
            )
            if image_limited:
                return _rate_limit_response('Too many discussion image uploads. Please try again later.', image_retry_after)

        if not content and not image:
            return redirect(f'/{cio.id}/?tab=discussions')

        message = Post.objects.create(
            cio=cio,
            author=request.user,
            title=content[:80],
            content=content,
            image=convert_upload_to_webp(image, stem='discussion') if image else None,
            kind=Post.DISCUSSION,
        )

        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"cio_discussion_{cio.id}",
                {
                    "type": "discussion.message",
                    "message_id": message.id,
                },
            )

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': True, 'message_id': message.id})

    return redirect(f'/{cio.id}/?tab=discussions')


@login_required
def create_comment(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    role = _get_role(request.user, post.cio)
    if role == "viewer":
        return redirect(f'/{post.cio.id}/')

    if request.method == 'POST':
        limited, retry_after = is_rate_limited(
            'create-comment',
            _rate_limit_identity(request, suffix=str(post.cio_id)),
            limit=30,
            window_seconds=60,
        )
        if limited:
            return _rate_limit_response('Too many comments. Please wait a minute and try again.', retry_after)

        content = request.POST.get('content', '').strip()
        image = request.FILES.get('image')
        parent_id = request.POST.get('parent_id')
        if image:
            image_limited, image_retry_after = is_rate_limited(
                'comment-upload',
                _rate_limit_identity(request),
                limit=8,
                window_seconds=600,
            )
            if image_limited:
                return _rate_limit_response('Too many comment image uploads. Please try again later.', image_retry_after)

        if not content and not image:
            return redirect(_comment_redirect_url(post))

        parent = None
        if parent_id:
            parent = Comment.objects.get(id=parent_id)

        comment = Comment.objects.create(
            post=post,
            author=request.user,
            content=content,
            image=convert_upload_to_webp(image, stem='comment') if image else None,
            parent=parent
        )
        if post.kind == Post.ANNOUNCEMENT:
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f"announcement_thread_{post.id}",
                    {
                        "type": "announcement.thread.message",
                        "comment_id": comment.id,
                        "comment_count": post.comments.count(),
                    },
                )
            _broadcast_announcement_updated(post)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': True, 'comment_id': comment.id})

    return redirect(_comment_redirect_url(post))


@login_required
def toggle_post_like(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if not Membership.objects.filter(user=request.user, cio=post.cio).exists():
        return redirect(f'/{post.cio.id}/')

    limited, retry_after = is_rate_limited(
        'toggle-post-like',
        _rate_limit_identity(request, suffix=str(post.cio_id)),
        limit=60,
        window_seconds=60,
    )
    if limited:
        return _rate_limit_response('Too many like actions. Please wait a minute and try again.', retry_after)

    if request.user in post.likes.all():
        post.likes.remove(request.user)
    else:
        post.likes.add(request.user)

    if post.kind == Post.DISCUSSION:
        return redirect(f'/{post.cio.id}/?tab=discussions')

    return redirect(f'/{post.cio.id}/?tab=announcements')


@login_required
def toggle_comment_like(request, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id)
    if not Membership.objects.filter(user=request.user, cio=comment.post.cio).exists():
        return redirect(f'/{comment.post.cio.id}/')

    limited, retry_after = is_rate_limited(
        'toggle-comment-like',
        _rate_limit_identity(request, suffix=str(comment.post.cio_id)),
        limit=60,
        window_seconds=60,
    )
    if limited:
        return _rate_limit_response('Too many like actions. Please wait a minute and try again.', retry_after)

    if request.user in comment.likes.all():
        comment.likes.remove(request.user)
    else:
        comment.likes.add(request.user)

    return redirect(_comment_redirect_url(comment.post))


@login_required
def discussion_list(request, cio_id):
    cio = get_object_or_404(CIO, id=cio_id)
    recent_discussion_messages = list(
        Post.objects.filter(cio=cio, kind=Post.DISCUSSION)
        .select_related('author', 'author__profile')
        .order_by('-created_at')[:60]
    )
    discussion_messages = _attach_chat_metadata(cio, list(reversed(recent_discussion_messages)))

    role = _get_role(request.user, cio)
    if role == 'viewer':
        return redirect(f'/{cio.id}/')

    return render(
        request,
        'discussions/list.html',
        {'cio': cio, 'discussion_messages': discussion_messages, 'role': role}
    )


@login_required
def announcement_detail(request, post_id):
    announcement = get_object_or_404(
        Post.objects.select_related('author', 'author__profile', 'cio'),
        pk=post_id,
        kind=Post.ANNOUNCEMENT,
    )
    cio = announcement.cio
    role = _get_role(request.user, cio)

    comments = list(
        announcement.comments.filter(parent__isnull=True)
        .select_related('author', 'author__profile')
        .order_by('-created_at')[:100]
    )
    comments = _attach_chat_metadata(cio, list(reversed(comments)))
    for comment in comments:
        comment.is_own = comment.author_id == request.user.id

    announcement.display_name = _display_name_for_user(announcement.author)
    announcement.comment_count = announcement.comments.count()
    announcement.relative_created_label = _relative_time_label(announcement.created_at)
    announcement.announcement_tags_list = list(announcement.announcement_tags or [])[:ANNOUNCEMENT_TAG_LIMIT]
    has_pending_request = False
    join_requests = []
    pending_requests_count = 0
    if request.user.is_authenticated:
        if role == Membership.OFFICER:
            join_requests = list(JoinRequest.objects.filter(cio=cio, status='pending').select_related('user'))
            pending_requests_count = len(join_requests)
        elif role == 'viewer':
            has_pending_request = JoinRequest.objects.filter(
                cio=cio,
                user=request.user,
                status='pending',
            ).exists()

    return render(
        request,
        'discussions/announcement_detail.html',
        {
            'announcement': announcement,
            'cio': cio,
            'role': role,
            'announcement_comments': comments,
            'join_requests': join_requests,
            'pending_requests_count': pending_requests_count,
            'has_pending_request': has_pending_request,
        },
    )
