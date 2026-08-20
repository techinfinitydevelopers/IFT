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
from django.utils.http import url_has_allowed_host_and_scheme
import threading


def _send_onboard_async(user, temp_password, role):
    """Send onboarding credentials on a background thread so a slow ZeptoMail
    call never blocks (and never 500s) the signup request/response."""
    def _worker():
        try:
            from .emails import send_onboard_credentials
            send_onboard_credentials(user, temp_password, role)
        except Exception:
            pass
    threading.Thread(target=_worker, daemon=True).start()

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
        for user_obj in User.objects.filter(email__iexact=email):
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
            # Only allow same-site redirects — block open-redirect to external hosts
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                return redirect(next_url)
            return redirect('accounts:role_redirect')
        else:
            # Distinguish a deactivated account (correct password but
            # is_active=False, which ModelBackend rejects as None) from a
            # genuinely wrong credential — only reveals "deactivated" when the
            # password actually matches, so it leaks nothing extra.
            inactive = User.objects.filter(email__iexact=email, is_active=False).first()
            if inactive and inactive.check_password(password):
                messages.error(request, 'Your account has been deactivated. Please contact support.')
            else:
                messages.error(request, 'Invalid email or password.')

    return render(request, 'accounts/sign_in.html')


def sign_up(request):
    if request.user.is_authenticated:
        # A logged-in student/school opening the public sign-up (e.g. a school
        # coordinator registering several students back-to-back) should get a
        # fresh registration form — not be bounced to the previous student's
        # payment page. Log them out first. Admin-level sessions are left alone.
        _p = getattr(request.user, 'profile', None)
        _role = getattr(_p, 'role', None) if _p is not None else None
        if request.user.is_staff or request.user.is_superuser or _role in ('viewer', 'tce'):
            return redirect('accounts:role_redirect')
        logout(request)

    show_school_not_registered = False
    duplicate_message = None
    if request.method == 'POST':
        form = StudentSignUpForm(request.POST)
        if form.is_valid():
            from . import otp as otp_service
            otp_ok, otp_err = otp_service.verify(request, form.cleaned_data.get('phone', ''), request.POST.get('otp', ''))
            if not otp_ok:
                return render(request, 'accounts/sign_up.html', {
                    'form': form,
                    'otp_error': otp_err,
                    'show_school_not_registered': show_school_not_registered,
                    'duplicate_message': duplicate_message,
                })
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
            otp_service.clear(request)
            login(request, user)
            messages.success(request, 'Account created successfully!')

            # Send welcome email in the background — don't block signup on ZeptoMail
            def _welcome_email(u):
                try:
                    from .emails import send_branded_email
                    send_branded_email(
                        "You're One Step Away from Starting Your IFT Journey!",
                        u.email,
                        'accounts/email_welcome_student.html',
                        {'user': u},
                    )
                except Exception:
                    pass
            threading.Thread(target=_welcome_email, args=(user,), daemon=True).start()
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
            # Surface duplicate email/phone as a popup, not just an inline error.
            for fld in ('email', 'phone'):
                errs = form.errors.get(fld, [])
                if any('already' in e.lower() for e in errs):
                    duplicate_message = errs[0]
                    break
    else:
        form = StudentSignUpForm()

    return render(request, 'accounts/sign_up.html', {
        'form': form,
        'show_school_not_registered': show_school_not_registered,
        'duplicate_message': duplicate_message,
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
        # Infer the real role from a linked profile instead of blindly assuming
        # 'student' (which mis-routed orphaned school/jury users).
        u = request.user
        if hasattr(u, 'school_profile'):
            role = 'school'
        elif hasattr(u, 'jury_profile'):
            role = 'jury'
        else:
            role = 'student'
        profile = UserProfile.objects.create(user=u, role=role)

    if profile.is_superadmin or profile.is_viewer or profile.is_tce:
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
        # Same as sign_up: log out a logged-in student/school so a fresh school
        # registration form is shown instead of bouncing to a dashboard/payment.
        # Admin-level sessions are left alone.
        _p = getattr(request.user, 'profile', None)
        _role = getattr(_p, 'role', None) if _p is not None else None
        if request.user.is_staff or request.user.is_superuser or _role in ('viewer', 'tce'):
            return redirect('accounts:role_redirect')
        logout(request)

    if request.method == 'POST':
        form = SchoolSignUpForm(request.POST)
        if form.is_valid():
            from . import otp as otp_service
            otp_ok, otp_err = otp_service.verify(request, form.cleaned_data.get('contact_phone', ''), request.POST.get('otp', ''))
            if not otp_ok:
                return render(request, 'accounts/school_sign_up.html', {'form': form, 'otp_error': otp_err})
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

            # Send email with temp credentials (background — don't block signup)
            _send_onboard_async(user, temp_password, 'School')

            otp_service.clear(request)
            messages.success(request, 'School registered! Check your email for login credentials.')
            return redirect('accounts:sign_in')
    else:
        form = SchoolSignUpForm()

    return render(request, 'accounts/school_sign_up.html', {'form': form})


def send_otp_api(request):
    """Send a phone-verification OTP for sign-up (student/school)."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST only'}, status=405)
    from . import otp as otp_service
    ok, err = otp_service.generate_and_send(request, request.POST.get('phone', ''))
    return JsonResponse({'success': ok, 'message': err or 'OTP sent to your mobile number.'})


def verify_otp_api(request):
    """Live-check a submitted OTP so the UI can show a checkmark before the
    user submits the whole form. Does NOT clear the session OTP — the final
    form submit still re-verifies (and clears) it server-side as before."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST only'}, status=405)
    from . import otp as otp_service
    ok, err = otp_service.verify(request, request.POST.get('phone', ''), request.POST.get('otp', ''))
    return JsonResponse({'success': ok, 'message': err or 'Mobile number verified.'})


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
