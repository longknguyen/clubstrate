from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

User = get_user_model()

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """
        Called before login completes; used to check userExists
        """

        email = sociallogin.account.extra_data.get('email')
        if email:
            try:
                existing_user = User.objects.get(email=email)
                sociallogin.connect(request, existing_user)
            except User.DoesNotExist:
                pass

        print("EXTRA DATA:", sociallogin.account.extra_data)
        email = sociallogin.account.extra_data.get('email')
        print("EMAIL:", email)

    def save_user(self, request, sociallogin, form=None) -> User:
        """
        Create new user if !userExists
        """

        user = super().save_user(request, sociallogin, form)
        user.email = sociallogin.account.extra_data.get('email', '')
        user.first_name = sociallogin.account.extra_data.get('given_name', '')
        user.last_name = sociallogin.account.extra_data.get('family_name', '')

        user.save()

        return user
    
    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        user.email = sociallogin.account.extra_data.get('email', '')
        user.first_name = sociallogin.account.extra_data.get('given_name', '')
        user.last_name = sociallogin.account.extra_data.get('family_name', '')
        return user
