from django import forms
from .models import CustomUser, Profile


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'pronouns', 'banner_colour']
        widgets = {
            'banner_colour': forms.TextInput(attrs={'type': 'color'}),
        }

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['image']
