from django.urls import re_path

from .consumers import AnnouncementFeedConsumer, AnnouncementThreadConsumer, DiscussionConsumer


websocket_urlpatterns = [
    re_path(r"ws/cios/(?P<cio_id>\d+)/discussions/$", DiscussionConsumer.as_asgi()),
    re_path(r"ws/cios/(?P<cio_id>\d+)/announcements/$", AnnouncementFeedConsumer.as_asgi()),
    re_path(r"ws/announcements/(?P<post_id>\d+)/thread/$", AnnouncementThreadConsumer.as_asgi()),
]
