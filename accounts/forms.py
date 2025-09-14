from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, UserProfile
from .timezone_utils import get_available_timezones


class SignUpForm(UserCreationForm):
    """
    Custom user registration form
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address'
        })
    )
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First Name'
        })
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last Name'
        })
    )
    
    class Meta:
        model = User
        fields = ('email', 'username', 'first_name', 'last_name', 'password1', 'password2')
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Choose a username'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user


class UserProfileForm(forms.ModelForm):
    """
    Form for editing user profile information
    """
    timezone = forms.ChoiceField(
        choices=get_available_timezones(),
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        help_text="Select your local timezone for accurate time display"
    )
    
    class Meta:
        model = UserProfile
        fields = [
            'age', 'occupation', 'daily_screen_time_hours',
            'wears_glasses', 'has_eye_strain', 'last_eye_checkup',
            'timezone', 'preferred_language'
        ]
        widgets = {
            'age': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '120'
            }),
            'occupation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Software Developer, Student, Designer'
            }),
            'daily_screen_time_hours': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '24',
                'step': '0.5'
            }),
            'wears_glasses': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'has_eye_strain': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'last_eye_checkup': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'preferred_language': forms.Select(attrs={
                'class': 'form-control'
            }),
        }


class UserSettingsForm(forms.ModelForm):
    """
    Form for user notification and timer settings
    """
    class Meta:
        model = User
        fields = [
            'email_notifications', 'break_reminders', 'daily_summary',
            'weekly_report', 'work_start_time', 'work_end_time',
            'break_duration', 'reminder_sound'
        ]
        widgets = {
            'work_start_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'work_end_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'break_duration': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '10',
                'max': '60'
            }),
            'email_notifications': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'break_reminders': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'daily_summary': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'weekly_report': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'reminder_sound': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }