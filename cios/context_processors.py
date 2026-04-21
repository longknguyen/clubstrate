from cios.models import CIO


def joined_cios(request):
    if not request.user.is_authenticated:
        return {"joined_cios": []}

    cios = (
        CIO.objects.filter(membership__user=request.user)
        .distinct()
        .order_by("name")
    )
    return {"joined_cios": cios}
