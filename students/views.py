from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.core.mail import send_mail
from .models import Student, IdeaSubmission, UploadedFile, School, IdeaLike, IdeaBookmark
from .forms import StudentRegistrationForm, IdeaSubmissionForm
from ai_assistant.processors import generate_summary
import os
import json


def _get_payment_amount(student):
    if student.school and student.school.is_tata_classedge:
        return 1600
    return 2500


def create_notification(user, notification_type, title, message='', icon='notifications', action_url='', action_label=''):
    """Helper to create an in-app notification (also fires a web push)."""
    from students.push import notify
    notify(user, notification_type, title, message, icon, action_url, action_label)


def home(request):
    """Landing page"""
    return render(request, 'landing/index.html')


def privacy_policy(request):
    """Privacy policy page"""
    return render(request, 'landing/privacy-policy.html')


def terms_of_service(request):
    """Terms of service page"""
    return render(request, 'landing/terms-of-service.html')


# ── Landing Page Email API ──────────────────────────────────────

FROM_EMAIL = 'noreply@indiafuturetycoons.com'
LANDING_INBOX = 'info@enlearning.in'


def _email_wrapper(title, badge, content):
    return f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f8;font-family:'Segoe UI',Arial,sans-serif;">
  <div style="max-width:600px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;margin-top:20px;margin-bottom:20px;box-shadow:0 4px 20px rgba(0,0,0,0.12);">
    <div style="background:linear-gradient(135deg,#1a1a2e 0%,#2d2d54 100%);padding:30px;text-align:center;border-bottom:3px solid #f59e0b;">
      <h2 style="color:#f59e0b;font-size:1.4rem;margin:0;font-weight:700;">{title}</h2>
      <p style="color:#cbd5e1;font-size:13px;margin:6px 0 0;letter-spacing:1px;">INDIA\'S FUTURE TYCOONS</p>
    </div>
    <div style="padding:30px;">
      <span style="display:inline-block;background:#f59e0b;color:#1a1a2e;padding:4px 12px;border-radius:50px;font-size:12px;font-weight:700;margin-bottom:14px;">{badge}</span>
      {content}
    </div>
    <div style="background:#f9fafb;padding:18px 30px;text-align:center;border-top:1px solid #e5e7eb;">
      <p style="color:#6b7280;font-size:12px;margin:0;">India\'s Future Tycoons (IFT)<br>indiasfuturetycoons.com</p>
    </div>
  </div>
