import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import CIO, Membership
from rate_limits import get_scope_ip, is_rate_limited_async


class CioRequestConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        limited, _ = await is_rate_limited_async(
            'ws-connect-cio-requests',
            get_scope_ip(self.scope),
            limit=30,
            window_seconds=60,
        )
        if limited:
            await self.close(code=4408)
            return

        if not self.user.is_authenticated:
            await self.close()
            return

        self.group_names = [f"cio_requests_user_{self.user.id}"]
        officer_cio_ids = await self._officer_cio_ids(self.user.id)
        self.group_names.extend(
            f"cio_requests_officers_{cio_id}"
            for cio_id in officer_cio_ids
        )

        for group_name in self.group_names:
            await self.channel_layer.group_add(group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        for group_name in getattr(self, "group_names", []):
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def cio_request_event(self, event):
        await self.send(text_data=json.dumps({
            "type": event["event_type"],
            **event["payload"],
        }))

    @database_sync_to_async
    def _officer_cio_ids(self, user_id):
        return list(
            Membership.objects.filter(user_id=user_id, role=Membership.OFFICER)
            .values_list("cio_id", flat=True)
        )


class CioEventConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.cio_id = self.scope["url_route"]["kwargs"].get("cio_id")
        limited, _ = await is_rate_limited_async(
            'ws-connect-cio-events',
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

        if not await self._cio_exists(self.cio_id):
            await self.close()
            return

        self.group_name = f"cio_events_{self.cio_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        group_name = getattr(self, "group_name", None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def cio_event_message(self, event):
        await self.send(text_data=json.dumps({
            "type": event["event_type"],
            **event["payload"],
        }))

    @database_sync_to_async
    def _cio_exists(self, cio_id):
        return CIO.objects.filter(id=cio_id).exists()
