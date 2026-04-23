from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.shortcuts import get_object_or_404, render, redirect
from datetime import timedelta

from cios.models import CIO, Membership
from discussions.models import Post, Comment
from image_utils import convert_upload_to_webp


def _display_name_for_user(user):
    full_name = f"{user.first_name} {user.last_name}".strip()
    return full_name or user.username


def _cio_role_label(role_value):
    if role_value == Membership.OFFICER:
        return "Officer"
    if role_value == Membership.MEMBER:
        return "Member"
    return "Viewer"


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


def _attach_chat_metadata(cio, messages):
    author_ids = {message.author_id for message in messages}
    membership_roles = {
        membership.user_id: membership.role
        for membership in Membership.objects.filter(cio=cio, user_id__in=author_ids)
    }

    for idx, message in enumerate(messages):
        message.display_name = _display_name_for_user(message.author)
        message.cio_role_label = _cio_role_label(membership_roles.get(message.author_id))

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


@login_required
def create_post(request, cio_id):
    cio = get_object_or_404(CIO, pk=cio_id)
    membership = Membership.objects.filter(user=request.user, cio=cio).first()
    if not membership or membership.role != Membership.OFFICER:
        return redirect(f'/{cio.id}/?tab=announcements')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        image = request.FILES.get('image')

        if not title and not content and not image:
            return redirect(f'/{cio.id}/?tab=announcements')

        Post.objects.create(
            cio=cio,
            author=request.user,
            title=title,
            content=content,
            image=convert_upload_to_webp(image, stem='announcement') if image else None,
            kind=Post.ANNOUNCEMENT,
        )

        return redirect(f'/{cio.id}/?tab=announcements')

    return render(request, 'discussions/create_post.html', {'cio': cio})


@login_required
def create_message(request, cio_id):
    cio = get_object_or_404(CIO, pk=cio_id)
    membership = Membership.objects.filter(user=request.user, cio=cio).first()
    if not membership:
        return redirect(f'/{cio.id}/')

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        image = request.FILES.get('image')

        if not content and not image:
            return redirect(f'/{cio.id}/?tab=discussions')

        Post.objects.create(
            cio=cio,
            author=request.user,
            title=content[:80],
            content=content,
            image=convert_upload_to_webp(image, stem='discussion') if image else None,
            kind=Post.DISCUSSION,
        )

    return redirect(f'/{cio.id}/?tab=discussions')


@login_required
def create_comment(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if not Membership.objects.filter(user=request.user, cio=post.cio).exists():
        return redirect(f'/{post.cio.id}/')

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        image = request.FILES.get('image')
        parent_id = request.POST.get('parent_id')

        if not content and not image:
            return redirect(f'/{post.cio.id}/?tab=announcements')

        parent = None
        if parent_id:
            parent = Comment.objects.get(id=parent_id)

        Comment.objects.create(
            post=post,
            author=request.user,
            content=content,
            image=convert_upload_to_webp(image, stem='comment') if image else None,
            parent=parent
        )

    return redirect(f'/{post.cio.id}/?tab=announcements')


@login_required
def toggle_post_like(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if not Membership.objects.filter(user=request.user, cio=post.cio).exists():
        return redirect(f'/{post.cio.id}/')

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

    if request.user in comment.likes.all():
        comment.likes.remove(request.user)
    else:
        comment.likes.add(request.user)

    return redirect(f'/{comment.post.cio.id}/?tab=discussions')

@login_required
def discussion_list(request, cio_id):
    cio = get_object_or_404(CIO, id=cio_id)
    recent_discussion_messages = list(
        Post.objects.filter(cio=cio, kind=Post.DISCUSSION)
        .select_related('author', 'author__profile')
        .order_by('-created_at')[:60]
    )
    discussion_messages = _attach_chat_metadata(cio, list(reversed(recent_discussion_messages)))

    role = 'viewer'
    if request.user.is_authenticated:
        membership = Membership.objects.filter(user=request.user, cio=cio).first()
        if membership:
            role = membership.role

    if role == 'viewer':
        return redirect(f'/{cio.id}/')

    return render(
        request,
        'discussions/list.html',
        {'cio': cio, 'discussion_messages': discussion_messages, 'role': role}
    )