</body>
</html>'''


def _table_row(label, value):
    v = value or '—'
    return (f'<tr><td style="padding:12px 16px;font-size:14px;border-bottom:1px solid #f0f0f0;'
            f'font-weight:700;color:#1a1a2e;width:40%;background:#fafafa;">{label}</td>'
            f'<td style="padding:12px 16px;font-size:14px;border-bottom:1px solid #f0f0f0;color:#555;">{v}</td></tr>')


def _build_table(rows):
    html = '<p style="color:#555;font-size:14px;margin-bottom:20px;line-height:1.6;">You have received a new inquiry from the IFT website.</p>'
    html += '<table style="width:100%;border-collapse:collapse;margin-bottom:20px;border:1px solid #f0f0f0;border-radius:8px;overflow:hidden;">'
    for label, value in rows:
        html += _table_row(label, value)
    html += '</table>'
    return html


@require_POST
@csrf_protect
def landing_school_inquiry(request):
    """Handle school inquiry form from landing page."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)

    content = _build_table([
        ('Full Name', data.get('name')),
        ('Role', data.get('role')),
        ('Email', data.get('email')),
        ('Contact Number', data.get('contact')),
        ('School Name & City', data.get('school')),
    ])
    subject = 'New School Inquiry — IFT Website'
    html_body = _email_wrapper('New School Inquiry', 'Bring IFT to My School', content)

    try:
        send_mail(subject, '', FROM_EMAIL, [LANDING_INBOX], html_message=html_body, fail_silently=False)
        return JsonResponse({'success': True, 'message': 'Inquiry sent successfully'})
    except Exception:
        return JsonResponse({'success': False, 'message': 'Failed to send email'}, status=500)


@require_POST
@csrf_protect
def landing_partner_inquiry(request):
    """Handle partner inquiry form from landing page."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)

    content = _build_table([
        ('Organization / Foundation', data.get('organization')),
        ('Designation', data.get('designation')),
        ('Email', data.get('email')),
        ('Contact Number', data.get('contact')),
    ])
    subject = 'New Partner Inquiry — IFT Website'
    html_body = _email_wrapper('New Partner Inquiry', 'Partner With IFT', content)

    try:
        send_mail(subject, '', FROM_EMAIL, [LANDING_INBOX], html_message=html_body, fail_silently=False)
        return JsonResponse({'success': True, 'message': 'Inquiry sent successfully'})
    except Exception:
        return JsonResponse({'success': False, 'message': 'Failed to send email'}, status=500)


def register(request):
    """Student registration view"""
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            # Create user
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                password=form.cleaned_data['password']
            )
            
            # Create student profile
            student = form.save(commit=False)
            student.user = user
            student.student_id = f"IFT{user.id:05d}"
            student.save()
            
            # Log the user in
            login(request, user)
            messages.success(request, 'Registration successful! Welcome to IFT Platform.')
            return redirect('students:dashboard')
    else:
        form = StudentRegistrationForm()
    
    return render(request, 'students/register.html', {'form': form})


def user_login(request):
    """Login view"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name}!')
            return redirect('students:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'students/login.html')


def user_logout(request):
    """Logout view"""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('students:home')


@login_required
def dashboard(request):
    """Student dashboard with submission status, team, timeline"""
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        # Auto-create student profile if missing
        student = Student.objects.create(
            user=request.user,
            school_name='Not Assigned',
            grade='10',
        )

    if not student.is_paid:
        return redirect('students:initiate_payment')

    from students.models import TeamMembership

    submissions = IdeaSubmission.objects.filter(student=student).order_by('-created_at')
    latest_submission = submissions.first()

    # If member, show leader's submission
    team_role = None
    membership = TeamMembership.objects.filter(student=student).select_related('team').first()
    if membership:
        team_role = membership.role
        if not latest_submission and team_role == 'member':
            leader_membership = membership.team.memberships.filter(role='leader').select_related('student').first()
            if leader_membership and leader_membership.student:
                latest_submission = IdeaSubmission.objects.filter(student=leader_membership.student).order_by('-created_at').first()

    # Submission stats
    total = submissions.count()
    submitted = submissions.filter(status='submitted').count()
    evaluated = submissions.filter(status='evaluated').count()
    draft = submissions.filter(status='draft').count()

    # Latest submission progress (how many of 12 questions filled)
    progress = 0
    if latest_submission:
        fields = ['q1_target_group', 'q2_exact_problem', 'q3_solution_simple', 'q4_differentiation',
                  'q5_build_steps', 'q6_resources', 'q7_positive_change', 'q8_challenges',
                  'q9_team_fit', 'q10_feedback', 'q11_creative_element', 'q12_pitch']
        filled = sum(1 for f in fields if getattr(latest_submission, f, ''))
        progress = round((filled / 12) * 100)

    # Team info from Team model
    team = None
    team_members_list = []
    team_code = None
    if membership:
        team = membership.team
        team_code = team.team_code
        team_members_list = list(team.memberships.select_related('student__user').filter(status='active'))

    # AI Score
    ai_score = None
    ai_rank = None
    if latest_submission:
        try:
            ev = latest_submission.ai_evaluation
            ai_score = ev.final_score
            ai_rank = ev.rank
        except:
            pass

    # Active phases (from Phase model)
    phases = []
    try:
        from admins.models import Phase
        phases = list(Phase.objects.all().order_by('order')[:5])
    except:
        pass

    # Recent activity from notifications
    from students.models import Notification
    recent_activity = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]

    # Published announcements for students
    from admins.models import Content
    announcements = Content.objects.filter(
        status='published',
        content_type='announcement',
        visibility__in=['all', 'students']
    ).order_by('-created_at')[:5]

    # Learning Videos
    from students.models import LearningVideo, VideoProgress
    learning_videos = LearningVideo.objects.filter(is_active=True).order_by('order')
    watched_video_ids = set()
    if student:
        watched_video_ids = set(VideoProgress.objects.filter(student=student, watched=True).values_list('video_id', flat=True))
    video_list = []
    for v in learning_videos:
        video_list.append({
            'id': v.id,
            'title': v.title,
            'youtube_id': v.youtube_id,
            'youtube_url': v.youtube_url,
            'is_mandatory': v.is_mandatory,
            'watched': v.id in watched_video_ids,
        })

    context = {
        'student': student,
        'submissions': submissions[:5],
        'latest_submission': latest_submission,
        'total': total,
        'submitted': submitted,
        'evaluated': evaluated,
        'draft': draft,
        'progress': progress,
        'team': team,
        'team_members': team_members_list,
        'team_code': team_code,
        'ai_score': ai_score,
        'ai_rank': ai_rank,
        'phases': phases,
        'active_phase': next((p for p in phases if p.status == 'active'), None),
        'team_role': team_role,
        'announcements': announcements,
        'recent_activity': recent_activity,
        'learning_videos': video_list,
        'videos_total': len(video_list),
        'videos_watched': len([v for v in video_list if v['watched']]),
        'payment_amount': _get_payment_amount(student) if not student.is_paid else 0,
    }
    return render(request, 'students/dashboard_v2.html', context)


import threading

@login_required
def _learning_progress(student, membership):
    """Own module progress + each team member's progress. Shared by leader and
    member views so both see the same 'Team Members Progress' list."""
    from students.models import LearningVideo, VideoProgress
    # Videos are OPTIONAL — this progress is informational only and never blocks
    # idea submission. All active videos are counted.
    mandatory_videos = list(LearningVideo.objects.filter(is_active=True).order_by('order'))
    watched_ids = set(VideoProgress.objects.filter(student=student, watched=True).values_list('video_id', flat=True))
    video_list = [{'id': v.id, 'title': v.title, 'youtube_url': v.youtube_url, 'youtube_id': v.youtube_id, 'watched': v.id in watched_ids} for v in mandatory_videos]
    videos_total = len(video_list)
    videos_watched = len([v for v in video_list if v['watched']])

    team_video_status = []
    if membership:
        for m in membership.team.memberships.filter(status='active').select_related('student__user'):
            if m.student:
                m_watched = VideoProgress.objects.filter(student=m.student, watched=True, video__in=mandatory_videos).count()
                team_video_status.append({
                    'name': m.student.user.get_full_name() or m.student.user.username,
                    'role': m.role,
                    'watched': m_watched,
                    'total': videos_total,
                    'complete': m_watched >= videos_total,
                })
    return video_list, videos_total, videos_watched, team_video_status


def submit_idea(request):
    """Idea submission form — only team leader or solo student can submit"""
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, 'Please complete your profile first.')
        return redirect('students:dashboard')

    # Check if member (not leader) — block submission
    from students.models import TeamMembership
    membership = TeamMembership.objects.filter(student=student).first()
    if membership and membership.role != 'leader':
        # Member — cannot submit, but should still see modules + team progress.
        team = membership.team
        leader_membership = team.memberships.filter(role='leader').select_related('student').first()
        leader_submission = None
        if leader_membership and leader_membership.student:
            leader_submission = IdeaSubmission.objects.filter(student=leader_membership.student).first()

        video_list, videos_total, videos_watched, team_video_status = _learning_progress(student, membership)
        return render(request, 'students/member_idea_view.html', {
            'student': student,
            'team': team,
            'leader_submission': leader_submission,
            'membership': membership,
            'video_list': video_list,
            'videos_total': videos_total,
            'videos_watched': videos_watched,
            'team_video_status': team_video_status,
        })

    # Check for existing submission (for edit flow)
    existing = IdeaSubmission.objects.filter(student=student).order_by('-created_at').first()

    if request.method == 'POST':
        save_type = request.POST.get('save_type', 'submit')  # 'draft' or 'submit'

        if save_type == 'draft':
            # Draft — save whatever is filled, skip validation
            if existing:
                submission = existing
            else:
                submission = IdeaSubmission(student=student)

            # Update ALL fields from POST data (including empty — user may clear a field)
            for field in ['q1_target_group', 'q2_exact_problem', 'q3_solution_simple', 'q4_differentiation',
                          'q5_build_steps', 'q6_resources', 'q7_positive_change', 'q8_challenges',
                          'q9_team_fit', 'q10_feedback', 'q11_creative_element', 'q12_pitch', 'title', 'competition_track']:
                if field in request.POST:
                    setattr(submission, field, request.POST.get(field, '').strip())

            submission.status = 'draft'

            # Auto-generate title
            title_source = (submission.q3_solution_simple or submission.q2_exact_problem or '').strip()
            if title_source and not submission.title:
                title = title_source[:80]
                if len(title_source) > 80:
                    last_space = title.rfind(' ')
                    if last_space > 40:
                        title = title[:last_space]
                submission.title = title

            submission.save()

            # Handle file uploads for draft too
            for field_name, file_type in [('document_file', 'document'), ('image_file', 'image'), ('video_file', 'video')]:
                uploaded_file = request.FILES.get(field_name)
                if uploaded_file:
                    if existing:
                        UploadedFile.objects.filter(submission=submission, file_type=file_type).delete()
                    UploadedFile.objects.create(
                        submission=submission, file_type=file_type,
                        file=uploaded_file, original_filename=uploaded_file.name, file_size=uploaded_file.size
                    )

            messages.success(request, 'Draft saved successfully!')
            return redirect('students:dashboard')

        # Submit for Review — no validation, save all fields as draft
        if existing:
            submission = existing
        else:
            submission = IdeaSubmission(student=student)

        for field in ['q1_target_group', 'q2_exact_problem', 'q3_solution_simple', 'q4_differentiation',
                      'q5_build_steps', 'q6_resources', 'q7_positive_change', 'q8_challenges',
                      'q9_team_fit', 'q10_feedback', 'q11_creative_element', 'q12_pitch', 'title', 'competition_track']:
            if field in request.POST:
                setattr(submission, field, request.POST.get(field, '').strip())

        submission.student = student
        submission.status = 'draft'

        # Auto-generate title
        title_source = (submission.q3_solution_simple or submission.q2_exact_problem or '').strip()
        if title_source and not submission.title:
            title = title_source[:80]
            if len(title_source) > 80:
                last_space = title.rfind(' ')
                if last_space > 40:
                    title = title[:last_space]
            submission.title = title

        submission.save()

        if True:  # keep indentation for file uploads below

            # Handle file uploads
            files_data = [
                ('document_file', 'document'),
                ('image_file', 'image'),
                ('video_file', 'video'),
            ]

            for field_name, file_type in files_data:
                uploaded_file = request.FILES.get(field_name)
                if uploaded_file:
                    # Remove old file of same type if editing
                    if existing:
                        UploadedFile.objects.filter(submission=submission, file_type=file_type).delete()
                    UploadedFile.objects.create(
                        submission=submission,
                        file_type=file_type,
                        file=uploaded_file,
                        original_filename=uploaded_file.name,
                        file_size=uploaded_file.size
                    )

            # Submit for Review — redirect to My Idea where leader can Publish
            messages.success(request, 'Idea saved! Review and publish from My Idea page.')
            return redirect('students:my_idea')
    else:
        form = IdeaSubmissionForm(instance=existing) if existing else IdeaSubmissionForm()

    # Video completion data for popup (+ team progress) — shared helper.
    video_list, videos_total, videos_watched, team_video_status = _learning_progress(student, membership)
    all_videos_done = videos_watched >= videos_total
    if team_video_status:
        all_videos_done = all_videos_done and all(t['complete'] for t in team_video_status)

    return render(request, 'students/submit_idea_v2.html', {
        'form': form,
        'is_edit': existing is not None,
        'saved_title': existing.title if existing else '',
        'saved_track': existing.competition_track if existing else '',
        'video_list': video_list,
        'videos_total': videos_total,
        'videos_watched': videos_watched,
        'all_videos_done': all_videos_done,
        'team_video_status': team_video_status,
    })


@login_required
def submit_idea_classic(request):
    """Old submit idea view — classic UI"""
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, 'Please complete your profile first.')
        return redirect('students:dashboard')

    if request.method == 'POST':
        return redirect('students:submit_idea')

    form = IdeaSubmissionForm()
    return render(request, 'students/submit_idea.html', {'form': form})


@login_required
def submission_confirmation(request, submission_id):
    """Confirmation page after submission"""
    submission = get_object_or_404(IdeaSubmission, id=submission_id, student__user=request.user)
    ai_summary = None
    try:
        ai_summary = submission.ai_summary
    except:
        pass
    return render(request, 'students/submission_confirmation.html', {'submission': submission, 'ai_summary': ai_summary})



@login_required
def submission_detail(request, submission_id):
    """View details of a specific submission — owner or team member can view"""
    from students.models import TeamMembership
    submission = get_object_or_404(IdeaSubmission, id=submission_id)

    # Check access: owner OR same team member
    is_owner = submission.student.user == request.user
    is_team_member = False
    if not is_owner:
        try:
            student = request.user.student_profile
            my_membership = TeamMembership.objects.filter(student=student).first()
            leader_membership = TeamMembership.objects.filter(student=submission.student, role='leader').first()
            if my_membership and leader_membership and my_membership.team == leader_membership.team:
                is_team_member = True
        except:
            pass

    # School admin can view submissions from their own school; superadmin/staff can view any
    is_school_admin = False
    try:
        school = request.user.school_profile
        if submission.student and submission.student.school_id == school.id:
            is_school_admin = True
    except School.DoesNotExist:
        pass
    is_staff_admin = request.user.is_staff or request.user.is_superuser

    if not (is_owner or is_team_member or is_school_admin or is_staff_admin):
        from django.http import Http404
        raise Http404("Submission not found.")
    
    ai_summary = None
    try:
        ai_summary = submission.ai_summary
    except:
        pass
    
    # Flatten context for reliable rendering
    context = {
        'submission': submission,
        'ai_summary': ai_summary,
        'submitted_at': submission.submitted_at.strftime("%B %d, %Y") if submission.submitted_at else "Not submitted",
        'status_label': submission.get_status_display(),
        
        # Questions (v3 with fallback to v2)
        'q1': submission.q1_target_group or submission.target_user_group or "Not provided",
        'q2': submission.q2_exact_problem or submission.problem_definition or "Not provided",
        'q3': submission.q3_solution_simple or submission.solution or "Not provided",
        'q4': submission.q4_differentiation or "Not provided",
        'q5': submission.q5_build_steps or "Not provided",
        'q6': submission.q6_resources or "Not provided",
        'q7': submission.q7_positive_change or submission.solution_benefits or "Not provided",
        'q8': submission.q8_challenges or "Not provided",
        'q9': submission.q9_team_fit or submission.why_best_equipped or "Not provided",
        'q10': submission.q10_feedback or "Not provided",
        'q11': submission.q11_creative_element or "Not provided",
        'q12': submission.q12_pitch or "Not provided",
        
        'uploaded_files': submission.uploaded_files.all(),
    }
    
    return render(request, 'students/submission_detail_v3.html', context)


@login_required
def school_dashboard(request):
    """School dashboard - complete profile or view full dashboard."""
    from students.models import Team, TeamMembership, IdeaSubmission
    from admins.models import Content, Phase
    from ai_assistant.models import AIEvaluation
    from django.db.models import Avg, Count

    try:
        school = request.user.school_profile
    except School.DoesNotExist:
        messages.error(request, 'No school profile found for this account. Please contact support.')
        return redirect('students:dashboard')

    if request.method == 'POST':
        import re
        from django.core.validators import validate_email, URLValidator
        from django.core.exceptions import ValidationError as DjangoValidationError

        P = request.POST
        def g(k):
            return (P.get(k) or '').strip()

        branch = g('branch')
        board = g('board')
        affiliation_number = g('affiliation_number')
        school_type = g('school_type')
        medium = g('medium')
        established_year = g('established_year')
        total_students = g('total_students')
        address = g('address')
        pin_code = re.sub(r'\s', '', g('pin_code'))
        country = g('country') or 'India'
        principal_name = g('principal_name')
        principal_email = g('principal_email')
        website = g('website')
        dt_name = g('designated_teacher_name')
        dt_mobile = g('designated_teacher_mobile')

        # Normalise mobile: strip non-digits, drop +91 / leading 0
        m = re.sub(r'\D', '', dt_mobile)
        if len(m) == 12 and m.startswith('91'):
            m = m[2:]
        elif len(m) == 11 and m.startswith('0'):
            m = m[1:]

        cur_year = timezone.now().year
        NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'\-]{1,99}$")
        BOARDS = ['CBSE', 'ICSE', 'SSC', 'IB', 'IGCSE', 'Other']
        TYPES = ['private', 'government', 'aided', 'other']

        errors = {}
        # --- Required + format ---
        if not board:
            errors['board'] = 'Please select a board.'
        elif board not in BOARDS:
            errors['board'] = 'Invalid board selected.'
        if not address:
            errors['address'] = 'Address is required.'
        elif len(address) < 5:
            errors['address'] = 'Enter a complete address (at least 5 characters).'
        elif len(address) > 500:
            errors['address'] = 'Address is too long (max 500 characters).'
        if not pin_code:
            errors['pin_code'] = 'PIN code is required.'
        elif not re.fullmatch(r'\d{6}', pin_code):
            errors['pin_code'] = 'PIN code must be exactly 6 digits.'
        if not principal_name:
            errors['principal_name'] = 'Principal name is required.'
        elif not NAME_RE.fullmatch(principal_name):
            errors['principal_name'] = 'Enter a valid name (letters, spaces, . - only).'
        if not principal_email:
            errors['principal_email'] = 'Principal email is required.'
        else:
            try:
                validate_email(principal_email)
            except DjangoValidationError:
                errors['principal_email'] = 'Enter a valid email address.'
        if not dt_name:
            errors['designated_teacher_name'] = 'Designated teacher name is required.'
        elif not NAME_RE.fullmatch(dt_name):
            errors['designated_teacher_name'] = 'Enter a valid name (letters, spaces, . - only).'
        if not dt_mobile:
            errors['designated_teacher_mobile'] = 'Mobile number is required.'
        elif not re.fullmatch(r'[6-9]\d{9}', m):
            errors['designated_teacher_mobile'] = 'Enter a valid 10-digit Indian mobile number.'
        # --- Optional but validated if provided ---
        if school_type and school_type not in TYPES:
            errors['school_type'] = 'Invalid school type.'
        if website:
            try:
                URLValidator(schemes=['http', 'https'])(website)
            except DjangoValidationError:
                errors['website'] = 'Enter a valid URL (starting with http:// or https://).'
        year_val = None
        if established_year:
            if not re.fullmatch(r'\d{4}', established_year) or not (1800 <= int(established_year) <= cur_year):
                errors['established_year'] = f'Enter a valid year (1800–{cur_year}).'
            else:
                year_val = int(established_year)
        students_val = None
        if total_students:
            if not re.fullmatch(r'\d{1,6}', total_students) or int(total_students) < 1:
                errors['total_students'] = 'Enter a valid number of students.'
            else:
                students_val = int(total_students)
        if len(branch) > 200:
            errors['branch'] = 'Too long (max 200 characters).'
        if affiliation_number:
            if not affiliation_number.isdigit():
                errors['affiliation_number'] = 'Affiliation number must contain only numbers.'
            elif len(affiliation_number) > 100:
                errors['affiliation_number'] = 'Affiliation number is too long (max 100 digits).'
        if len(medium) > 100:
            errors['medium'] = 'Too long (max 100 characters).'
        if len(country) > 100:
            errors['country'] = 'Too long (max 100 characters).'

        if errors:
            return JsonResponse({
                'success': False,
                'message': 'Please fix the highlighted fields.',
                'errors': errors,
            }, status=400)

        # --- Valid: save ---
        school.branch = branch
        school.board = board
        school.affiliation_number = affiliation_number
        school.school_type = school_type
        school.medium = medium
        school.established_year = year_val
        school.total_students = students_val
        school.address = address
        school.pin_code = pin_code
        school.country = country
        school.principal_name = principal_name
        school.principal_email = principal_email
        school.website = website
        school.designated_teacher_name = dt_name
        school.designated_teacher_mobile = m
        school.status = 'active'
        school.is_active = True
        school.save()

        return JsonResponse({
            'success': True,
            'message': 'School profile completed successfully!',
        })

    # If pending, show complete profile form
    if school.status == 'pending':
        return render(request, 'students/school_dashboard.html', {'school': school, 'is_pending': True})

    # ---- Active dashboard stats ----
    students = Student.objects.filter(school=school)
    student_count = students.count()

    # Teams (where leader's school is this school)
    team_ids = TeamMembership.objects.filter(
        student__school=school, role='leader'
    ).values_list('team_id', flat=True)
    teams_count = len(set(team_ids))

    # Ideas submitted by this school's students (exclude drafts)
    ideas = IdeaSubmission.objects.filter(
        student__school=school
    ).exclude(status='draft')
    ideas_count = ideas.count()

    # Avg AI score
    avg_score = AIEvaluation.objects.filter(
        submission__student__school=school
    ).aggregate(avg=Avg('final_score'))['avg'] or 0

    # SDG Track Distribution
    all_ideas = IdeaSubmission.objects.filter(student__school=school).exclude(competition_track='')
    track_data = list(all_ideas.values('competition_track').annotate(count=Count('id')).order_by('-count'))
    track_display = {
        'no-poverty': 'No Poverty', 'zero-hunger': 'Zero Hunger', 'good-health': 'Good Health',
        'quality-education': 'Quality Education', 'gender-equality': 'Gender Equality',
        'clean-water': 'Clean Water', 'clean-energy': 'Clean Energy',
        'economic-growth': 'Economic Growth', 'industry-innovation': 'Industry & Innovation',
        'reduced-inequalities': 'Reduced Inequalities', 'sustainable-cities': 'Sustainable Cities',
        'responsible-consumption': 'Responsible Consumption', 'climate-action': 'Climate Action',
        'life-below-water': 'Life Below Water', 'life-on-land': 'Life on Land',
        'peace-justice': 'Peace & Justice', 'partnerships': 'Partnerships',
    }
    sdg_tracks = [{'name': track_display.get(t['competition_track'], t['competition_track']), 'count': t['count']} for t in track_data]
    sdg_max = max((t['count'] for t in sdg_tracks), default=1)

    # Team Formation Status
    students_in_teams = TeamMembership.objects.filter(student__school=school, status='active').values_list('student_id', flat=True).distinct().count()
    solo_students = student_count - students_in_teams

    # Recent activity (last 5 submissions from this school)
    recent = IdeaSubmission.objects.filter(
        student__school=school
    ).select_related('student__user').order_by('-created_at')[:5]

    # Announcements for schools
    announcements = Content.objects.filter(
        status='published', content_type='announcement',
        visibility__in=['all', 'schools']
    ).order_by('-created_at')[:5]

    # Phases for competition progress
    phases = list(Phase.objects.all().order_by('order')[:6])

    # ---- Grade-wise submissions (this school) ----
    grade_qs = ideas.values('student__grade').annotate(count=Count('id')).order_by('student__grade')
    grade_data = [
        {'grade': (g['student__grade'] or 'N/A'), 'count': g['count']}
        for g in grade_qs
    ]

    # ---- Payment status (registered students who have paid) ----
    paid_count = students.filter(is_paid=True).count()
    unpaid_count = student_count - paid_count

    # ---- Live status funnel (this school) ----
    funnel = {
        'registered': student_count,
        'payment': paid_count,
        'team_formation': students_in_teams,
        'idea_submission': ideas_count,
    }

    # ---- Team Formation Status pie (this school) ----
    working_on_ideas = students_in_teams  # students in a team = actively working on ideas
    team_pie = {
        'registered': student_count,
        'paid': paid_count,
        'working': working_on_ideas,
        'submitted': ideas_count,
    }

    # ---- Platform-wide counts (across all schools) ----
    platform_schools = School.objects.filter(status='active').count()
    platform_students = Student.objects.count()
    platform_teams = Team.objects.filter(is_active=True).count()
    platform_ideas = IdeaSubmission.objects.exclude(status='draft').count()

    # ---- Days left for submission (from submission Phase, fallback 15 Oct 2026) ----
    from datetime import date
    sub_phase = Phase.objects.filter(name__icontains='submission').order_by('order').first()
    if sub_phase:
        days_left = sub_phase.days_remaining
        submission_deadline = sub_phase.end_date
    else:
        submission_deadline = date(2026, 10, 15)
        days_left = max(0, (submission_deadline - timezone.now().date()).days)

    # ---- Upcoming training calendar (managed by super admin via Content) ----
    today = timezone.now().date()
    training_qs = Content.objects.filter(
        content_type='training',
        status='published',
        visibility__in=['all', 'schools'],
        event_date__gte=today,
    ).order_by('event_date')
    import re
    _url_re = re.compile(r'https?://\S+')
    training_sessions = []
    for c in training_qs:
        match = _url_re.search(c.body or '')
        training_sessions.append({
            'title': c.title,
            'subtitle': c.subtitle,
            'body': c.body,
            'link': match.group(0) if match else '',
            'date': c.event_date,
            'time': c.event_time,
            'mode': c.event_mode or 'Online',
        })

    # ---- School participation badges (based on registered + paid students) ----
    badge_metric = paid_count  # registered students who have paid
    badge_tiers = [
        {'key': 'silver', 'name': 'Silver IFT Participation Badge', 'threshold': 20, 'image': 'images/badge_silver.png'},
        {'key': 'gold', 'name': 'Gold IFT Participation Badge', 'threshold': 30, 'image': 'images/badge_gold.png'},
        {'key': 'excellence', 'name': 'IFT School Excellence Trophy', 'threshold': 40, 'image': 'images/badge_excellence.png'},
    ]
    for tier in badge_tiers:
        tier['achieved'] = badge_metric >= tier['threshold']
        tier['percent'] = min(100, round(badge_metric * 100 / tier['threshold'])) if tier['threshold'] else 0
        tier['remaining'] = max(0, tier['threshold'] - badge_metric)

    context = {
        'school': school,
        'is_pending': False,
        'student_count': student_count,
        'badge_metric': badge_metric,
        'badge_tiers': badge_tiers,
        'teams_count': teams_count,
        'ideas_count': ideas_count,
        'avg_score': round(avg_score, 1),
        'sdg_tracks': sdg_tracks,
        'sdg_max': sdg_max,
        'students_in_teams': students_in_teams,
        'solo_students': solo_students,
        'recent': recent,
        'announcements': announcements,
        'phases': phases,
        'active_phase': next((p for p in phases if p.status == 'active'), None),
        'grade_data': grade_data,
        'paid_count': paid_count,
        'unpaid_count': unpaid_count,
        'funnel': funnel,
        'team_pie': team_pie,
        'platform_schools': platform_schools,
        'platform_students': platform_students,
        'platform_teams': platform_teams,
        'platform_ideas': platform_ideas,
        'days_left': days_left,
        'submission_deadline': submission_deadline,
        'training_sessions': training_sessions,
    }
    return render(request, 'students/school_dashboard.html', context)


@login_required
def school_payments(request):
    """Detailed payment status of this school's students for follow-ups."""
    from students.models import IdeaSubmission
    try:
        school = request.user.school_profile
    except School.DoesNotExist:
        messages.error(request, 'No school profile found for this account. Please contact support.')
        return redirect('students:dashboard')

    students = Student.objects.filter(school=school).select_related('user').order_by('user__first_name')
    rows = []
    for s in students:
        has_submission = IdeaSubmission.objects.filter(student=s).exclude(status='draft').exists()
        rows.append({
            'name': s.user.get_full_name() or s.user.username,
            'email': s.user.email,
            'grade': s.grade or '-',
            'phone': getattr(s, 'phone', '') or getattr(s, 'mobile', '') or '-',
            'is_paid': s.is_paid,
            'has_submission': has_submission,
        })

    paid = [r for r in rows if r['is_paid']]
    unpaid = [r for r in rows if not r['is_paid']]

    context = {
        'school': school,
        'rows': rows,
        'paid_count': len(paid),
        'unpaid_count': len(unpaid),
        'total_count': len(rows),
    }
    return render(request, 'students/school_payments.html', context)


def platform_live_stats(request):
    """JSON endpoint for the live ticker (platform-wide, refreshed daily)."""
    from datetime import date
    from admins.models import Phase
    from students.models import Team, IdeaSubmission

    sub_phase = Phase.objects.filter(name__icontains='submission').order_by('order').first()
    if sub_phase:
        days_left = sub_phase.days_remaining
        deadline = sub_phase.end_date
    else:
        deadline = date(2026, 10, 15)
        days_left = max(0, (deadline - timezone.now().date()).days)

    return JsonResponse({
        'days_left': days_left,
        'deadline': deadline.strftime('%d %b %Y'),
        'schools': School.objects.filter(status='active').count(),
        'students': Student.objects.count(),
        'teams': Team.objects.filter(is_active=True).count(),
        'ideas': IdeaSubmission.objects.exclude(status='draft').count(),
    })


@login_required
def student_profile(request):
    """Student profile page with edit capability."""
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        return redirect('accounts:sign_in')

    # Counts based on the current Team/TeamMembership system (not legacy).
    from students.models import TeamMembership
    SUBMITTED_STATUSES = ['submitted', 'under_review', 'evaluated', 'reviewed']

    membership = TeamMembership.objects.filter(student=student).select_related('team').first()
    if membership:
        team = membership.team
        # Count everyone in the team, including invited members not yet joined.
        all_members = team.memberships.filter(status__in=['active', 'pending'])
        team_count = all_members.count()
        member_students = [m.student_id for m in all_members if m.student_id]
        # "Ideas Submitted" = submitted (non-draft) ideas across the whole team.
        submissions_count = IdeaSubmission.objects.filter(
            student_id__in=member_students, status__in=SUBMITTED_STATUSES
        ).count()
    else:
        team_count = 0
        submissions_count = IdeaSubmission.objects.filter(
            student=student, status__in=SUBMITTED_STATUSES
        ).count()

    if request.method == 'POST':
        # Profile photo upload (multipart, separate from the JSON edit sections).
        if request.FILES.get('photo'):
            photo = request.FILES['photo']
            if photo.content_type not in ('image/jpeg', 'image/png', 'image/webp'):
                return JsonResponse({'success': False, 'message': 'Please upload a JPG, PNG or WEBP image.'}, status=400)
            if photo.size > 5 * 1024 * 1024:
                return JsonResponse({'success': False, 'message': 'Image must be under 5 MB.'}, status=400)
            student.photo = photo
            student.save(update_fields=['photo'])
            return JsonResponse({'success': True, 'message': 'Profile photo updated!', 'photo_url': student.photo.url})

        import json as json_mod
        if request.content_type == 'application/json':
            data = json_mod.loads(request.body)
        else:
            data = request.POST

        section = data.get('section', '')

        if section == 'personal':
            request.user.first_name = data.get('full_name', '').split(' ')[0]
            request.user.last_name = ' '.join(data.get('full_name', '').split(' ')[1:])
            request.user.email = data.get('email', request.user.email)
            student.phone = data.get('phone', student.phone)
            student.gender = data.get('gender', student.gender)
            student.nationality = data.get('nationality', student.nationality)
            dob = data.get('date_of_birth', '')
            if dob:
                student.date_of_birth = dob
            elif dob == '':
                student.date_of_birth = None
            request.user.save()
            student.save()
        elif section == 'academic':
            student.grade = data.get('grade', student.grade)
            student.division = data.get('division', student.division)
            student.roll_number = data.get('roll_number', student.roll_number)
            student.academic_year = data.get('academic_year', student.academic_year)
            student.stream = data.get('stream', student.stream)
            student.school_board = data.get('school_board', student.school_board)
            student.save()
        elif section == 'contact':
            student.phone = data.get('phone', student.phone)
            student.parent_mobile = data.get('parent_mobile', student.parent_mobile)
            student.parent_email = data.get('parent_email', student.parent_email)
            student.address = data.get('address', student.address)
            student.city = data.get('city', student.city)
            student.state = data.get('state', student.state)
            student.pin_code = data.get('pin_code', student.pin_code)
            student.save()

        return JsonResponse({'success': True, 'message': 'Profile updated successfully!'})

    context = {
        'student': student,
        'submissions_count': submissions_count,
        'team_count': team_count,
    }
    return render(request, 'students/profile.html', context)


@login_required
def my_idea(request):
    """Show student's or team leader's submitted idea."""
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        return redirect('accounts:sign_in')

    from students.models import TeamMembership, IdeaSuggestion

    # First check own submissions
    submission = IdeaSubmission.objects.filter(student=student).order_by('-created_at').first()

    # If no own submission, check if member of a team — show leader's submission
    team_role = None
    membership = TeamMembership.objects.filter(student=student).select_related('team').first()
    if membership:
        team_role = membership.role
        if not submission and team_role == 'member':
            # Find leader's submission
            leader_membership = membership.team.memberships.filter(role='leader').select_related('student').first()
            if leader_membership and leader_membership.student:
                submission = IdeaSubmission.objects.filter(student=leader_membership.student).order_by('-created_at').first()

    if not submission:
        # If member with no leader submission, show waiting message
        if membership and team_role == 'member':
            return render(request, 'students/my_idea.html', {
                'student': student, 'submission': None, 'team_role': 'member',
                'team_name': membership.team.name,
            })
        return render(request, 'students/my_idea.html', {'student': student, 'submission': None})

    # Get AI evaluation if exists
    ai_score = None
    ai_rank = None
    try:
        ev = submission.ai_evaluation
        ai_score = ev.final_score
        ai_rank = ev.rank
    except:
        pass

    # Team members from Team model (not legacy TeamMember)
    team_members = []
    if membership:
        team_members = list(membership.team.memberships.select_related('student__user').filter(status='active'))
    else:
        # Solo student — check if they have a team as leader
        solo_membership = TeamMembership.objects.filter(student=student, role='leader').select_related('team').first()
        if solo_membership:
            team_members = list(solo_membership.team.memberships.select_related('student__user').filter(status='active'))

    # Uploaded files
    files = list(submission.uploaded_files.all())

    # Pending suggestions count (for leader)
    pending_suggestions_count = 0
    if membership and team_role == 'leader':
        pending_suggestions_count = IdeaSuggestion.objects.filter(
            submission=submission, status='pending'
        ).count()

    # Member's own suggestions history
    my_suggestions = []
    if membership and team_role == 'member':
        my_suggestions = list(IdeaSuggestion.objects.filter(
            submission=submission, suggested_by=request.user
        ).order_by('-created_at'))

    context = {
        'student': student,
        'submission': submission,
        'ai_score': ai_score,
        'ai_rank': ai_rank,
        'team_members': team_members,
        'files': files,
        'team_role': team_role,
        'pending_suggestions_count': pending_suggestions_count,
        'my_suggestions': my_suggestions,
    }
    return render(request, 'students/my_idea.html', context)


@login_required
def team_page(request):
    """Team landing - show create/join if no team, else show team management."""
    from students.models import Team, TeamMembership
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        return redirect('accounts:sign_in')

    # Check if student is already in a team
    membership = TeamMembership.objects.filter(student=student).first()
    if membership:
        team = membership.team
        members = team.memberships.select_related('student__user').all()
        return render(request, 'students/team_management.html', {
            'student': student,
            'team': team,
            'members': members,
            'is_leader': team.leader == request.user,
        })

    # No team - show create/join page (with optional pre-filled team code from invite link)
    prefill_code = request.GET.get('team_code', '')
    return render(request, 'students/team.html', {'student': student, 'prefill_code': prefill_code})


@login_required
def create_team(request):
    """Create team page + POST handler."""
    from students.models import Team, TeamMembership
    import secrets, string
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        return redirect('accounts:sign_in')

    # Already in a team?
    if TeamMembership.objects.filter(student=student).exists():
        return redirect('students:team_page')

    if not student.is_paid:
        if request.method == 'POST' and request.content_type == 'application/json':
            return JsonResponse({'success': False, 'message': 'Please complete payment before creating a team.', 'redirect': '/payment/'}, status=403)
        return redirect('students:initiate_payment')

    if request.method == 'POST':
        import json as json_mod
        if request.content_type == 'application/json':
            data = json_mod.loads(request.body)
        else:
            data = request.POST

        team_name = data.get('team_name', '').strip()
        tagline = data.get('tagline', '').strip()
        track = data.get('track', '')
        description = data.get('description', '').strip()

        if not team_name:
            return JsonResponse({'success': False, 'message': 'Team name is required.'}, status=400)

        # Generate unique team code: IFT- + 5 random alphanumeric
        while True:
            code = 'IFT-' + ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(5))
            if not Team.objects.filter(team_code=code).exists():
                break

        team = Team.objects.create(
            name=team_name,
            tagline=tagline,
            track=track,
            description=description,
            team_code=code,
            leader=request.user,
        )

        # Add leader as first member
        TeamMembership.objects.create(
            team=team,
            student=student,
            role='leader',
            status='active',
        )

        create_notification(request.user, 'team', 'Team Created', f'Your team "{team_name}" has been created. Share code {code} to invite members.', 'group_add', '/team/', 'Manage Team')

        try:
            from accounts.emails import send_branded_email
            send_branded_email(
                'IFT Team Created Successfully!',
                request.user.email,
                'students/email_team_created.html',
                {'user': request.user},
            )
        except Exception:
            pass

        return JsonResponse({
            'success': True,
            'message': f'Team "{team_name}" created! Code: {code}',
            'team_code': code,
            'redirect': '/team/'
        })

    return render(request, 'students/create_team.html', {'student': student})


@login_required
def join_team(request):
    """Join team via code."""
    from students.models import Team, TeamMembership
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Student profile not found.'}, status=400)

    if TeamMembership.objects.filter(student=student).exists():
        return JsonResponse({'success': False, 'message': 'You are already in a team.'}, status=400)

    if not student.is_paid:
        return JsonResponse({'success': False, 'message': 'Please complete payment before joining a team.', 'redirect': '/payment/'}, status=403)

    import json as json_mod
    if request.content_type == 'application/json':
        data = json_mod.loads(request.body)
    else:
        data = request.POST

    code = data.get('team_code', '').strip().upper()

    try:
        team = Team.objects.get(team_code=code)
    except Team.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Invalid team code.'}, status=400)

    if team.is_full:
        return JsonResponse({'success': False, 'message': 'Team is full (max 2 members).'}, status=400)

    # Check if there's a pending invite for this student's email
    pending = TeamMembership.objects.filter(team=team, email=student.user.email, status='pending').first()
    if pending:
        pending.student = student
        pending.status = 'active'
        pending.save()
    else:
        TeamMembership.objects.create(
            team=team,
            student=student,
            role='member',
            status='active',
        )

    create_notification(team.leader, 'team', 'New Member Joined', f'{student.user.get_full_name()} has joined your team.', 'group_add', '/team/', 'View Team')

    return JsonResponse({
        'success': True,
        'message': f'You joined "{team.name}"!',
        'redirect': '/team/'
    })


@login_required
def remove_team_member(request):
    """Leader removes a member from team."""
    from students.models import TeamMembership
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json as json_mod
    if request.content_type == 'application/json':
        data = json_mod.loads(request.body)
    else:
        data = request.POST

    member_id = data.get('member_id')

    try:
        membership = TeamMembership.objects.get(id=member_id)
        if membership.team.leader != request.user:
            return JsonResponse({'success': False, 'message': 'Only team leader can remove members.'}, status=403)
        if membership.role == 'leader':
            return JsonResponse({'success': False, 'message': 'Cannot remove team leader.'}, status=400)
        membership.delete()
        return JsonResponse({'success': True, 'message': 'Member removed.'})
    except TeamMembership.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Member not found.'}, status=404)


@login_required
def invite_member(request):
    """Leader invites member via email."""
    from students.models import Team, TeamMembership
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json as json_mod
    if request.content_type == 'application/json':
        data = json_mod.loads(request.body)
    else:
        data = request.POST

    email = data.get('email', '').strip().lower()
    if not email:
        return JsonResponse({'success': False, 'message': 'Email is required.'}, status=400)

    # Get leader's team
    try:
        student = request.user.student_profile
        membership = TeamMembership.objects.filter(student=student, role='leader').first()
        if not membership:
            return JsonResponse({'success': False, 'message': 'Only team leader can invite.'}, status=403)
        team = membership.team
    except Exception:
        return JsonResponse({'success': False, 'message': 'Team not found.'}, status=400)

    if team.is_full:
        return JsonResponse({'success': False, 'message': 'Team is full (max 2 members).'}, status=400)

    # Check if already invited or active member with this email
    existing = TeamMembership.objects.filter(team=team, email=email).first()
    if existing:
        if existing.status == 'pending':
            # Resend - just return success
            return JsonResponse({'success': True, 'message': f'Invitation resent to {email}!'})
        return JsonResponse({'success': False, 'message': 'This email is already a team member.'}, status=400)

    # Create pending membership
    TeamMembership.objects.create(
        team=team,
        student=None,
        role='member',
        status='pending',
        email=email,
    )

    return JsonResponse({'success': True, 'message': f'Invitation sent to {email}!'})


@login_required
def suggest_edit(request, submission_id):
    """Team member suggests edits to the idea."""
    from students.models import IdeaSuggestion, TeamMembership

    submission = get_object_or_404(IdeaSubmission, id=submission_id)
    student = request.user.student_profile

    # Verify member of same team
    leader_membership = TeamMembership.objects.filter(student=submission.student, role='leader').first()
    if not leader_membership:
        return JsonResponse({'success': False, 'message': 'No team found.'}, status=400)

    my_membership = TeamMembership.objects.filter(student=student, team=leader_membership.team).first()
    if not my_membership:
        return JsonResponse({'success': False, 'message': 'You are not in this team.'}, status=403)

    if request.method == 'GET':
        context = {
            'student': student,
            'submission': submission,
            'is_suggestion': True,
        }
        return render(request, 'students/suggest_edit.html', context)

    if request.method == 'POST':
        import json as json_mod
        if request.content_type == 'application/json':
            data = json_mod.loads(request.body)
        else:
            data = request.POST

        message = data.get('message', '').strip()

        # Build changes dict - only include fields that changed
        fields = ['title', 'q1_target_group', 'q2_exact_problem', 'q3_solution_simple',
                  'q4_differentiation', 'q5_build_steps', 'q6_resources', 'q7_positive_change',
                  'q8_challenges', 'q9_team_fit', 'q10_feedback', 'q11_creative_element', 'q12_pitch']

        changes = {}
        for field in fields:
            new_val = data.get(field, '').replace('\r\n', '\n').strip()
            old_val = (getattr(submission, field, '') or '').replace('\r\n', '\n').strip()
            if new_val != old_val and new_val:  # only if actually different AND not empty
                changes[field] = new_val

        if not changes:
            return JsonResponse({'success': False, 'message': 'No changes detected.'}, status=400)

        IdeaSuggestion.objects.create(
            submission=submission,
            suggested_by=request.user,
            message=message,
            changes=changes,
        )

        create_notification(submission.student.user, 'submission', 'New Suggestion', f'{request.user.get_full_name()} suggested changes to your idea.', 'edit_note', f'/idea/{submission.id}/suggestions/', 'Review')

        return JsonResponse({
            'success': True,
            'message': f'Suggestion submitted! {len(changes)} field(s) changed. Leader will review.',
            'redirect': '/my-idea/'
        })

    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required
def review_suggestions(request, submission_id):
    """Leader reviews pending suggestions."""
    from students.models import IdeaSuggestion

    submission = get_object_or_404(IdeaSubmission, id=submission_id)

    if submission.student.user != request.user:
        return JsonResponse({'success': False, 'message': 'Only team leader can review.'}, status=403)

    suggestions = IdeaSuggestion.objects.filter(submission=submission).select_related('suggested_by')
    pending = suggestions.filter(status='pending')
    history = suggestions.exclude(status='pending')

    context = {
        'student': request.user.student_profile,
        'submission': submission,
        'pending': pending,
        'history': history,
    }
    return render(request, 'students/review_suggestions.html', context)


@login_required
def handle_suggestion(request, suggestion_id):
    """Leader approves or rejects a suggestion."""
    from students.models import IdeaSuggestion

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    suggestion = get_object_or_404(IdeaSuggestion, id=suggestion_id)

    if suggestion.submission.student.user != request.user:
        return JsonResponse({'success': False, 'message': 'Only team leader can review.'}, status=403)

    import json as json_mod
    if request.content_type == 'application/json':
        data = json_mod.loads(request.body)
    else:
        data = request.POST

    action = data.get('action', '')

    if action == 'approve':
        # Optional per-question selection: `fields` = list of field names to merge.
        # If omitted/empty -> approve all (original behaviour, backward compatible).
        selected = data.get('fields') or []
        if not isinstance(selected, list):
            selected = []

        if selected:
            applied = suggestion.apply_changes(only_fields=selected)
            # Keep only the still-unreviewed changes on the suggestion.
            remaining = {f: v for f, v in suggestion.changes.items() if f not in applied}
            if remaining:
                # Some questions still pending review — keep it open for later.
                suggestion.changes = remaining
                suggestion.save(update_fields=['changes'])
                create_notification(suggestion.suggested_by, 'submission', 'Some Suggestions Approved', f'{len(applied)} of your suggested change(s) were merged; the rest are still under review.', 'check_circle', '/my-idea/', 'View Idea')
                return JsonResponse({'success': True, 'message': f'{len(applied)} change(s) merged. {len(remaining)} still pending.', 'partial': True})
            # Everything got applied — close it out as approved.
            suggestion.status = 'approved'
            suggestion.reviewed_by = request.user
            suggestion.reviewed_at = timezone.now()
            suggestion.save()
            create_notification(suggestion.suggested_by, 'submission', 'Suggestion Approved', 'Your suggested changes have been approved and merged.', 'check_circle', '/my-idea/', 'View Idea')
            return JsonResponse({'success': True, 'message': f'{len(applied)} change(s) approved and merged!'})

        # No selection -> approve and merge everything.
        suggestion.status = 'approved'
        suggestion.reviewed_by = request.user
        suggestion.reviewed_at = timezone.now()
        suggestion.save()
        suggestion.apply_changes()
        create_notification(suggestion.suggested_by, 'submission', 'Suggestion Approved', 'Your suggested changes have been approved and merged.', 'check_circle', '/my-idea/', 'View Idea')
        return JsonResponse({'success': True, 'message': 'Changes approved and merged!'})

    elif action == 'reject':
        suggestion.status = 'rejected'
        suggestion.reject_reason = data.get('reason', '')
        suggestion.reviewed_by = request.user
        suggestion.reviewed_at = timezone.now()
        suggestion.save()
        create_notification(suggestion.suggested_by, 'submission', 'Suggestion Rejected', f'Reason: {data.get("reason", "No reason provided")}', 'cancel', '/my-idea/', 'View Idea')
        return JsonResponse({'success': True, 'message': 'Suggestion rejected.'})

    return JsonResponse({'success': False, 'message': 'Invalid action.'}, status=400)


@login_required
def publish_idea(request, submission_id):
    """Publish/finalize an idea - locks it from further edits."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    submission = get_object_or_404(IdeaSubmission, id=submission_id)

    if submission.student.user != request.user:
        return JsonResponse({'success': False, 'message': 'Only the team leader can publish.'}, status=403)

    if submission.status == 'submitted':
        return JsonResponse({'success': False, 'message': 'Already published.'}, status=400)

    # Validate required fields before publishing
    required_fields = ['q1_target_group', 'q2_exact_problem', 'q3_solution_simple', 'q4_differentiation',
                       'q5_build_steps', 'q6_resources', 'q7_positive_change', 'q8_challenges',
                       'q9_team_fit', 'q10_feedback', 'q11_creative_element', 'q12_pitch']
    empty_fields = [f for f in required_fields if not getattr(submission, f, '').strip()]
    if empty_fields:
        count = len(empty_fields)
        return JsonResponse({
            'success': False,
            'message': f'{count} required field(s) are empty. Please edit and fill all sections before publishing.'
        }, status=400)

    submission.status = 'submitted'
    submission.submitted_at = timezone.now()
    submission.save(update_fields=['status', 'submitted_at'])

    create_notification(request.user, 'submission', 'Idea Published', 'Your idea has been published and submitted for review.', 'rocket_launch', '/my-idea/', 'View Idea')

    # Send idea-submission confirmation email
    try:
        from accounts.emails import send_branded_email
        send_branded_email(
            'Your Idea Was Submitted Successfully!',
            request.user.email,
            'students/email_idea_submitted.html',
            {'user': request.user},
        )
    except:
        pass

    # Trigger AI processing
    def run_ai(sub_id):
        try:
            sub = IdeaSubmission.objects.get(id=sub_id)
            generate_summary(sub)
            sub.ai_processed = True
            sub.ai_processing_error = ''
            sub.save(update_fields=['ai_processed', 'ai_processing_error'])
        except Exception as e:
            try:
                sub = IdeaSubmission.objects.get(id=sub_id)
                sub.ai_processing_error = str(e)[:500]
                sub.save(update_fields=['ai_processing_error'])
            except Exception:
                pass

    threading.Thread(target=run_ai, args=(submission.id,), daemon=True).start()

    # Auto-send the Participation certificate (background, once per student)
    try:
        from admins.views import send_participation_certificate
        send_participation_certificate(submission.student, sent_by=request.user)
    except Exception:
        pass

    return JsonResponse({'success': True, 'message': 'Your idea has been published and submitted for review!'})


@login_required
def idea_corner(request):
    """Public idea gallery — browse all published ideas."""
    from django.db.models import Count
    ideas = IdeaSubmission.objects.filter(
        status__in=['submitted', 'evaluated', 'reviewed']
    ).select_related('student__user', 'student__school').annotate(
        like_count=Count('likes', distinct=True)
    ).order_by('-submitted_at')

    # Ideas the current user has already liked / bookmarked (to show filled icons).
    liked_ids = set()
    bookmarked_ids = set()
    if request.user.is_authenticated:
        liked_ids = set(
            IdeaLike.objects.filter(user=request.user).values_list('submission_id', flat=True)
        )
        bookmarked_ids = set(
            IdeaBookmark.objects.filter(user=request.user).values_list('submission_id', flat=True)
        )

    # Stats
    total_ideas = ideas.count()
    total_schools = ideas.values('student__school').distinct().count()

    # Serialize for template
    idea_list = []
    for idea in ideas[:50]:  # limit to 50
        # Use competition_track as primary category, fallback to final_category
        track = idea.competition_track or ''
        track_map = {
            'no-poverty': 'No Poverty',
            'zero-hunger': 'Zero Hunger',
            'good-health': 'Good Health and Well-Being',
            'quality-education': 'Quality Education',
            'gender-equality': 'Gender Equality',
            'clean-water': 'Clean Water and Sanitation',
            'clean-energy': 'Affordable and Clean Energy',
            'economic-growth': 'Decent Work and Economic Growth',
            'industry-innovation': 'Industry, Innovation and Infrastructure',
            'reduced-inequalities': 'Reduced Inequalities',
            'sustainable-cities': 'Sustainable Cities and Communities',
            'responsible-consumption': 'Responsible Consumption and Production',
            'climate-action': 'Climate Action',
            'life-below-water': 'Life Below Water',
            'life-on-land': 'Life on Land',
            'peace-justice': 'Peace, Justice and Strong Institutions',
            'partnerships': 'Partnerships for the Goals',
        }
        category = track_map.get(track, '')
        if not category:
            raw_category = idea.final_category or idea.ai_suggested_category or ''
            category_map = {
                'other': 'Partnerships for the Goals', 'incoherent': 'Partnerships for the Goals',
                'healthtech': 'Good Health and Well-Being', 'edtech': 'Quality Education',
                'agritech': 'Zero Hunger', 'sustainability': 'Climate Action',
                'fintech': 'Decent Work and Economic Growth', 'social_impact': 'Reduced Inequalities',
                'technology': 'Industry, Innovation and Infrastructure',
                'entertainment': 'Sustainable Cities and Communities',
            }
            category = category_map.get(raw_category.lower(), 'General')

        title = idea.title or ''
        if not title and idea.q3_solution_simple:
            title = idea.q3_solution_simple[:60]
        if not title:
            title = 'Untitled'

        # Slug for filtering
        category_slug = track if track else category.lower().replace(' ', '-')

        # Get AI summary if available
        ai_summary_text = ''
        try:
            ai_summary_text = idea.ai_summary.summary or ''
        except:
            pass

        idea_list.append({
            'id': idea.id,
            'title': title,
            'pitch': ai_summary_text[:200] if ai_summary_text else (idea.q3_solution_simple or '')[:100] + '...',
            'category': category,
            'category_slug': category_slug,
            'student_name': idea.student.user.get_full_name() or 'Anonymous',
            'school_name': idea.student.school_display_name or 'Not specified',
            'student_initial': idea.student.user.first_name[:1].upper() if idea.student.user.first_name else 'A',
            'ai_summary': ai_summary_text,
            'tags': [category],
            'submitted_at': idea.submitted_at,
            'like_count': idea.like_count,
            'liked': idea.id in liked_ids,
            'bookmarked': idea.id in bookmarked_ids,
        })

    context = {
        'ideas': idea_list,
        'total_ideas': total_ideas,
        'total_schools': total_schools,
        'student': request.user.student_profile if hasattr(request.user, 'student_profile') else None,
    }
    return render(request, 'students/idea_corner.html', context)


@login_required
@require_POST
def toggle_idea_like(request, idea_id):
    """Like / unlike a published idea. Returns the new like count + state."""
    idea = get_object_or_404(
        IdeaSubmission, id=idea_id,
        status__in=['submitted', 'evaluated', 'reviewed']
    )
    like, created = IdeaLike.objects.get_or_create(submission=idea, user=request.user)
    if not created:
        like.delete()
        liked = False
    else:
        liked = True
    count = IdeaLike.objects.filter(submission=idea).count()
    return JsonResponse({'success': True, 'liked': liked, 'like_count': count})


@login_required
@require_POST
def toggle_idea_bookmark(request, idea_id):
    """Bookmark / un-bookmark a published idea. Returns the new state."""
    idea = get_object_or_404(
        IdeaSubmission, id=idea_id,
        status__in=['submitted', 'evaluated', 'reviewed']
    )
    bm, created = IdeaBookmark.objects.get_or_create(submission=idea, user=request.user)
    if not created:
        bm.delete()
        bookmarked = False
    else:
        bookmarked = True
    return JsonResponse({'success': True, 'bookmarked': bookmarked})


@login_required
@require_POST
def push_subscribe(request):
    """Store a browser Web Push subscription for the current user."""
    from students.models import PushSubscription
    import json as _json
    try:
        data = _json.loads(request.body)
        sub = data.get('subscription') or {}
        endpoint = sub.get('endpoint')
        keys = sub.get('keys') or {}
        p256dh = keys.get('p256dh')
        auth = keys.get('auth')
        if not (endpoint and p256dh and auth):
            return JsonResponse({'success': False, 'message': 'Invalid subscription.'}, status=400)
        PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                'user': request.user,
                'p256dh': p256dh,
                'auth': auth,
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:300],
            },
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@login_required
def evaluator_dashboard(request):
    """Dashboard for evaluators showing assigned ideas and stats."""
    from admins.models import EvaluatorAssignment
    from django.db.models import Avg, Count

    assignments = EvaluatorAssignment.objects.filter(
        evaluator=request.user
    ).select_related('submission', 'submission__student__user', 'submission__student__school').order_by('-assigned_on')

    total = assignments.count()
    evaluated = assignments.filter(status='evaluated').count()
    pending = assignments.filter(status__in=['assigned', 'in_progress']).count()
    in_progress = assignments.filter(status='in_progress').count()

    # Avg score of evaluated
    avg_score = 0
    evaluated_assignments = assignments.filter(status='evaluated', score__isnull=False)
    if evaluated_assignments.exists():
        avg_score = round(evaluated_assignments.aggregate(avg=Avg('score'))['avg'] or 0, 1)

    # Completion percentage
    completion_pct = round((evaluated / max(total, 1)) * 100)

    # Get jury profile
    jury_profile = None
    try:
        jury_profile = request.user.jury_profile
    except Exception:
        pass

    context = {
        'assignments': assignments,
        'total': total,
        'evaluated': evaluated,
        'pending': pending,
        'in_progress': in_progress,
        'avg_score': avg_score,
        'completion_pct': completion_pct,
        'jury_profile': jury_profile,
    }
    return render(request, 'students/evaluator_dashboard.html', context)


@login_required
def evaluator_assigned_ideas(request):
    """Evaluator — view all assigned ideas with filters."""
    from admins.models import EvaluatorAssignment

    status_filter = request.GET.get('status', '')
    search = request.GET.get('q', '').strip()

    assignments = EvaluatorAssignment.objects.filter(
        evaluator=request.user
    ).select_related('submission', 'submission__student__user', 'submission__student__school').order_by('-assigned_on')

    if status_filter == 'shortlisted':
        assignments = assignments.filter(is_shortlisted=True)
    elif status_filter:
        assignments = assignments.filter(status=status_filter)

    if search:
        from django.db.models import Q
        assignments = assignments.filter(
            Q(submission__title__icontains=search) |
            Q(submission__student__user__first_name__icontains=search) |
            Q(submission__student__user__last_name__icontains=search)
        )

    all_assignments = EvaluatorAssignment.objects.filter(evaluator=request.user)
    total = all_assignments.count()
    pending = all_assignments.filter(status__in=['assigned', 'in_progress']).count()
    evaluated = all_assignments.filter(status='evaluated').count()
    shortlisted = all_assignments.filter(is_shortlisted=True).count()

    from django.core.paginator import Paginator
    paginator = Paginator(assignments, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    jury_profile = None
    try:
        jury_profile = request.user.jury_profile
    except:
        pass

    context = {
        'assignments': page_obj,
        'total': total,
        'pending': pending,
        'evaluated': evaluated,
        'shortlisted': shortlisted,
        'status_filter': status_filter,
        'search_query': search,
        'jury_profile': jury_profile,
    }
    return render(request, 'students/evaluator_assigned_ideas.html', context)


@login_required
def notifications_page(request):
    """Notifications page."""
    from students.models import Notification
    try:
        student = request.user.student_profile
    except:
        student = None

    notifications = Notification.objects.filter(user=request.user)

    from admins.models import Content
    from accounts.context_processors import _visibility_for_role
    role = getattr(getattr(request.user, 'profile', None), 'role', 'student')
    vis = _visibility_for_role(role)
    content_qs = Content.objects.filter(
        status='published', visibility__in=vis
    ).order_by('-created_at')[:20]

    combined = []
    for n in notifications[:50]:
        combined.append({'type': 'notif', 'id': n.id, 'title': n.title, 'message': n.message, 'icon': n.icon or 'notifications', 'is_read': n.is_read, 'created_at': n.created_at, 'notif_type': n.notification_type, 'action_url': n.action_url})
    icon_map = {'announcement': 'campaign', 'training': 'event', 'faq': 'quiz'}
    for c in content_qs:
        combined.append({'type': 'content', 'id': f'content-{c.id}', 'title': c.title, 'message': c.body or c.subtitle or '', 'icon': icon_map.get(c.content_type, 'campaign'), 'is_read': False, 'created_at': c.created_at, 'notif_type': c.content_type, 'action_url': ''})
    combined.sort(key=lambda x: x['created_at'], reverse=True)

    content_count = content_qs.count()
    announcement_content_count = len([c for c in content_qs if c.content_type == 'announcement'])
    context = {
        'student': student,
        'combined_notifications': combined,
        'total': len(combined),
        'unread': notifications.filter(is_read=False).count() + content_count,
        'team_count': notifications.filter(notification_type='team').count(),
        'submission_count': notifications.filter(notification_type='submission').count(),
        'announcement_count': notifications.filter(notification_type='announcement').count() + announcement_content_count,
    }
    return render(request, 'students/notifications.html', context)


@login_required
def mark_notification_read(request, notification_id):
    """Mark single notification as read."""
    from students.models import Notification
    if request.method == 'POST':
        Notification.objects.filter(id=notification_id, user=request.user).update(is_read=True)
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'POST required'}, status=405)


@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read, and clear announcement badges too."""
    from students.models import Notification
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        # Also clear the announcement/content part of the bell badge.
        profile = getattr(request.user, 'profile', None)
        if profile is not None:
            profile.announcements_read_at = timezone.now()
            profile.save(update_fields=['announcements_read_at'])
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'POST required'}, status=405)


@login_required
def school_teams(request):
    """School admin — Idea Submissions list (with team members column)."""
    from students.models import School, TeamMembership, IdeaSubmission
    from django.core.paginator import Paginator

    try:
        school = request.user.school_profile
    except School.DoesNotExist:
        return redirect('accounts:sign_in')

    if school.status != 'active':
        return redirect('students:school_dashboard')

    search = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')

    submissions = IdeaSubmission.objects.filter(
        student__school=school
    ).select_related('student__user').order_by('-created_at')

    if search:
        submissions = submissions.filter(
            Q(title__icontains=search) |
            Q(student__user__first_name__icontains=search) |
            Q(student__user__last_name__icontains=search) |
            Q(q3_solution_simple__icontains=search)
        )

    if status_filter:
        submissions = submissions.filter(status=status_filter)

    # Build list with extra data
    sub_list = []
    for s in submissions:
        ai_score = None
        is_top_400 = False
        try:
            ev = s.ai_evaluation
            ai_score = ev.final_score
            is_top_400 = ev.is_top_400
        except Exception:
            pass

        # Resolve team (leader membership preferred) for name + members
        leader_membership = TeamMembership.objects.filter(
            student=s.student, role='leader'
        ).select_related('team').first()
        team = leader_membership.team if leader_membership else None
        if team is None:
            membership = TeamMembership.objects.filter(
                student=s.student
            ).select_related('team').first()
            team = membership.team if membership else None

        team_name = team.name if team else s.student.user.get_full_name()
        member_dots = []
        if team:
            for m in team.memberships.filter(status='active').select_related('student__user'):
                if not m.student:
                    continue
                mu = m.student.user
                full = mu.get_full_name() or mu.username
                initial = (mu.first_name[:1] or mu.username[:1]).upper()
                member_dots.append({'name': full, 'initial': initial, 'role': m.role})

        sub_list.append({
            'id': s.id,
            'title': (s.title or s.q3_solution_simple or 'Untitled')[:60],
            'student_name': s.student.user.get_full_name(),
            'team_name': team_name,
            'members': member_dots,
            'track': s.get_competition_track_display() if s.competition_track else '',
            'status': s.status,
            'status_label': s.get_status_display(),
            'ai_score': ai_score,
            'is_top_400': is_top_400,
            'submitted_at': s.submitted_at or s.created_at,
            'grade': s.student.grade,
        })

    # Stats
    all_subs = IdeaSubmission.objects.filter(student__school=school)
    total = all_subs.count()
    draft_count = all_subs.filter(status='draft').count()
    submitted_count = all_subs.filter(status='submitted').count()
    evaluated_count = all_subs.filter(status='evaluated').count()

    # Pagination
    paginator = Paginator(sub_list, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'school': school,
        'submissions': page_obj,
        'total': total,
        'draft_count': draft_count,
        'submitted_count': submitted_count,
        'evaluated_count': evaluated_count,
        'search_query': search,
        'status_filter': status_filter,
    }
    return render(request, 'students/school_submissions.html', context)


@login_required
def school_students(request):
    """School admin — view enrolled students."""
    from students.models import School, Student, TeamMembership, IdeaSubmission

    try:
        school = request.user.school_profile
    except School.DoesNotExist:
        return redirect('accounts:sign_in')

    if school.status != 'active':
        return redirect('students:school_dashboard')

    search = request.GET.get('q', '').strip()
    grade_filter = request.GET.get('grade', '')
    status_filter = request.GET.get('status', '')

    students_qs = Student.objects.filter(school=school).select_related('user')

    if search:
        students_qs = students_qs.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(student_id__icontains=search)
        )
    if grade_filter:
        students_qs = students_qs.filter(grade=grade_filter)

    # Annotate with team and submission info
    student_list = []
    for s in students_qs:
        membership = TeamMembership.objects.filter(student=s).select_related('team').first()
        team_name = membership.team.name if membership else ''
        idea = IdeaSubmission.objects.filter(student=s).exclude(status='draft').first()
        idea_title = (idea.title or idea.q3_solution_simple or '')[:40] if idea else ''
        idea_desc = (idea.q3_solution_simple or idea.q2_exact_problem or '')[:80] if idea else ''

        # Get AI score
        ai_score = None
        if idea:
            try:
                ai_score = idea.ai_evaluation.final_score
            except:
                pass

        # Status
        if idea:
            stu_status = 'submitted'
        elif membership:
            stu_status = 'in-team'
        else:
            stu_status = 'no-team'

        if status_filter:
            if status_filter == 'in-team' and stu_status != 'in-team':
                continue
            if status_filter == 'no-team' and stu_status != 'no-team':
                continue
            if status_filter == 'submitted' and stu_status != 'submitted':
                continue

        student_list.append({
            'id': s.id,
            'first_name': s.user.first_name,
            'last_name': s.user.last_name,
            'email': s.user.email,
            'grade': s.grade,
            'division': s.division,
            'student_id': s.student_id,
            'team_name': team_name,
            'idea_title': idea_title,
            'idea_desc': idea_desc,
            'ai_score': ai_score,
            'status': stu_status,
            'phone': s.phone,
            'created_at': s.created_at,
            'is_paid': s.is_paid,
            'payment_transaction_id': s.payment_transaction_id,
        })

    # Stats
    all_students = Student.objects.filter(school=school)
    total = all_students.count()
    in_teams = sum(1 for sl in student_list if sl['status'] in ['in-team', 'submitted'])
    no_teams = total - in_teams
    submitted = sum(1 for sl in student_list if sl['status'] == 'submitted')

    # Bento-box metrics for the Students tab
    from students.models import Team as _Team
    registered_count = total
    paid_count = all_students.filter(is_paid=True).count()
    school_total_students = school.total_students or total
    teams_count = _Team.objects.filter(memberships__student__school=school).distinct().count()
    ideas_count = IdeaSubmission.objects.filter(student__school=school).exclude(status='draft').count()

    # Grades for filter
    grades = all_students.values_list('grade', flat=True).distinct().order_by('grade')

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(student_list, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'school': school,
        'students': page_obj,
        'total': total,
        'active_count': total,
        'in_teams': in_teams,
        'no_teams': no_teams,
        'grades': grades,
        'search_query': search,
        'grade_filter': grade_filter,
        'status_filter': status_filter,
        'registered_count': registered_count,
        'paid_count': paid_count,
        'school_total_students': school_total_students,
        'teams_count': teams_count,
        'ideas_count': ideas_count,
    }
    return render(request, 'students/school_students.html', context)


@login_required
def school_submissions(request):
    """Merged into school_teams — redirect for backward compat."""
    return redirect('students:school_teams')


def _school_submissions_legacy(request):
    """(kept only for reference; no longer routed)"""
    from students.models import School, Student, IdeaSubmission, TeamMembership
    from ai_assistant.models import AIEvaluation
    from django.db.models import Q

    try:
        school = request.user.school_profile
    except School.DoesNotExist:
        return redirect('accounts:sign_in')

    if school.status != 'active':
        return redirect('students:school_dashboard')

    search = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')

    submissions = IdeaSubmission.objects.filter(
        student__school=school
    ).select_related('student__user').order_by('-created_at')

    if search:
        submissions = submissions.filter(
            Q(title__icontains=search) |
            Q(student__user__first_name__icontains=search) |
            Q(student__user__last_name__icontains=search) |
            Q(q3_solution_simple__icontains=search)
        )

    if status_filter:
        submissions = submissions.filter(status=status_filter)

    # Build list with extra data
    sub_list = []
    for s in submissions:
        ai_score = None
        is_top_400 = False
        try:
            ev = s.ai_evaluation
            ai_score = ev.final_score
            is_top_400 = ev.is_top_400
        except:
            pass

        # Get team name
        membership = TeamMembership.objects.filter(student=s.student, role='leader').select_related('team').first()
        team_name = membership.team.name if membership else s.student.user.get_full_name()

        sub_list.append({
            'id': s.id,
            'title': (s.title or s.q3_solution_simple or 'Untitled')[:60],
            'student_name': s.student.user.get_full_name(),
            'team_name': team_name,
            'track': s.get_competition_track_display() if s.competition_track else '',
            'status': s.status,
            'status_label': s.get_status_display(),
            'ai_score': ai_score,
            'is_top_400': is_top_400,
            'submitted_at': s.submitted_at or s.created_at,
            'grade': s.student.grade,
        })

    # Stats
    all_subs = IdeaSubmission.objects.filter(student__school=school)
    total = all_subs.count()
    draft_count = all_subs.filter(status='draft').count()
    submitted_count = all_subs.filter(status='submitted').count()
    evaluated_count = all_subs.filter(status='evaluated').count()

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(sub_list, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'school': school,
        'submissions': page_obj,
        'total': total,
        'draft_count': draft_count,
        'submitted_count': submitted_count,
        'evaluated_count': evaluated_count,
        'search_query': search,
        'status_filter': status_filter,
    }
    return render(request, 'students/school_submissions.html', context)


@login_required
def school_results(request):
    """School admin — view evaluation results for this school."""
    from students.models import School, Student, IdeaSubmission
    from ai_assistant.models import AIEvaluation
    from django.db.models import Avg, Count, Q

    try:
        school = request.user.school_profile
    except School.DoesNotExist:
        return redirect('accounts:sign_in')

    if school.status != 'active':
        return redirect('students:school_dashboard')

    # Get all evaluations for this school
    evaluations = AIEvaluation.objects.filter(
        submission__student__school=school
    ).select_related('submission', 'submission__student__user').order_by('-final_score')

    # Stats
    total_evaluated = evaluations.count()
    top_400_count = evaluations.filter(is_top_400=True).count()
    avg_score = evaluations.aggregate(avg=Avg('final_score'))['avg'] or 0
    highest_score = evaluations.first().final_score if evaluations.exists() else 0

    # Parameter-wise averages
    param_avgs = evaluations.aggregate(
        uniqueness=Avg('uniqueness_score'),
        ease=Avg('ease_of_implementation_score'),
        feasibility=Avg('feasibility_score'),
        impact=Avg('impactful_score'),
        sustainability=Avg('sustainable_score'),
        clarity=Avg('conceptual_clarity_score'),
        empathy=Avg('empathy_score'),
        creativity=Avg('creativity_score'),
        communication=Avg('communication_score'),
        flexible=Avg('flexible_thinking_score'),
    )

    # Build results list
    results_list = []
    for i, ev in enumerate(evaluations):
        s = ev.submission
        results_list.append({
            'rank': i + 1,
            'title': (s.title or s.q3_solution_simple or 'Untitled')[:50],
            'student_name': s.student.user.get_full_name(),
            'student_initial': (s.student.user.first_name[:1] + s.student.user.last_name[:1]).upper() if s.student.user.first_name and s.student.user.last_name else 'S',
            'grade': s.student.grade,
            'score': ev.final_score,
            'is_top_400': ev.is_top_400,
            'global_rank': ev.rank,
            'id': s.id,
        })

    # Top 3 for podium
    top_3 = results_list[:3] if len(results_list) >= 3 else results_list

    # Remaining for leaderboard (4+)
    remaining = results_list[3:] if len(results_list) > 3 else []

    # Pagination on remaining
    from django.core.paginator import Paginator
    paginator = Paginator(remaining, 18)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'school': school,
        'results': page_obj,
        'all_results': results_list,
        'top_3': top_3,
        'total_evaluated': total_evaluated,
        'top_400_count': top_400_count,
        'avg_score': round(avg_score, 1),
        'highest_score': highest_score,
        'param_avgs': {k: round(v or 0, 1) for k, v in param_avgs.items()},
    }
    return render(request, 'students/school_results.html', context)


@login_required
def school_reports(request):
    """School admin — reports & analytics for this school."""
    from students.models import School, Student, Team, TeamMembership, IdeaSubmission
    from ai_assistant.models import AIEvaluation
    from admins.models import Phase
    from django.db.models import Avg, Count, Q
    from django.db.models.functions import TruncMonth
    from datetime import timedelta

    try:
        school = request.user.school_profile
    except School.DoesNotExist:
        return redirect('accounts:sign_in')

    if school.status != 'active':
        return redirect('students:school_dashboard')

    now = timezone.now()

    # Students
    students = Student.objects.filter(school=school)
    student_count = students.count()

    # Teams
    leader_ids = TeamMembership.objects.filter(student__school=school, role='leader').values_list('team_id', flat=True)
    teams_count = len(set(leader_ids))

    # Submissions
    all_subs = IdeaSubmission.objects.filter(student__school=school)
    total_subs = all_subs.count()
    draft_count = all_subs.filter(status='draft').count()
    submitted_count = all_subs.filter(status='submitted').count()
    evaluated_count = all_subs.filter(status='evaluated').count()

    # Participation rate
    participation_rate = round((total_subs / max(student_count, 1)) * 100)

    # AI Scores
    evaluations = AIEvaluation.objects.filter(submission__student__school=school)
    avg_score = evaluations.aggregate(avg=Avg('final_score'))['avg'] or 0
    top_400 = evaluations.filter(is_top_400=True).count()
    highest_score = evaluations.order_by('-final_score').values_list('final_score', flat=True).first() or 0

    # Grade-wise breakdown
    grade_data = students.values('grade').annotate(count=Count('id')).order_by('grade')
    grade_max = max((g['count'] for g in grade_data), default=1)

    # Track-wise breakdown (from submissions)
    track_data = all_subs.exclude(competition_track='').values('competition_track').annotate(count=Count('id')).order_by('-count')
    track_max = max((t['count'] for t in track_data), default=1)

    # Parameter averages
    param_avgs = evaluations.aggregate(
        uniqueness=Avg('uniqueness_score'),
        ease=Avg('ease_of_implementation_score'),
        feasibility=Avg('feasibility_score'),
        impact=Avg('impactful_score'),
        sustainability=Avg('sustainable_score'),
        clarity=Avg('conceptual_clarity_score'),
        empathy=Avg('empathy_score'),
        creativity=Avg('creativity_score'),
        communication=Avg('communication_score'),
        flexible=Avg('flexible_thinking_score'),
    )

    # Monthly trend
    six_months_ago = now - timedelta(days=180)
    monthly_trend = list(all_subs.filter(created_at__gte=six_months_ago).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(count=Count('id')).order_by('month'))
    monthly_max = max((m['count'] for m in monthly_trend), default=1)

    # Top 5 performers
    top_5 = evaluations.select_related(
        'submission', 'submission__student__user'
    ).order_by('-final_score')[:5]

    top_performers = []
    for i, ev in enumerate(top_5):
        s = ev.submission
        membership = TeamMembership.objects.filter(student=s.student, role='leader').select_related('team').first()
        team_name = membership.team.name if membership else '-'
        top_performers.append({
            'rank': i + 1,
            'student_name': s.student.user.get_full_name(),
            'team_name': team_name,
            'idea_title': (s.title or s.q3_solution_simple or 'Untitled')[:40],
            'score': ev.final_score,
        })

    # Circle chart offsets (circumference = 2 * pi * 54 ≈ 339.29)
    circumference = 339.29
    registration_pct = 100  # always done
    registration_offset = 0
    submission_pct = round((total_subs / max(student_count, 1)) * 100) if student_count else 0
    submission_offset = round(circumference - (circumference * submission_pct / 100), 1)
    evaluated_pct_val = round((evaluated_count / max(total_subs, 1)) * 100) if total_subs else 0
    evaluated_offset = round(circumference - (circumference * evaluated_pct_val / 100), 1)
    shortlisted_pct = round((top_400 / max(evaluated_count, 1)) * 100) if evaluated_count else 0
    shortlisted_offset = round(circumference - (circumference * shortlisted_pct / 100), 1)

    # Grade participation for bar chart (with colors)
    grade_colors = [
        ('#7c3aed', '#a78bfa'), ('#5E2A97', '#9061c2'), ('#4c1d95', '#7c3aed'),
        ('#6d28d9', '#a78bfa'), ('#8b5cf6', '#c4b5fd'), ('#7e22ce', '#a855f7'),
    ]
    grade_participation = []
    for i, g in enumerate(grade_data):
        height_pct = round((g['count'] / max(grade_max, 1)) * 100)
        c = grade_colors[i % len(grade_colors)]
        grade_participation.append({
            'grade': g['grade'],
            'count': g['count'],
            'height_pct': height_pct,
            'color_start': c[0],
            'color_end': c[1],
        })

    # Score distribution buckets
    score_buckets = [
        {'range': '0-20', 'min': 0, 'max': 20, 'color_start': '#ef4444', 'color_end': '#f87171', 'label_bg': 'rgba(239,68,68,0.1)'},
        {'range': '21-40', 'min': 21, 'max': 40, 'color_start': '#f59e0b', 'color_end': '#fbbf24', 'label_bg': 'rgba(245,158,11,0.1)'},
        {'range': '41-60', 'min': 41, 'max': 60, 'color_start': '#3b82f6', 'color_end': '#60a5fa', 'label_bg': 'rgba(59,130,246,0.1)'},
        {'range': '61-80', 'min': 61, 'max': 80, 'color_start': '#8b5cf6', 'color_end': '#a78bfa', 'label_bg': 'rgba(139,92,246,0.1)'},
        {'range': '81-100', 'min': 81, 'max': 100, 'color_start': '#22c55e', 'color_end': '#4ade80', 'label_bg': 'rgba(34,197,94,0.1)'},
    ]
    score_distribution = []
    score_counts = []
    for bucket in score_buckets:
        count = evaluations.filter(final_score__gte=bucket['min'], final_score__lte=bucket['max']).count()
        score_counts.append(count)
        score_distribution.append({**bucket, 'count': count})
    score_dist_max = max(score_counts) if score_counts else 1
    for sd in score_distribution:
        sd['height_pct'] = round((sd['count'] / max(score_dist_max, 1)) * 100)

    # Categories donut data
    track_map = dict(IdeaSubmission.TRACK_CHOICES)
    cat_colors = ['#5E2A97', '#0EA5E9', '#F59E0B', '#10B981', '#EF4444', '#8B5CF6']
    categories = []
    total_track = sum(t['count'] for t in track_data) or 1
    cumulative = 0
    for i, t in enumerate(track_data):
        pct = round((t['count'] / total_track) * 100)
        dash = round(339.29 * pct / 100, 1)
        rotation = round(cumulative * 3.6, 1)
        categories.append({
            'name': track_map.get(t['competition_track'], t['competition_track']),
            'count': t['count'],
            'percentage': pct,
            'color': cat_colors[i % len(cat_colors)],
            'dash_offset': f"{dash} {round(339.29 - dash, 1)}",
            'rotation': rotation,
        })
        cumulative += pct

    # Grade avg scores
    grade_avg_scores = []
    for g in grade_data:
        grade_evals = evaluations.filter(submission__student__grade=g['grade'])
        g_avg = grade_evals.aggregate(avg=Avg('final_score'))['avg'] or 0
        grade_avg_scores.append({
            'grade': g['grade'],
            'avg_score': round(g_avg, 1),
            'width_pct': round(g_avg),
            'color': '#5E2A97' if g_avg >= 60 else '#f59e0b' if g_avg >= 40 else '#ef4444',
        })

    context = {
        'school': school,
        'total_students': student_count,
        'total_teams': teams_count,
        'total_submitted': total_subs,
        'participation_rate': participation_rate,
        'avg_score': round(avg_score, 1),
        'highest_score': highest_score,
        # Circle charts
        'registration_pct': registration_pct,
        'registration_offset': registration_offset,
        'submission_pct': submission_pct,
        'submission_offset': submission_offset,
        'evaluated_pct': evaluated_pct_val,
        'evaluated_offset': evaluated_offset,
        'shortlisted_pct': shortlisted_pct,
        'shortlisted_offset': shortlisted_offset,
        # Charts
        'draft_count': draft_count,
        'submitted_count': submitted_count,
        'evaluated_count': evaluated_count,
        'shortlisted_count': top_400,
        'categories': categories,
        'monthly_trend': monthly_trend,
        'monthly_max': monthly_max,
    }
    return render(request, 'students/school_reports.html', context)


@login_required
def school_halloffame(request):
    """School Hall of Fame — top performers from this school."""
    from students.models import School, Student, TeamMembership, IdeaSubmission
    from ai_assistant.models import AIEvaluation

    try:
        school = request.user.school_profile
    except School.DoesNotExist:
        return redirect('accounts:sign_in')

    if school.status != 'active':
        return redirect('students:school_dashboard')

    # Get top evaluated ideas from this school
    evaluations = AIEvaluation.objects.filter(
        submission__student__school=school
    ).select_related('submission', 'submission__student__user').order_by('-final_score')

    winners = []
    for i, ev in enumerate(evaluations[:20]):
        s = ev.submission
        membership = TeamMembership.objects.filter(student=s.student, role='leader').select_related('team').first()
        team_name = membership.team.name if membership else s.student.user.get_full_name()

        winners.append({
            'rank': i + 1,
            'student_name': s.student.user.get_full_name(),
            'team_name': team_name,
            'idea_title': (s.title or s.q3_solution_simple or 'Untitled')[:50],
            'score': ev.final_score,
            'is_top_400': ev.is_top_400,
            'grade': s.student.grade,
            'track': s.get_competition_track_display() if s.competition_track else '',
            'initial': s.student.user.first_name[:1].upper() if s.student.user.first_name else 'S',
        })

    # Top 3 for podium
    top_3 = winners[:3]
    rest = winners[3:]

    # Hall of Fame entries from admin-managed model
    from admins.models import HallOfFameEntry
    hof_entries = HallOfFameEntry.objects.filter(is_active=True)
    hof_seasons = hof_entries.values_list('season', flat=True).distinct().order_by('-season')
    hof_season = hof_seasons[0] if hof_seasons else ''
    if hof_season:
        hof_entries = hof_entries.filter(season=hof_season)

    context = {
        'school': school,
        'top_3': top_3,
        'rest': rest,
        'total_winners': len(winners),
        'podium': list(hof_entries.filter(rank__lte=3).order_by('rank')),
        'grid': list(hof_entries.filter(rank__gt=3).order_by('rank')),
        'current_season': hof_season,
    }
    return render(request, 'students/halloffame.html', context)


@login_required
def school_profile(request):
    """School profile page — view and edit school details."""
    from students.models import School

    try:
        school = request.user.school_profile
    except School.DoesNotExist:
        return redirect('accounts:sign_in')

    if request.method == 'POST':
        import json as json_mod
        if request.content_type == 'application/json':
            data = json_mod.loads(request.body)
        else:
            data = request.POST

        section = data.get('section', '')

        if section == 'basic':
            school.name = data.get('name', school.name).strip()
            school.branch = data.get('branch', school.branch).strip()
            school.board = data.get('board', school.board)
            school.affiliation_number = data.get('affiliation_number', school.affiliation_number).strip()
            school.school_type = data.get('school_type', school.school_type)
            school.medium = data.get('medium', school.medium).strip()
            school.established_year = int(data.get('established_year', 0)) if data.get('established_year') else school.established_year
            school.total_students = int(data.get('total_students', 0)) if data.get('total_students') else school.total_students
        elif section == 'location':
            school.address = data.get('address', school.address).strip()
            school.city = data.get('city', school.city).strip()
            school.state = data.get('state', school.state).strip()
            school.pin_code = data.get('pin_code', school.pin_code).strip()
            school.country = data.get('country', school.country).strip()
        elif section == 'contact':
            school.principal_name = data.get('principal_name', school.principal_name).strip()
            school.principal_email = data.get('principal_email', school.principal_email).strip()
            school.contact_phone = data.get('contact_phone', school.contact_phone).strip()
            school.website = data.get('website', school.website).strip()

        school.save()
        from django.http import JsonResponse
        return JsonResponse({'success': True, 'message': 'Profile updated successfully!'})

    # Stats
    from students.models import Student, TeamMembership, IdeaSubmission
    student_count = Student.objects.filter(school=school).count()
    team_count = len(set(TeamMembership.objects.filter(student__school=school, role='leader').values_list('team_id', flat=True)))
    ideas_count = IdeaSubmission.objects.filter(student__school=school).exclude(status='draft').count()

    context = {
        'school': school,
        'student_count': student_count,
        'team_count': team_count,
        'ideas_count': ideas_count,
    }
    return render(request, 'students/school_profile.html', context)


@login_required
def learning_resources(request):
    """Student Learning Resources page — same video library as the dashboard."""
    from students.models import LearningVideo, VideoProgress
    try:
        student = request.user.student_profile
    except:
        student = None

    videos = LearningVideo.objects.filter(is_active=True).order_by('order')
    watched_video_ids = set()
    if student:
        watched_video_ids = set(VideoProgress.objects.filter(student=student, watched=True).values_list('video_id', flat=True))
    video_list = [{
        'id': v.id,
        'title': v.title,
        'youtube_id': v.youtube_id,
        'youtube_url': v.youtube_url,
        'watched': v.id in watched_video_ids,
    } for v in videos]

    context = {
        'student': student,
        'learning_videos': video_list,
        'videos_total': len(video_list),
        'videos_watched': len([v for v in video_list if v['watched']]),
    }
    return render(request, 'students/learning_resources.html', context)


@login_required
def digital_resources(request):
    """Student-facing Digital Resources page — downloadable collaterals."""
    from admins.models import DigitalResource
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        student = None

    resources = DigitalResource.objects.filter(is_active=True, visibility__in=['all', 'students']).order_by('category', '-created_at')
    return render(request, 'students/digital_resources.html', {'student': student, 'resources': resources})


def student_faq(request):
    """Student FAQ page — shows published FAQs for students."""
    from admins.models import Content
    try:
        student = request.user.student_profile
    except:
        student = None
    faqs = Content.objects.filter(
        status='published',
        content_type='faq',
        visibility__in=['all', 'students']
    ).order_by('created_at')
    return render(request, 'students/student_faq.html', {'student': student, 'faqs': faqs})


@login_required
def school_submission_detail(request, submission_id):
    """School admin — view a full submission from their own school (school chrome)."""
    from students.models import School
    try:
        school = request.user.school_profile
    except School.DoesNotExist:
        return redirect('accounts:sign_in')

    submission = get_object_or_404(IdeaSubmission, id=submission_id)
    if not submission.student or submission.student.school_id != school.id:
        from django.http import Http404
        raise Http404("Submission not found.")

    ai_summary = None
    try:
        ai_summary = submission.ai_summary
    except Exception:
        pass

    questions = [
        {'label': 'Target User Group', 'answer': submission.q1_target_group or submission.target_user_group or 'Not provided'},
        {'label': 'Exact Problem', 'answer': submission.q2_exact_problem or submission.problem_definition or 'Not provided'},
        {'label': 'Solution (Simple)', 'answer': submission.q3_solution_simple or submission.solution or 'Not provided'},
        {'label': 'Differentiation', 'answer': submission.q4_differentiation or 'Not provided'},
        {'label': 'Build Steps', 'answer': submission.q5_build_steps or 'Not provided'},
        {'label': 'Resources Needed', 'answer': submission.q6_resources or 'Not provided'},
        {'label': 'Positive Change', 'answer': submission.q7_positive_change or submission.solution_benefits or 'Not provided'},
        {'label': 'Challenges', 'answer': submission.q8_challenges or 'Not provided'},
        {'label': 'Team Fit', 'answer': submission.q9_team_fit or submission.why_best_equipped or 'Not provided'},
        {'label': 'Feedback & Learning', 'answer': submission.q10_feedback or 'Not provided'},
        {'label': 'Creative Element', 'answer': submission.q11_creative_element or 'Not provided'},
        {'label': '60-Second Pitch', 'answer': submission.q12_pitch or 'Not provided'},
    ]

    context = {
        'school': school,
        'submission': submission,
        'ai_summary': ai_summary,
        'submitted_at': submission.submitted_at.strftime("%B %d, %Y") if submission.submitted_at else "Not submitted",
        'status_label': submission.get_status_display(),
        'questions': questions,
        'uploaded_files': submission.uploaded_files.all(),
    }
    return render(request, 'students/school_submission_detail.html', context)


@login_required
def school_learning_resources(request):
    """School Learning Resources page — same video library as the student page."""
    from students.models import School, LearningVideo
    try:
        school = request.user.school_profile
    except School.DoesNotExist:
        return redirect('accounts:sign_in')
    videos = LearningVideo.objects.filter(is_active=True).order_by('order')
    return render(request, 'students/school_learning_resources.html', {'school': school, 'learning_videos': videos})


@login_required
def school_digital_resources(request):
    """School-facing Digital Resources page — downloadable collaterals."""
    from students.models import School
    from admins.models import DigitalResource
    try:
        school = request.user.school_profile
    except School.DoesNotExist:
        return redirect('students:dashboard')

    resources = DigitalResource.objects.filter(is_active=True, visibility__in=['all', 'schools']).order_by('category', '-created_at')
    return render(request, 'students/school_digital_resources.html', {'school': school, 'resources': resources})


@login_required
def school_faq(request):
    """School FAQ page — shows published FAQs from Content model."""
    from students.models import School
    from admins.models import Content

    try:
        school = request.user.school_profile
    except School.DoesNotExist:
        return redirect('accounts:sign_in')

    faqs = Content.objects.filter(
        status='published',
        content_type='faq',
        visibility__in=['all', 'schools']
    ).order_by('created_at')

    context = {
        'school': school,
        'faqs': faqs,
    }
    return render(request, 'students/school_faq.html', context)


@login_required
def evaluator_evaluate_idea(request, assignment_id):
    """Evaluator — evaluate an assigned idea with manual scoring."""
    from admins.models import EvaluatorAssignment
    from ai_assistant.models import AIEvaluation
    from django.http import JsonResponse

    assignment = get_object_or_404(EvaluatorAssignment, id=assignment_id, evaluator=request.user)
    submission = assignment.submission

    if request.method == 'POST':
        import json as json_mod
        if request.content_type == 'application/json':
            data = json_mod.loads(request.body)
        else:
            data = request.POST

        # Save parameter scores
        param_scores = {
            'uniqueness': int(data.get('uniqueness', 0)),
            'ease_of_implementation': int(data.get('ease_of_implementation', 0)),
            'feasibility': int(data.get('feasibility', 0)),
            'impactful': int(data.get('impactful', 0)),
            'sustainable': int(data.get('sustainable', 0)),
            'conceptual_clarity': int(data.get('conceptual_clarity', 0)),
            'empathy': int(data.get('empathy', 0)),
            'creativity': int(data.get('creativity', 0)),
            'communication': int(data.get('communication', 0)),
            'flexible_thinking': int(data.get('flexible_thinking', 0)),
        }
        assignment.parameter_scores = param_scores
        assignment.score = sum(param_scores.values())
        assignment.notes = data.get('notes', '').strip()
        assignment.is_shortlisted = data.get('is_shortlisted', False) in [True, 'true', 'True', 1, '1']
        assignment.status = 'evaluated'
        assignment.evaluated_on = timezone.now()
        assignment.save()

        return JsonResponse({'success': True, 'message': 'Evaluation submitted successfully!'})

    # Get AI evaluation for reference
    ai_eval = None
    try:
        ai_eval = submission.ai_evaluation
    except:
        pass

    # Get submission questions
    questions = {
        'q1': submission.q1_target_group or '',
        'q2': submission.q2_exact_problem or '',
        'q3': submission.q3_solution_simple or '',
        'q4': submission.q4_differentiation or '',
        'q5': submission.q5_build_steps or '',
        'q6': submission.q6_resources or '',
        'q7': submission.q7_positive_change or '',
        'q8': submission.q8_challenges or '',
        'q9': submission.q9_team_fit or '',
        'q10': submission.q10_feedback or '',
        'q11': submission.q11_creative_element or '',
        'q12': submission.q12_pitch or '',
    }

    # Uploaded files
    files = list(submission.uploaded_files.all())

    # Team info
    from students.models import TeamMembership
    membership = TeamMembership.objects.filter(student=submission.student, role='leader').select_related('team').first()
    team_name = membership.team.name if membership else submission.student.user.get_full_name()

    jury_profile = None
    try:
        jury_profile = request.user.jury_profile
    except:
        pass

    context = {
        'assignment': assignment,
        'submission': submission,
        'ai_eval': ai_eval,
        'questions': questions,
        'files': files,
        'team_name': team_name,
        'jury_profile': jury_profile,
    }
    return render(request, 'students/evaluator_evaluate.html', context)


@login_required
def evaluator_profile(request):
    """Evaluator profile page — view and edit details."""
    from accounts.models import JuryProfile
    from admins.models import EvaluatorAssignment
    from django.http import JsonResponse

    jury_profile = None
    try:
        jury_profile = request.user.jury_profile
    except JuryProfile.DoesNotExist:
        pass

    if request.method == 'POST':
        import json as json_mod
        if request.content_type == 'application/json':
            data = json_mod.loads(request.body)
        else:
            data = request.POST

        section = data.get('section', '')

        if jury_profile:
            if section == 'personal':
                request.user.first_name = data.get('first_name', request.user.first_name).strip()
                request.user.last_name = data.get('last_name', request.user.last_name).strip()
                jury_profile.gender = data.get('gender', jury_profile.gender)
                jury_profile.nationality = data.get('nationality', jury_profile.nationality)
                jury_profile.city = data.get('city', jury_profile.city)
                jury_profile.state = data.get('state', jury_profile.state)
                request.user.save()
            elif section == 'professional':
                jury_profile.designation = data.get('designation', jury_profile.designation)
                jury_profile.organization = data.get('organization', jury_profile.organization)
                jury_profile.industry = data.get('industry', jury_profile.industry)
                jury_profile.experience = data.get('experience', jury_profile.experience)
                jury_profile.qualification = data.get('qualification', jury_profile.qualification)
                jury_profile.linkedin_url = data.get('linkedin_url', jury_profile.linkedin_url)
                jury_profile.bio = data.get('bio', jury_profile.bio)
            elif section == 'contact':
                jury_profile.phone = data.get('phone', jury_profile.phone)
                jury_profile.alternate_phone = data.get('alternate_phone', jury_profile.alternate_phone)
                jury_profile.alternate_email = data.get('alternate_email', jury_profile.alternate_email)
                jury_profile.address = data.get('address', jury_profile.address)
                jury_profile.pin_code = data.get('pin_code', jury_profile.pin_code)
                jury_profile.preferred_contact = data.get('preferred_contact', jury_profile.preferred_contact)
            elif section == 'availability':
                jury_profile.available_from = data.get('available_from', '') or jury_profile.available_from
                jury_profile.available_to = data.get('available_to', '') or jury_profile.available_to
                jury_profile.preferred_time = data.get('preferred_time', jury_profile.preferred_time)
                jury_profile.evaluation_mode = data.get('evaluation_mode', jury_profile.evaluation_mode)
                jury_profile.willing_to_mentor = data.get('willing_to_mentor', jury_profile.willing_to_mentor)
            jury_profile.save()

        return JsonResponse({'success': True, 'message': 'Profile updated successfully!'})

    # Stats
    assignments = EvaluatorAssignment.objects.filter(evaluator=request.user)
    total_assigned = assignments.count()
    total_evaluated = assignments.filter(status='evaluated').count()
    shortlisted = assignments.filter(is_shortlisted=True).count()

    context = {
        'jury_profile': jury_profile,
        'total_assigned': total_assigned,
        'total_evaluated': total_evaluated,
        'shortlisted': shortlisted,
        'pending_count': total_assigned - total_evaluated,
    }
    return render(request, 'students/evaluator_profile.html', context)


@login_required
def student_halloffame(request):
    """Student Hall of Fame — dynamic from HallOfFameEntry model."""
    from admins.models import HallOfFameEntry
    entries = HallOfFameEntry.objects.filter(is_active=True)
    seasons = entries.values_list('season', flat=True).distinct().order_by('-season')
    season = request.GET.get('season', '')
    if not season and seasons:
        season = seasons[0]
    if season:
        entries = entries.filter(season=season)

    podium = list(entries.filter(rank__lte=3).order_by('rank'))
    grid = list(entries.filter(rank__gt=3).order_by('rank'))

    return render(request, 'students/halloffame.html', {
        'podium': podium,
        'grid': grid,
        'seasons': seasons,
        'current_season': season,
    })


@login_required
def evaluator_halloffame(request):
    """Evaluator Hall of Fame — top ideas evaluated by this evaluator."""
    from admins.models import EvaluatorAssignment
    from students.models import TeamMembership

    assignments = EvaluatorAssignment.objects.filter(
        evaluator=request.user, status='evaluated'
    ).select_related('submission', 'submission__student__user').order_by('-score')

    winners = []
    for i, a in enumerate(assignments[:20]):
        s = a.submission
        membership = TeamMembership.objects.filter(student=s.student, role='leader').select_related('team').first()
        team_name = membership.team.name if membership else s.student.user.get_full_name()

        winners.append({
            'rank': i + 1,
            'student_name': s.student.user.get_full_name(),
            'team_name': team_name,
            'idea_title': (s.title or s.q3_solution_simple or 'Untitled')[:50],
            'score': a.score,
            'is_shortlisted': a.is_shortlisted,
            'initial': s.student.user.first_name[:1].upper() if s.student.user.first_name else 'S',
        })

    top_3 = winners[:3]
    rest = winners[3:]

    # Hall of Fame entries from admin-managed model
    from admins.models import HallOfFameEntry
    hof_entries = HallOfFameEntry.objects.filter(is_active=True)
    hof_seasons = hof_entries.values_list('season', flat=True).distinct().order_by('-season')
    hof_season = hof_seasons[0] if hof_seasons else ''
    if hof_season:
        hof_entries = hof_entries.filter(season=hof_season)

    context = {
        'top_3': top_3,
        'rest': rest,
        'total_winners': len(winners),
        'podium': list(hof_entries.filter(rank__lte=3).order_by('rank')),
        'grid': list(hof_entries.filter(rank__gt=3).order_by('rank')),
        'current_season': hof_season,
    }
    return render(request, 'students/halloffame.html', context)


@login_required
def evaluator_faq(request):
    """Evaluator FAQ page — shows published FAQs."""
    from admins.models import Content

    faqs = Content.objects.filter(
        status='published',
        content_type='faq',
        visibility__in=['all', 'evaluators']
    ).order_by('created_at')

    jury_profile = None
    try:
        jury_profile = request.user.jury_profile
    except:
        pass

    context = {
        'faqs': faqs,
        'jury_profile': jury_profile,
    }
    return render(request, 'students/evaluator_faq.html', context)


@login_required
@require_POST
def mark_video_watched(request, video_id):
    from students.models import LearningVideo, VideoProgress
    student = request.user.student_profile
    video = get_object_or_404(LearningVideo, id=video_id)
    progress, _ = VideoProgress.objects.get_or_create(student=student, video=video)
    if not progress.watched:
        progress.watched = True
        progress.watched_at = timezone.now()
        progress.save()
    return JsonResponse({'success': True})


@login_required
def video_completion_status(request):
    from students.models import LearningVideo, VideoProgress, TeamMembership
    student = request.user.student_profile
    # Videos are optional — progress is informational only.
    videos = LearningVideo.objects.filter(is_active=True)

    # Current student progress
    watched_ids = set(VideoProgress.objects.filter(student=student, watched=True).values_list('video_id', flat=True))
    my_progress = {'total': videos.count(), 'watched': len(watched_ids), 'complete': len(watched_ids) >= videos.count()}

    # Team members progress
    team_progress = []
    membership = TeamMembership.objects.filter(student=student).first()
    if membership and membership.role == 'leader':
        team_members = membership.team.memberships.filter(status='active').select_related('student__user')
        for m in team_members:
            if m.student:
                m_watched = VideoProgress.objects.filter(student=m.student, watched=True, video__is_active=True).count()
                team_progress.append({
                    'name': m.student.user.get_full_name() or m.student.user.username,
                    'role': m.role,
                    'watched': m_watched,
                    'total': videos.count(),
                    'complete': m_watched >= videos.count()
                })

    return JsonResponse({'my_progress': my_progress, 'team_progress': team_progress})


@login_required
def test_payment(request):
    """Test payment page — Rs 1 Razorpay checkout to verify integration."""
    import razorpay
    from django.conf import settings

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    if request.method == 'POST':
        import json as json_mod
        data = json_mod.loads(request.body)
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_signature = data.get('razorpay_signature')

        try:
            client.utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature,
            })
            return JsonResponse({'success': True, 'message': 'Payment verified successfully!', 'payment_id': razorpay_payment_id})
        except razorpay.errors.SignatureVerificationError:
            return JsonResponse({'success': False, 'message': 'Payment verification failed.'}, status=400)

    order = client.order.create({
        'amount': 100,
        'currency': 'INR',
        'payment_capture': 1,
    })

    context = {
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'order_id': order['id'],
        'amount': 100,
        'currency': 'INR',
        'user': request.user,
    }
    return render(request, 'students/test_payment.html', context)


@login_required
def initiate_payment(request):
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        return redirect('accounts:sign_in')

    if student.is_paid:
        messages.info(request, 'Payment already completed.')
        return redirect('students:dashboard')

    if request.method == 'POST' and request.POST.get('coupon_code'):
        code = request.POST.get('coupon_code', '').strip().upper()
        if code == 'IFT99OFF':
            full_amount = _get_payment_amount(student)
            discounted_amount = round(full_amount * 0.01, 2)
            student.is_paid = True
            student.payment_amount = discounted_amount
            student.payment_transaction_id = f'COUPON-{code}'
            student.paid_at = timezone.now()
            student.save(update_fields=['is_paid', 'payment_amount', 'payment_transaction_id', 'paid_at'])
            messages.success(request, f'Coupon applied! 99% off — ₹{discounted_amount} instead of ₹{full_amount}.')
            return redirect('students:dashboard')
        else:
            messages.error(request, 'Invalid coupon code.')

    import razorpay
    from django.conf import settings
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    amount = _get_payment_amount(student)
    amount_paise = amount * 100

    order = client.order.create({
        'amount': amount_paise,
        'currency': 'INR',
        'payment_capture': 1,
        'receipt': f'ift_{student.id}',
    })

    student.razorpay_order_id = order['id']
    student.payment_amount = amount
    student.save(update_fields=['razorpay_order_id', 'payment_amount'])

    is_tce = student.school and student.school.is_tata_classedge
    context = {
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'order_id': order['id'],
        'amount': amount_paise,
        'amount_display': f'{amount:,}',
        'currency': 'INR',
        'student': student,
        'school_name': student.school.name if student.school else student.school_name or 'N/A',
        'is_tce': is_tce,
    }
    return render(request, 'students/payment.html', context)


@login_required
@require_POST
def verify_payment(request):
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Student not found.'}, status=400)

    if student.is_paid:
        return JsonResponse({'success': True, 'message': 'Already paid.', 'redirect': '/dashboard/'})

    data = json.loads(request.body)
    razorpay_payment_id = data.get('razorpay_payment_id')
    razorpay_order_id = data.get('razorpay_order_id')
    razorpay_signature = data.get('razorpay_signature')

    import razorpay
    from django.conf import settings
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature,
        })
    except razorpay.errors.SignatureVerificationError:
        try:
            from accounts.emails import send_branded_email
            send_branded_email(
                'Payment Failed - India\'s Future Tycoons',
                request.user.email,
                'students/email_payment_failed.html',
                {'user': request.user, 'login_url': f"{getattr(settings, 'SITE_URL', '')}/dashboard/"},
            )
        except Exception:
            pass
        create_notification(request.user, 'system', 'Payment Failed', 'Your payment could not be verified. Any deducted amount will be refunded. Please try again.', 'error', '/dashboard/', 'Retry')
        return JsonResponse({'success': False, 'message': 'Payment verification failed.'}, status=400)

    student.is_paid = True
    student.payment_transaction_id = razorpay_payment_id
    student.razorpay_signature = razorpay_signature
    student.paid_at = timezone.now()
    if not student.payment_amount:
        student.payment_amount = _get_payment_amount(student)
    student.save(update_fields=['is_paid', 'payment_transaction_id', 'razorpay_signature', 'paid_at', 'payment_amount'])

    create_notification(request.user, 'system', 'Payment Successful', f'Your registration fee of Rs {int(student.payment_amount)} has been received.', 'check_circle', '/dashboard/', 'Go to Dashboard')

    try:
        from accounts.emails import send_branded_email
        school_name = student.school.name if student.school else student.school_name or 'N/A'
        send_branded_email(
            'Payment Successful - India\'s Future Tycoons',
            request.user.email,
            'students/email_payment_success.html',
            {
                'user': request.user,
                'payment_amount': int(student.payment_amount),
                'transaction_id': razorpay_payment_id,
                'school_name': school_name,
                'login_url': f"{getattr(settings, 'SITE_URL', '')}/dashboard/",
            },
        )
    except Exception:
        pass

    return JsonResponse({'success': True, 'message': 'Payment verified!', 'redirect': '/dashboard/'})


@csrf_exempt
def razorpay_webhook(request):
    """Server-to-server payment confirmation from Razorpay.

    verify_payment() above only fires if the user's browser stays open and
    the client-side JS 'success' callback completes — with Razorpay's UPI
    intent flow (pay in a UPI app, then return to the browser), it's common
    for the payment to succeed on Razorpay's side while the browser never
    gets the callback (backgrounded, closed, network drop). This webhook is
    the durable fix: Razorpay calls it directly regardless of what the
    browser does, so a captured payment always gets recorded.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import razorpay
    from django.conf import settings

    webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', '')
    signature = request.headers.get('X-Razorpay-Signature', '')
    body = request.body

    if webhook_secret:
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        try:
            client.utility.verify_webhook_signature(body.decode('utf-8'), signature, webhook_secret)
        except razorpay.errors.SignatureVerificationError:
            return JsonResponse({'error': 'Invalid signature'}, status=400)
    else:
        print('[RAZORPAY WEBHOOK] Warning: RAZORPAY_WEBHOOK_SECRET not set, skipping signature verification', flush=True)

    try:
        event = json.loads(body)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    event_type = event.get('event', '')
    if event_type not in ('payment.captured', 'order.paid'):
        return JsonResponse({'success': True, 'ignored': event_type})

    payment_entity = event.get('payload', {}).get('payment', {}).get('entity', {})
    order_id = payment_entity.get('order_id', '')
    payment_id = payment_entity.get('id', '')
    amount_paise = payment_entity.get('amount', 0)

    if not order_id:
        return JsonResponse({'error': 'No order_id in payload'}, status=400)

    try:
        student = Student.objects.get(razorpay_order_id=order_id)
    except Student.DoesNotExist:
        print(f'[RAZORPAY WEBHOOK] No student found for order_id={order_id}', flush=True)
        return JsonResponse({'success': True, 'message': 'No matching student'})

    if student.is_paid:
        return JsonResponse({'success': True, 'message': 'Already recorded'})

    student.is_paid = True
    student.payment_transaction_id = payment_id
    student.payment_amount = amount_paise / 100
    student.paid_at = timezone.now()
    student.save(update_fields=['is_paid', 'payment_transaction_id', 'payment_amount', 'paid_at'])

    create_notification(student.user, 'system', 'Payment Successful', f'Your registration fee of Rs {int(student.payment_amount)} has been received.', 'check_circle', '/dashboard/', 'Go to Dashboard')

    try:
        from accounts.emails import send_branded_email
        school_name = student.school.name if student.school else student.school_name or 'N/A'
        send_branded_email(
            'Payment Successful - India\'s Future Tycoons',
            student.user.email,
            'students/email_payment_success.html',
            {
                'user': student.user,
                'payment_amount': int(student.payment_amount),
                'transaction_id': payment_id,
                'school_name': school_name,
                'login_url': f"{getattr(settings, 'SITE_URL', '')}/dashboard/",
            },
        )
    except Exception:
        pass

    print(f'[RAZORPAY WEBHOOK] Payment recorded for student {student.id} via webhook (order_id={order_id})', flush=True)
    return JsonResponse({'success': True, 'message': 'Payment recorded'})
