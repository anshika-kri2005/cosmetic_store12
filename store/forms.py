from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Review


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Username or Email",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter username or email",
                "autofocus": True,
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter password",
            }
        ),
    )


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(
                choices=[(5, '5 Stars'), (4, '4 Stars'), (3, '3 Stars'), (2, '2 Stars'), (1, '1 Star')],
                attrs={'class': 'form-select form-select-sm'},
            ),
            'comment': forms.Textarea(
                attrs={
                    'class': 'form-control form-control-sm',
                    'rows': 3,
                    'placeholder': 'Share your experience with this product',
                }
            ),
        }
