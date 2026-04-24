from cios.models import CIO
from users.models import FriendRequest


def joined_cios(request):
    if not request.user.is_authenticated:
        return {"joined_cios": [], "pending_friend_requests_count": 0}

    from cios.views import _attach_cio_branding_display

    cios = (
        CIO.objects.filter(membership__user=request.user)
        .distinct()
        .order_by("name")
    )
    for cio in cios:
        _attach_cio_branding_display(cio)
    pending_friend_requests_count = FriendRequest.objects.filter(
        recipient=request.user,
        status=FriendRequest.PENDING,
    ).count()
    return {
        "joined_cios": cios,
        "pending_friend_requests_count": pending_friend_requests_count,
    }
