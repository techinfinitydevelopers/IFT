from django import forms
from django.contrib.auth.models import User
from students.models import School


class StudentSignUpForm(forms.Form):
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={
        'placeholder': 'First Name',
    }))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={
        'placeholder': 'Last Name',
    }))
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'placeholder': 'Email Address',
    }))
    password = forms.CharField(min_length=8, widget=forms.PasswordInput(attrs={
        'placeholder': 'Password (min 8 characters)',
    }))
    school = forms.ModelChoiceField(
        queryset=School.objects.filter(status='active').order_by('name'),
        empty_label='Select School',
    )
    grade = forms.ChoiceField(choices=[(str(i), f'Class {i}') for i in range(6, 13)])
    phone = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={
        'placeholder': 'Phone Number (optional)',
    }))
    terms = forms.BooleanField(error_messages={
        'required': 'You must agree to the Terms & Conditions.',
    })

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email


class SchoolSignUpForm(forms.Form):
    school_name = forms.CharField(max_length=300, widget=forms.TextInput(attrs={'placeholder': 'School Name'}))
    contact_email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'School Email'}))
    contact_phone = forms.CharField(max_length=15, widget=forms.TextInput(attrs={'placeholder': 'Phone Number'}))
    city = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'placeholder': 'City'}))
    state = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'placeholder': 'State'}))
    terms = forms.BooleanField(error_messages={'required': 'You must agree to the Terms & Conditions.'})

    def clean_contact_email(self):
        email = self.cleaned_data['contact_email']
        from django.contrib.auth.models import User
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email
