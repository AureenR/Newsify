from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import UserProfile

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-input',
        'placeholder': 'Email address'
    }))
    first_name = forms.CharField(required=True, widget=forms.TextInput(attrs={
        'class': 'form-input',
        'placeholder': 'First name'
    }))
    last_name = forms.CharField(required=True, widget=forms.TextInput(attrs={
        'class': 'form-input',
        'placeholder': 'Last name'
    }))
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Username'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # MODIFIED: Updated placeholders for temporary password clarity
        self.fields['password1'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Temporary Password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Confirm Temporary password'
        })
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already registered.')
        return email

class SetInitialPasswordForm(forms.Form):
    """The form used for the mandatory permanent password reset after signup."""
    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'New Password'}),
        strip=False,
        help_text="Enter a strong password."
    )
    new_password2 = forms.CharField(
        label="New Password Confirmation",
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Confirm New Password'}),
        strip=False,
        help_text="Enter the same password as above, for verification."
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_new_password2(self):
        new_password1 = self.cleaned_data.get('new_password1')
        new_password2 = self.cleaned_data.get('new_password2')
        if new_password1 and new_password2:
            if new_password1 != new_password2:
                raise forms.ValidationError(
                    "The two password fields didn't match."
                )
        return new_password2

    def save(self):
        new_password = self.cleaned_data["new_password1"]
        self.user.set_password(new_password)
        self.user.save()
        return self.user

class OnboardingForm(forms.ModelForm):
    CATEGORY_CHOICES = [
        ('technology', 'Technology'),
        ('sports', 'Sports'),
        ('business', 'Business'),
        ('entertainment', 'Entertainment'),
        ('health', 'Health'),
        ('science', 'Science'),
        ('world', 'World News'),
        ('politics', 'Politics'),
    ]
    
    preferred_categories = forms.MultipleChoiceField(
        choices=CATEGORY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
        help_text='Select at least 3 categories you are interested in'
    )
    
    country = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Your country (optional)'
        })
    )
    
    bio = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'placeholder': 'Tell us a bit about yourself (optional)',
            'rows': 3
        })
    )
    
    class Meta:
        model = UserProfile
        fields = ['preferred_categories', 'country', 'bio']
    
    def clean_preferred_categories(self):
        categories = self.cleaned_data.get('preferred_categories')
        if len(categories) < 3:
            raise forms.ValidationError('Please select at least 3 categories.')
        return categories

class ProfileUpdateForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

class PreferencesUpdateForm(forms.ModelForm):
    CATEGORY_CHOICES = [
        ('technology', 'Technology'),
        ('sports', 'Sports'),
        ('business', 'Business'),
        ('entertainment', 'Entertainment'),
        ('health', 'Health'),
        ('science', 'Science'),
        ('world', 'World News'),
        ('politics', 'Politics'),
    ]
    
    preferred_categories = forms.MultipleChoiceField(
        choices=CATEGORY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    
    class Meta:
        model = UserProfile
        fields = ['preferred_categories', 'country', 'bio', 'email_notifications', 'show_images', 'dark_mode']