from django import forms
from .models import CustomUser, Profile

PROFILE_FIRST_NAME_MAX_LENGTH = 50
PROFILE_LAST_NAME_MAX_LENGTH = 50
PROFILE_USERNAME_MAX_LENGTH = 30
PROFILE_PRONOUNS_MAX_LENGTH = 50


class UserUpdateForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=PROFILE_FIRST_NAME_MAX_LENGTH,
        required=False,
        widget=forms.TextInput(attrs={'maxlength': PROFILE_FIRST_NAME_MAX_LENGTH, 'id': 'id_first_name'}),
    )
    last_name = forms.CharField(
        max_length=PROFILE_LAST_NAME_MAX_LENGTH,
        required=False,
        widget=forms.TextInput(attrs={'maxlength': PROFILE_LAST_NAME_MAX_LENGTH, 'id': 'id_last_name'}),
    )
    username = forms.CharField(
        max_length=PROFILE_USERNAME_MAX_LENGTH,
        widget=forms.TextInput(attrs={'maxlength': PROFILE_USERNAME_MAX_LENGTH, 'id': 'id_username'}),
    )
    pronouns = forms.CharField(
        max_length=PROFILE_PRONOUNS_MAX_LENGTH,
        required=False,
        widget=forms.TextInput(attrs={'maxlength': PROFILE_PRONOUNS_MAX_LENGTH, 'id': 'id_pronouns'}),
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'pronouns', 'banner_colour']
        widgets = {
            'banner_colour': forms.TextInput(attrs={'type': 'color', 'maxlength': 7, 'id': 'id_banner_colour'}),
        }

    def clean_first_name(self):
        return self.cleaned_data['first_name'].strip()

    def clean_last_name(self):
        return self.cleaned_data['last_name'].strip()

    def clean_username(self):
        return self.cleaned_data['username'].strip()

    def clean_pronouns(self):
        return self.cleaned_data['pronouns'].strip()

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['image']
