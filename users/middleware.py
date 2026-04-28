from django.shortcuts import redirect


class UserAdminLockMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user

        if user.is_authenticated:
            if hasattr(user, "profile") and user.profile.user_type == "user_admin":
                allowed_prefixes = (
                    "/users/role-admin/",
                    "/users/login/",
                    "/users/logout/",
                    "/users/login-redirect/",
                    "/static/",
                    "/media/",
                )

                if not request.path.startswith(allowed_prefixes):
                    return redirect("/users/role-admin/")

        return self.get_response(request)
