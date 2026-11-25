from django import forms
from django.contrib.auth import get_user_model


class ProfileForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ["username", "email", "first_name", "last_name"]
        labels = {
            "username": "Username",
            "email": "Email",
            "first_name": "First name",
            "last_name": "Last name",
        }