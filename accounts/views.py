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
from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
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

    show_school_not_registered = False
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
                gender=form.cleaned_data['gender'],
                phone=form.cleaned_data.get('phone', ''),
            )
            login(request, user)
            messages.success(request, 'Account created successfully!')

            # Send welcome email + in-app / push notification
            try:
                from .emails import send_branded_email
                send_branded_email(
                    'IFT: Registered Successfully',
                    user.email,
                    'accounts/email_welcome_student.html',
                    {'user': user},
                )
            except:
                pass
            try:
                from students.push import notify
                notify(user, 'system', 'Welcome to IFT Season 6!', 'Your account is ready. Start your innovation journey.', 'celebration', '/dashboard/', 'Go to Dashboard')
            except:
                pass

            return redirect('students:dashboard')
        else:
            posted_school = request.POST.get('school', '').strip()
            posted_school_name = request.POST.get('school_name_typed', '').strip()
            if 'school' in form.errors and (not posted_school or posted_school_name):
                show_school_not_registered = True
    else:
        form = StudentSignUpForm()

    return render(request, 'accounts/sign_up.html', {
        'form': form,
        'show_school_not_registered': show_school_not_registered,
    })


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

    if profile.is_superadmin or profile.is_viewer:
        return redirect('admins:dashboard')
    elif profile.is_jury:
        return redirect('students:evaluator_dashboard')
    elif profile.is_school:
        # A 'school' role with no linked School row (deleted/orphaned) would
        # otherwise bounce forever: school_dashboard -> sign_in -> role_redirect
        # -> school_dashboard. Fall through to the student dashboard instead.
        if hasattr(request.user, 'school_profile'):
            return redirect('students:school_dashboard')
        messages.error(request, 'Your school account has no school profile linked. Please contact support.')
        return redirect('students:dashboard')
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

            # TCE validation via India-region (Mumbai) proxy — TCE API is only
            # reachable from Indian IPs, and Railway/Cloudflare-edge egress is
            # outside India, so we route through a Cloud Run Mumbai proxy.
            is_tce = False
            try:
                import requests as http_requests
                from django.conf import settings as django_settings
                tce_payload = {
                    'school_name': form.cleaned_data['school_name'],
                    'address': form.cleaned_data['address'],
                    'city': form.cleaned_data['city'],
                    'state': form.cleaned_data['state'],
                    'pin_code': form.cleaned_data['pin_code'],
                }
                tce_proxy_url = getattr(django_settings, 'TCE_PROXY_URL', '')
                tce_proxy_secret = getattr(django_settings, 'TCE_PROXY_SECRET', '')
                print(f"[TCE] Payload: {tce_payload}", flush=True)
                if tce_proxy_url:
                    tce_resp = http_requests.post(
                        tce_proxy_url,
                        json=tce_payload,
                        headers={'X-Proxy-Secret': tce_proxy_secret},
                        timeout=20,
                    )
                    print(f"[TCE] Proxy: status={tce_resp.status_code}, body={tce_resp.text}", flush=True)
                    if tce_resp.status_code == 200:
                        is_tce = tce_resp.json().get('is_tce_school', False)
                else:
                    print("[TCE] Skipped — TCE_PROXY_URL not configured", flush=True)
                print(f"[TCE] {form.cleaned_data['school_name']}: is_tce={is_tce}", flush=True)
            except Exception as e:
                print(f"[TCE] API error: {e}", flush=True)

            school = School.objects.create(
                user=user,
                name=form.cleaned_data['school_name'],
                designated_teacher_name=form.cleaned_data['coordinator_name'],
                contact_email=email,
                contact_phone=form.cleaned_data['contact_phone'],
                address=form.cleaned_data['address'],
                city=form.cleaned_data['city'],
                state=form.cleaned_data['state'],
                pin_code=form.cleaned_data['pin_code'],
                is_tata_classedge=is_tce,
                status='pending',
                is_active=False,
                google_place_id=form.cleaned_data.get('google_place_id') or None,
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
    email_template_name = 'accounts/password_reset_email.txt'
    html_email_template_name = 'accounts/password_reset_email_html.html'
    success_url = '/accounts/forgot-password/done/'

    def get_extra_email_context(self):
        return {'logo_url': f"{getattr(settings, 'SITE_URL', '')}{staticfiles_storage.url('images/email_logo.png')}"}

    def form_valid(self, form):
        self.extra_email_context = self.get_extra_email_context()
        return super().form_valid(form)


class ForgotPasswordDoneView(PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'


class ResetPasswordConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = '/accounts/reset/done/'


class ResetPasswordCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'
