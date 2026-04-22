from cios.models import CIO


def joined_cios(request):
    if not request.user.is_authenticated:
        return {"joined_cios": []}

    from cios.views import _attach_cio_branding_display

    cios = (
        CIO.objects.filter(membership__user=request.user)
        .distinct()
        .order_by("name")
    )
    for cio in cios:
        _attach_cio_branding_display(cio)
    return {"joined_cios": cios}
