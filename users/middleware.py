from django.shortcuts import redirect


class UserAdminLockMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        user = request.user

        if user.is_authenticated:
            if hasattr(user, "profile") and user.profile.user_type == "user_admin":

                allowed_paths = [
                    "/users/role-admin/",
                    "/users/login/",
                    "/users/logout/",
                    "/users/login-redirect/",
                ]

                if not any(request.path.startswith(p) for p in allowed_paths):
                    return redirect("/users/role-admin/")

        return response