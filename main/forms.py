from django import forms
from .models import Profile
from .models import Content
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

class contentForm(forms.ModelForm):
    class Meta:
        model = Content
        fields = ['title', 'description', 'instructor', 'duration', 'image', 'video', 'pdf']

class registerForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['full_name', 'profession', 'about', 'profile_picture']