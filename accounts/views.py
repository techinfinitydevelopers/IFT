from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.views import (
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)

import secrets
from django.http import JsonResponse

from .models import UserProfile, JuryProfile
from .forms import StudentSignUpForm, SchoolSignUpForm
from students.models import Student, School


def sign_in(request):
    if request.user.is_authenticated:
        return redirect('accounts:role_redirect')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me')

        user = None
        for user_obj in User.objects.filter(email=email):
            user = authenticate(request, username=user_obj.username, password=password)
            if user is not None:
                break

        if user is not None:
            login(request, user)
            if not remember_me:
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(1209600)  # 2 weeks
            next_url = request.GET.get('next') or request.POST.get('next', '')
            if next_url:
                return redirect(next_url)
            return redirect('accounts:role_redirect')
        else:
            messages.error(request, 'Invalid email or password.')

    return render(request, 'accounts/sign_in.html')


def sign_up(request):
    if request.user.is_authenticated:
        return redirect('accounts:role_redirect')

    if request.method == 'POST':
        form = StudentSignUpForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['email'],
                email=form.cleaned_data['email'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                password=form.cleaned_data['password'],
            )
            UserProfile.objects.create(user=user, role='student')
            school_obj = form.cleaned_data['school']
            Student.objects.create(
                user=user,
                student_id=f"IFT{user.id:05d}",
                school=school_obj,
                school_name=school_obj.name,
                grade=form.cleaned_data['grade'],
                phone=form.cleaned_data.get('phone', ''),
            )
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('students:dashboard')
    else:
        form = StudentSignUpForm()

    return render(request, 'accounts/sign_up.html', {'form': form})


def sign_out(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('accounts:sign_in')


@login_required
def role_redirect(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user, role='student')

    if profile.is_superadmin:
        return redirect('admins:dashboard')
    elif profile.is_jury:
        return redirect('students:evaluator_dashboard')
    elif profile.is_school:
        return redirect('students:school_dashboard')
    else:
        return redirect('students:dashboard')


def school_sign_up(request):
    if request.user.is_authenticated:
        return redirect('accounts:role_redirect')

    if request.method == 'POST':
        form = SchoolSignUpForm(request.POST)
        if form.is_valid():
            temp_password = secrets.token_urlsafe(8)
            email = form.cleaned_data['contact_email']

            user = User.objects.create_user(
                username=email,
                email=email,
                password=temp_password,
            )
            UserProfile.objects.create(user=user, role='school')

            school = School.objects.create(
                user=user,
                name=form.cleaned_data['school_name'],
                contact_email=email,
                contact_phone=form.cleaned_data['contact_phone'],
                city=form.cleaned_data['city'],
                state=form.cleaned_data['state'],
                status='pending',
                is_active=False,
            )

            # Send email with temp credentials
            from .emails import send_onboard_credentials
            send_onboard_credentials(user, temp_password, 'School')

            messages.success(request, 'School registered! Check your email for login credentials.')
            return redirect('accounts:sign_in')
    else:
        form = SchoolSignUpForm()

    return render(request, 'accounts/school_sign_up.html', {'form': form})


def school_search_api(request):
    q = request.GET.get('q', '').strip()
    schools = School.objects.filter(status='active')
    if q:
        schools = schools.filter(name__icontains=q)
    data = [{'id': s.id, 'name': s.name, 'city': s.city} for s in schools[:20]]
    return JsonResponse(data, safe=False)


class ForgotPasswordView(PasswordResetView):
    template_name = 'accounts/password_reset.html'
    email_template_name = 'accounts/password_reset_email.html'
    success_url = '/accounts/forgot-password/done/'


class ForgotPasswordDoneView(PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'


class ResetPasswordConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = '/accounts/reset/done/'


class ResetPasswordCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'
