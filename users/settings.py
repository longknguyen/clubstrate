AUTH_USER_MODEL = "users.CustomUser"
SOCIALACCOUNT_ADAPTER = "users.adapters.CustomSocialAccountAdapter"

# used https://docs.djangoproject.com/en/6.0/ref/settings/ to look for URL redirection settings
LOGIN_URL = "/users/login/"
LOGIN_REDIRECT_URL = "/users/login-redirect/"
LOGOUT_REDIRECT_URL = "/"
