AUTH_USER_MODEL = "users.CustomUser"
SOCIALACCOUNT_ADAPTER = "users.adapters.CustomSocialAccountAdapter"

# used https://docs.djangoproject.com/en/6.0/ref/settings/ to look for URL redirection settings
LOGIN_REDIRECT_URL = "/users/profile/"
LOGOUT_REDIRECT_URL = "/"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",  # MUST exist
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",  # MUST exist
]