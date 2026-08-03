import re
from django import forms
from django.contrib.auth.models import User
from students.models import School, Student

_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'\-]{1,99}$")


def _clean_person_name(value, label='Name'):
    value = (value or '').strip()
    if not _NAME_RE.fullmatch(value):
        raise forms.ValidationError(f'{label} should contain only letters, spaces, . - characters.')
    return value


def _clean_mobile(value):
    """Validate + normalise an Indian 10-digit mobile (strips +91 / 0 / spaces)."""
    m = re.sub(r'\D', '', value or '')
    if len(m) == 12 and m.startswith('91'):
        m = m[2:]
    elif len(m) == 11 and m.startswith('0'):
        m = m[1:]
    if not re.fullmatch(r'[6-9]\d{9}', m):
        raise forms.ValidationError('Enter a valid 10-digit Indian mobile number.')
    return m


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
    grade = forms.ChoiceField(choices=[(str(i), f'Class {i}') for i in range(7, 13)])
    gender = forms.ChoiceField(
        choices=[('male', 'Male'), ('female', 'Female')],
        error_messages={'required': 'Please select your gender.'},
    )
    phone = forms.CharField(max_length=15, error_messages={
        'required': 'Phone number is required.',
    }, widget=forms.TextInput(attrs={
        'placeholder': '10-digit mobile number',
    }))
    terms = forms.BooleanField(error_messages={
        'required': 'You must agree to the Terms & Conditions.',
    })

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_first_name(self):
        return _clean_person_name(self.cleaned_data.get('first_name'), 'First name')

    def clean_last_name(self):
        return _clean_person_name(self.cleaned_data.get('last_name'), 'Last name')

    def clean_phone(self):
        phone = _clean_mobile(self.cleaned_data.get('phone'))
        if Student.objects.filter(phone=phone).exists():
            raise forms.ValidationError('An account with this phone number already exists.')
        return phone


class SchoolSignUpForm(forms.Form):
    school_name = forms.CharField(max_length=300, widget=forms.TextInput(attrs={'placeholder': 'School Name'}))
    coordinator_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'placeholder': 'School Coordinator Name'}))
    contact_email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'School Email'}))
    contact_phone = forms.CharField(max_length=15, widget=forms.TextInput(attrs={'placeholder': 'Phone Number'}))
    address = forms.CharField(max_length=500, widget=forms.TextInput(attrs={'placeholder': 'School Address'}))
    city = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'placeholder': 'City'}))
    state = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'placeholder': 'State'}))
    pin_code = forms.CharField(max_length=10, widget=forms.TextInput(attrs={'placeholder': 'PIN Code'}))
    google_place_id = forms.CharField(max_length=255, required=False, widget=forms.HiddenInput())
    terms = forms.BooleanField(error_messages={'required': 'You must agree to the Terms & Conditions.'})

    def clean_contact_email(self):
        email = self.cleaned_data['contact_email']
        from django.contrib.auth.models import User
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_google_place_id(self):
        place_id = (self.cleaned_data.get('google_place_id') or '').strip()
        if place_id:
            from students.models import School
            if School.objects.filter(google_place_id=place_id).exists():
                raise forms.ValidationError(
                    'This school is already registered on IFT. Please sign in instead, or contact support if you believe this is an error.'
                )
        return place_id

    def clean_coordinator_name(self):
        return _clean_person_name(self.cleaned_data.get('coordinator_name'), 'Coordinator name')

    def clean_contact_phone(self):
        return _clean_mobile(self.cleaned_data.get('contact_phone'))

    def clean_pin_code(self):
        pin = re.sub(r'\s', '', self.cleaned_data.get('pin_code') or '')
        if not re.fullmatch(r'\d{6}', pin):
            raise forms.ValidationError('PIN code must be exactly 6 digits.')
        return pin
