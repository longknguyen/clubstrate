import json
from datetime import timedelta

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.template.loader import render_to_string
from django.utils import timezone

from cios.models import CIO, Membership
from discussions.models import Comment, Post
from rate_limits import get_scope_ip, is_rate_limited_async

CHAT_GROUP_GAP = timedelta(minutes=5)
DISCUSSION_MESSAGE_MAX_LENGTH = 2000

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


class DiscussionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.cio_id = int(self.scope["url_route"]["kwargs"]["cio_id"])
        limited, _ = await is_rate_limited_async(
            'ws-connect-discussion',
            f"{get_scope_ip(self.scope)}:{self.cio_id}",
            limit=20,
            window_seconds=60,
        )
        if limited:
            await self.close(code=4408)
            return

        if not self.user.is_authenticated:
            await self.close()
            return

        if not await self._user_in_cio(self.cio_id, self.user.id):
            await self.close()
            return

        self.group_name = f"cio_discussion_{self.cio_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        limited, retry_after = await is_rate_limited_async(
            'ws-discussion-send',
            f"user:{self.user.id}:cio:{self.cio_id}",
            limit=30,
            window_seconds=60,
        )
        if limited:
            await self.send(text_data=json.dumps({
                "type": "rate_limited",
                "error": "Too many discussion messages. Please wait a minute and try again.",
                "retry_after": retry_after,
            }))
            return

        payload = json.loads(text_data)
        content = (payload.get("content") or "").strip()
        if not content or len(content) > DISCUSSION_MESSAGE_MAX_LENGTH:
            return

        message_id = await self._create_discussion_message(self.cio_id, self.user.id, content)
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "discussion.message",
                "message_id": message_id,
            },
        )

    async def discussion_message(self, event):
        html = await self._render_discussion_message_html(event["message_id"], self.user.id)
        await self.send(text_data=json.dumps({"type": "message", "html": html}))

    @database_sync_to_async
    def _user_in_cio(self, cio_id, user_id):
        return Membership.objects.filter(cio_id=cio_id, user_id=user_id).exists()

    @database_sync_to_async
    def _create_discussion_message(self, cio_id, author_id, content):
        cio = CIO.objects.get(id=cio_id)
        message = Post.objects.create(
            cio=cio,
            author_id=author_id,
            title=content[:80],
            content=content,
            kind=Post.DISCUSSION,
        )
        return message.id

    @database_sync_to_async
    def _render_discussion_message_html(self, message_id, viewer_id):
        message = Post.objects.select_related("author", "author__profile", "cio").get(id=message_id, kind=Post.DISCUSSION)
        previous_message = (
            Post.objects.select_related("author", "author__profile")
            .filter(cio_id=message.cio_id, kind=Post.DISCUSSION, created_at__lt=message.created_at)
            .order_by("-created_at")
            .first()
        )
        membership = Membership.objects.filter(cio_id=message.cio_id, user_id=message.author_id).first()
        within_gap_of_previous = previous_message is not None and message.created_at - previous_message.created_at <= CHAT_GROUP_GAP
        same_as_previous = (
            previous_message is not None
            and previous_message.author_id == message.author_id
            and previous_message.created_at.date() == message.created_at.date()
            and within_gap_of_previous
        )
        show_time_divider = (
            previous_message is None
            or message.created_at.date() != previous_message.created_at.date()
            or message.created_at - previous_message.created_at > CHAT_GROUP_GAP
        )
        return render_to_string(
            "discussions/partials/discussion_message_item.html",
            {
                "message": message,
                "is_own": viewer_id == message.author_id,
                "show_header": not same_as_previous,
                "show_avatar": True,
                "show_time_divider": show_time_divider,
                "time_divider_label": _time_divider_label(message.created_at),
                "display_name": _display_name_for_user(message.author),
                "cio_role_label": _cio_role_label(membership.role if membership else None),
            },
        )


class AnnouncementFeedConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.cio_id = int(self.scope["url_route"]["kwargs"]["cio_id"])
        limited, _ = await is_rate_limited_async(
            'ws-connect-announcement-feed',
            f"{get_scope_ip(self.scope)}:{self.cio_id}",
            limit=20,
            window_seconds=60,
        )
        if limited:
            await self.close(code=4408)
            return

        if not self.user.is_authenticated:
            await self.close()
            return

        if not await self._user_can_view_cio(self.cio_id, self.user.id):
            await self.close()
            return

        self.group_name = f"cio_announcements_{self.cio_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def announcement_event(self, event):
        await self.send(text_data=json.dumps({
            "type": event["event_type"],
            **event["payload"],
        }))

    @database_sync_to_async
    def _user_can_view_cio(self, cio_id, user_id):
        return CIO.objects.filter(id=cio_id).exists()


class AnnouncementThreadConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.post_id = int(self.scope["url_route"]["kwargs"]["post_id"])
        limited, _ = await is_rate_limited_async(
            'ws-connect-announcement-thread',
            f"{get_scope_ip(self.scope)}:{self.post_id}",
            limit=20,
            window_seconds=60,
        )
        if limited:
            await self.close(code=4408)
            return

        if not self.user.is_authenticated:
            await self.close()
            return

        thread_context = await self._thread_context(self.post_id, self.user.id)
        if not thread_context:
            await self.close()
            return

        self.cio_id = thread_context["cio_id"]
        self.viewer_role = thread_context["role"]
        self.group_name = f"announcement_thread_{self.post_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data or self.viewer_role == "viewer":
            return

        limited, retry_after = await is_rate_limited_async(
            'ws-announcement-thread-send',
            f"user:{self.user.id}:post:{self.post_id}",
            limit=30,
            window_seconds=60,
        )
        if limited:
            await self.send(text_data=json.dumps({
                "type": "rate_limited",
                "error": "Too many comments. Please wait a minute and try again.",
                "retry_after": retry_after,
            }))
            return

        payload = json.loads(text_data)
        content = (payload.get("content") or "").strip()
        if not content or len(content) > DISCUSSION_MESSAGE_MAX_LENGTH:
            return

        comment_id, comment_count = await self._create_comment(self.post_id, self.user.id, content)
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "announcement.thread.message",
                "comment_id": comment_id,
                "comment_count": comment_count,
            },
        )
        await self.channel_layer.group_send(
            f"cio_announcements_{self.cio_id}",
            {
                "type": "announcement.event",
                "event_type": "announcement_updated",
                "payload": await self._announcement_feed_payload(self.post_id),
            },
        )

    async def announcement_thread_message(self, event):
        html = await self._render_comment_html(event["comment_id"], self.user.id)
        await self.send(text_data=json.dumps({
            "type": "message",
            "html": html,
            "comment_count": event["comment_count"],
        }))

    async def announcement_event(self, event):
        await self.send(text_data=json.dumps({
            "type": event["event_type"],
            **event["payload"],
        }))

    @database_sync_to_async
    def _thread_context(self, post_id, user_id):
        try:
            post = Post.objects.select_related("cio").get(id=post_id, kind=Post.ANNOUNCEMENT)
        except Post.DoesNotExist:
            return None
        membership = Membership.objects.filter(cio_id=post.cio_id, user_id=user_id).first()
        return {
            "cio_id": post.cio_id,
            "role": membership.role if membership else "viewer",
        }

    @database_sync_to_async
    def _create_comment(self, post_id, author_id, content):
        comment = Comment.objects.create(post_id=post_id, author_id=author_id, content=content)
        return comment.id, comment.post.comments.count()

    @database_sync_to_async
    def _render_comment_html(self, comment_id, viewer_id):
        comment = Comment.objects.select_related("author", "author__profile", "post", "post__cio").get(id=comment_id)
        previous_comment = (
            Comment.objects.select_related("author", "author__profile")
            .filter(post_id=comment.post_id, parent__isnull=True, created_at__lt=comment.created_at)
            .order_by("-created_at")
            .first()
        )
        membership = Membership.objects.filter(cio_id=comment.post.cio_id, user_id=comment.author_id).first()
        within_gap_of_previous = previous_comment is not None and comment.created_at - previous_comment.created_at <= CHAT_GROUP_GAP
        same_as_previous = (
            previous_comment is not None
            and previous_comment.author_id == comment.author_id
            and previous_comment.created_at.date() == comment.created_at.date()
            and within_gap_of_previous
        )
        show_time_divider = (
            previous_comment is None
            or comment.created_at.date() != previous_comment.created_at.date()
            or comment.created_at - previous_comment.created_at > CHAT_GROUP_GAP
        )
        return render_to_string(
            "discussions/partials/announcement_comment_item.html",
            {
                "message": comment,
                "is_own": viewer_id == comment.author_id,
                "show_header": not same_as_previous,
                "show_avatar": True,
                "show_time_divider": show_time_divider,
                "time_divider_label": _time_divider_label(comment.created_at),
                "display_name": _display_name_for_user(comment.author),
                "cio_role_label": _cio_role_label(membership.role if membership else None),
            },
        )

    @database_sync_to_async
    def _announcement_feed_payload(self, post_id):
        post = Post.objects.select_related("author", "author__profile", "cio").get(id=post_id, kind=Post.ANNOUNCEMENT)
        post.display_name = _display_name_for_user(post.author)
        post.comment_count = post.comments.count()
        post.relative_created_label = _relative_time_label(post.created_at)
        post.announcement_tags_list = list(post.announcement_tags or [])[:3]
        html = render_to_string("discussions/partials/announcement_card.html", {"post": post})
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
        return {
            "post_id": post.id,
            "html": html,
            "summary_html": summary_html,
            "comment_count": post.comment_count,
        }
