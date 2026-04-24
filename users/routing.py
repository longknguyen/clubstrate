from django.urls import re_path

from .consumers import DirectMessageConsumer, FriendRequestConsumer


websocket_urlpatterns = [
    re_path(r"ws/friends/(?P<friendship_id>\d+)/$", DirectMessageConsumer.as_asgi()),
    re_path(r"ws/friends/requests/$", FriendRequestConsumer.as_asgi()),
]
