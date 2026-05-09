import time

from asgiref.sync import sync_to_async
from django.core.cache import cache


def _window_key(bucket, identity, window_seconds):
    window = int(time.time() // window_seconds)
    return f"rate-limit:{bucket}:{identity}:{window}"


def get_request_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def get_scope_ip(scope):
    headers = {
        key.decode("latin1").lower(): value.decode("latin1")
        for key, value in scope.get("headers", [])
    }
    forwarded_for = headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    client = scope.get("client") or ()
    if client:
        return client[0]
    return "unknown"


def is_rate_limited(bucket, identity, limit, window_seconds):
    key = _window_key(bucket, identity, window_seconds)
    created = cache.add(key, 1, timeout=window_seconds + 5)
    current_count = 1 if created else cache.incr(key)
    retry_after = window_seconds - (int(time.time()) % window_seconds)
    return current_count > limit, retry_after


async def is_rate_limited_async(bucket, identity, limit, window_seconds):
    return await sync_to_async(is_rate_limited)(bucket, identity, limit, window_seconds)
