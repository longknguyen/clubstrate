import json
from datetime import timedelta

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone

from cios.models import CIO, Membership
from discussions.models import Post

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


class DiscussionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.cio_id = int(self.scope["url_route"]["kwargs"]["cio_id"])

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

        payload = json.loads(text_data)
        content = (payload.get("content") or "").strip()
        if not content:
            return

        if len(content) > DISCUSSION_MESSAGE_MAX_LENGTH:
            return

        message_payload = await self._create_message_payload(self.cio_id, self.user.id, content)
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "discussion.message",
                "message_id": message_payload["message_id"],
            },
        )

    async def discussion_message(self, event):
        html = await self._render_message_html(event["message_id"], self.user.id)
        await self.send(text_data=json.dumps({"type": "message", "html": html}))

    @database_sync_to_async
    def _user_in_cio(self, cio_id, user_id):
        return Membership.objects.filter(cio_id=cio_id, user_id=user_id).exists()

    @database_sync_to_async
    def _create_message_payload(self, cio_id, author_id, content):
        cio = CIO.objects.get(id=cio_id)
        message = Post.objects.create(
            cio=cio,
            author_id=author_id,
            title=content[:80],
            content=content,
            kind=Post.DISCUSSION,
        )
        return {"message_id": message.id}

    @database_sync_to_async
    def _render_message_html(self, message_id, viewer_id):
        message = Post.objects.select_related(
            "author",
            "author__profile",
            "cio",
        ).get(id=message_id, kind=Post.DISCUSSION)
        previous_message = (
            Post.objects.select_related("author", "author__profile")
            .filter(
                cio_id=message.cio_id,
                kind=Post.DISCUSSION,
                created_at__lt=message.created_at,
            )
            .order_by("-created_at")
            .first()
        )
        membership = Membership.objects.filter(cio_id=message.cio_id, user_id=message.author_id).first()

        within_gap_of_previous = (
            previous_message is not None
            and message.created_at - previous_message.created_at <= CHAT_GROUP_GAP
        )
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

        html = render_to_string(
            "discussions/partials/discussion_message_item.html",
            {
                "message": message,
                "is_own": viewer_id == message.author_id,
                "show_header": not same_as_previous,
                "show_avatar": True,
                "show_time_divider": show_time_divider,
                "time_divider_label": _time_divider_label(message.created_at),
                "display_name": _display_name_for_user(message.author),
                "timestamp_label": timezone.localtime(message.created_at).strftime("%-I:%M %p"),
                "cio_role_label": _cio_role_label(membership.role if membership else None),
            },
        )
        return html
