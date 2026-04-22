from django import forms

from .models import CIO


CIO_NAME_MAX_LENGTH = 100
CIO_DESCRIPTION_MAX_LENGTH = 250
CIO_DUES_MAX_LENGTH = 100
CIO_COMMITMENT_LEVEL_MAX_LENGTH = 100
CIO_TIME_EXPECTATIONS_MAX_LENGTH = 200


class CIOCreateForm(forms.ModelForm):
    class Meta:
        model = CIO
        fields = ['name', 'icon']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'discussion-input',
                    'id': 'name',
                    'placeholder': 'Enter CIO name',
                    'maxlength': CIO_NAME_MAX_LENGTH,
                }
            ),
        }

    def clean_name(self):
        return self.cleaned_data['name'].strip()


class CIOAboutForm(forms.ModelForm):
    remove_icon = forms.BooleanField(required=False)
    remove_banner = forms.BooleanField(required=False)

    name = forms.CharField(
        max_length=CIO_NAME_MAX_LENGTH,
        widget=forms.TextInput(
            attrs={
                'class': 'discussion-input',
                'id': 'name',
                'maxlength': CIO_NAME_MAX_LENGTH,
            }
        ),
    )

    description = forms.CharField(
        required=False,
        max_length=CIO_DESCRIPTION_MAX_LENGTH,
        widget=forms.Textarea(
            attrs={
                'class': 'discussion-textarea discussion-textarea-lg',
                'id': 'description',
                'rows': 5,
                'maxlength': CIO_DESCRIPTION_MAX_LENGTH,
            }
        ),
    )
    dues = forms.CharField(
        required=False,
        max_length=CIO_DUES_MAX_LENGTH,
        widget=forms.TextInput(attrs={'class': 'discussion-input', 'id': 'dues', 'maxlength': CIO_DUES_MAX_LENGTH}),
    )
    commitment_level = forms.CharField(
        required=False,
        max_length=CIO_COMMITMENT_LEVEL_MAX_LENGTH,
        widget=forms.TextInput(
            attrs={'class': 'discussion-input', 'id': 'commitment_level', 'maxlength': CIO_COMMITMENT_LEVEL_MAX_LENGTH}
        ),
    )
    time_expectations = forms.CharField(
        required=False,
        max_length=CIO_TIME_EXPECTATIONS_MAX_LENGTH,
        widget=forms.TextInput(
            attrs={'class': 'discussion-input', 'id': 'time_expectations', 'maxlength': CIO_TIME_EXPECTATIONS_MAX_LENGTH}
        ),
    )

    class Meta:
        model = CIO
        fields = ['name', 'description', 'dues', 'commitment_level', 'time_expectations', 'icon', 'banner_image']

    def clean_name(self):
        return self.cleaned_data['name'].strip()

    def clean_description(self):
        return self.cleaned_data['description'].strip()

    def clean_dues(self):
        return self.cleaned_data['dues'].strip()

    def clean_commitment_level(self):
        return self.cleaned_data['commitment_level'].strip()

    def clean_time_expectations(self):
        return self.cleaned_data['time_expectations'].strip()
