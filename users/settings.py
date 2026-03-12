AUTH_USER_MODEL = "users.CustomUser"
SOCIALACCOUNT_ADAPTER = "users.adapters.CustomSocialAccountAdapter"

LOGIN_REDIRECT_URL = "/users/profile/"
LOGOUT_REDIRECT_URL = "/"