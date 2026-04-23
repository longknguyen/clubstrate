import json
from datetime import timedelta

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone

from .models import DirectMessage, Friendship

DM_GROUP_GAP = timedelta(minutes=5)


def _display_name_for_user(user):
    full_name = f"{user.first_name} {user.last_name}".strip()
    return full_name or user.username


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


class DirectMessageConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.friendship_id = int(self.scope["url_route"]["kwargs"]["friendship_id"])

        if not self.user.is_authenticated:
            await self.close()
            return

        if not await self._user_in_friendship(self.friendship_id, self.user.id):
            await self.close()
            return

        self.group_name = f"friendship_{self.friendship_id}"
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

        message_payload = await self._create_message_payload(self.friendship_id, self.user.id, content)
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "direct.message",
                "html": message_payload["html"],
            },
        )

    async def direct_message(self, event):
        await self.send(text_data=json.dumps({"type": "message", "html": event["html"]}))

    @database_sync_to_async
    def _user_in_friendship(self, friendship_id, user_id):
        return Friendship.objects.filter(id=friendship_id).filter(
            Q(user_one_id=user_id) | Q(user_two_id=user_id)
        ).exists()

    @database_sync_to_async
    def _create_message_payload(self, friendship_id, sender_id, content):
        friendship = Friendship.objects.select_related(
            "user_one__profile",
            "user_two__profile",
        ).get(id=friendship_id)
        sender = friendship.user_one if friendship.user_one_id == sender_id else friendship.user_two

        previous_message = friendship.messages.select_related("sender", "sender__profile").order_by("-created_at").first()
        message = DirectMessage.objects.create(friendship=friendship, sender=sender, content=content)
        message = DirectMessage.objects.select_related("sender", "sender__profile").get(id=message.id)

        within_gap_of_previous = (
            previous_message is not None
            and message.created_at - previous_message.created_at <= DM_GROUP_GAP
        )
        same_as_previous = (
            previous_message is not None
            and previous_message.sender_id == message.sender_id
            and previous_message.created_at.date() == message.created_at.date()
            and within_gap_of_previous
        )
        show_time_divider = (
            previous_message is None
            or message.created_at.date() != previous_message.created_at.date()
            or message.created_at - previous_message.created_at > DM_GROUP_GAP
        )

        html = render_to_string(
            "users/partials/direct_message_item.html",
            {
                "message": message,
                "is_own": sender_id == message.sender_id,
                "show_header": not same_as_previous,
                "show_avatar": True,
                "show_time_divider": show_time_divider,
                "time_divider_label": _time_divider_label(message.created_at),
                "display_name": _display_name_for_user(message.sender),
                "timestamp_label": timezone.localtime(message.created_at).strftime("%-I:%M %p"),
            },
        )
        return {"html": html}
