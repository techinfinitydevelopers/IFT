from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Student, IdeaSubmission, UploadedFile, School
from .forms import StudentRegistrationForm, IdeaSubmissionForm
from ai_assistant.processors import generate_summary
import os


def create_notification(user, notification_type, title, message='', icon='notifications', action_url='', action_label=''):
    """Helper to create a notification."""
    from students.models import Notification
    Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        icon=icon,
        action_url=action_url,
        action_label=action_label,
    )


def home(request):
    """Home page"""
    return render(request, 'students/home.html')


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
        'team_role': team_role,
        'announcements': announcements,
        'recent_activity': recent_activity,
        'learning_videos': video_list,
        'videos_total': len(video_list),
        'videos_watched': len([v for v in video_list if v['watched']]),
    }
    return render(request, 'students/dashboard_v2.html', context)


import threading

@login_required
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
        # Member — cannot submit, show appropriate page
        team = membership.team
        leader_membership = team.memberships.filter(role='leader').select_related('student').first()
        leader_submission = None
        if leader_membership and leader_membership.student:
            leader_submission = IdeaSubmission.objects.filter(student=leader_membership.student).first()

        return render(request, 'students/member_idea_view.html', {
            'student': student,
            'team': team,
            'leader_submission': leader_submission,
            'membership': membership,
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

        # Check mandatory videos completion for team
        from students.models import LearningVideo, VideoProgress, TeamMembership
        mandatory_videos = LearningVideo.objects.filter(is_active=True, is_mandatory=True)
        if mandatory_videos.exists():
            # Check current student
            watched = VideoProgress.objects.filter(student=student, watched=True, video__in=mandatory_videos).count()
            if watched < mandatory_videos.count():
                messages.error(request, 'Please complete all mandatory learning videos before submitting.')
                return redirect('students:submit_idea')

            # Check team members
            membership = TeamMembership.objects.filter(student=student).first()
            if membership and membership.role == 'leader':
                for m in membership.team.memberships.filter(status='active').exclude(student=student):
                    if m.student:
                        m_watched = VideoProgress.objects.filter(student=m.student, watched=True, video__in=mandatory_videos).count()
                        if m_watched < mandatory_videos.count():
                            messages.error(request, f'Team member {m.student.user.get_full_name()} has not completed all mandatory videos.')
                            return redirect('students:submit_idea')

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

    return render(request, 'students/submit_idea_v2.html', {
        'form': form,
        'is_edit': existing is not None,
        'saved_title': existing.title if existing else '',
        'saved_track': existing.competition_track if existing else '',
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

    if not is_owner and not is_team_member:
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
        messages.error(request, 'No school profile found for this account.')
        return redirect('accounts:sign_in')

    if request.method == 'POST':
        # Section A - School Information
        school.branch = request.POST.get('branch', school.branch)
        school.board = request.POST.get('board', school.board)
        school.affiliation_number = request.POST.get('affiliation_number', school.affiliation_number)
        school.school_type = request.POST.get('school_type', school.school_type)
        school.medium = request.POST.get('medium', school.medium)
        established_year = request.POST.get('established_year', '')
        school.established_year = int(established_year) if established_year else None
        total_students = request.POST.get('total_students', '')
        school.total_students = int(total_students) if total_students else None

        # Section B - Location
        school.address = request.POST.get('address', school.address)
        school.pin_code = request.POST.get('pin_code', school.pin_code)
        school.country = request.POST.get('country', school.country) or 'India'

        # Section C - Contact & Principal
        school.principal_name = request.POST.get('principal_name', school.principal_name)
        school.principal_email = request.POST.get('principal_email', school.principal_email)
        school.website = request.POST.get('website', school.website)

        # Check required fields to activate
        required_filled = all([
            school.board,
            school.address,
            school.pin_code,
            school.principal_name,
            school.principal_email,
        ])

        if required_filled:
            school.status = 'active'
            school.is_active = True
        school.save()

        msg = 'School profile completed successfully!' if required_filled else 'Profile saved. Fill all required fields to activate.'
        return JsonResponse({
            'success': True,
            'message': msg,
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

    context = {
        'school': school,
        'is_pending': False,
        'student_count': student_count,
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
    }
    return render(request, 'students/school_dashboard.html', context)


@login_required
def student_profile(request):
    """Student profile page with edit capability."""
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        return redirect('accounts:sign_in')

    submissions_count = IdeaSubmission.objects.filter(student=student).count()
    team_count = 0
    latest = IdeaSubmission.objects.filter(student=student).first()
    if latest:
        team_count = latest.team_members.count()

    if request.method == 'POST':
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
        return JsonResponse({'success': False, 'message': 'Team is full (max 3 members).'}, status=400)

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
        return JsonResponse({'success': False, 'message': 'Team is full (max 3 members).'}, status=400)

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

    # Send publish confirmation email
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        send_mail(
            subject='Your Idea Has Been Published - IFT Season 6',
            message=f'Dear {request.user.first_name},\n\nYour idea was published successfully on IFT and is now under review. Announcing shortlisted ideas soon!\n\nTeam IFT\nhttps://indiafuturetycoons.com/',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
            fail_silently=True,
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

    return JsonResponse({'success': True, 'message': 'Your idea has been published and submitted for review!'})


@login_required
def idea_corner(request):
    """Public idea gallery — browse all published ideas."""
    ideas = IdeaSubmission.objects.filter(
        status__in=['submitted', 'evaluated', 'reviewed']
    ).select_related('student__user', 'student__school').order_by('-submitted_at')

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
        })

    context = {
        'ideas': idea_list,
        'total_ideas': total_ideas,
        'total_schools': total_schools,
        'student': request.user.student_profile if hasattr(request.user, 'student_profile') else None,
    }
    return render(request, 'students/idea_corner.html', context)


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

    # Also fetch published announcements
    from admins.models import Content
    announcements = Content.objects.filter(
        status='published',
        content_type='announcement',
        visibility__in=['all', 'students']
    ).order_by('-created_at')[:10]

    context = {
        'student': student,
        'notifications': notifications[:50],
        'announcements': announcements,
        'total': notifications.count(),
        'unread': notifications.filter(is_read=False).count(),
        'team_count': notifications.filter(notification_type='team').count(),
        'submission_count': notifications.filter(notification_type='submission').count(),
        'announcement_count': notifications.filter(notification_type='announcement').count() + announcements.count(),
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
    """Mark all notifications as read."""
    from students.models import Notification
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'POST required'}, status=405)


@login_required
def school_teams(request):
    """School admin — view teams from this school."""
    from students.models import School, Student, Team, TeamMembership, IdeaSubmission
    from ai_assistant.models import AIEvaluation

    try:
        school = request.user.school_profile
    except School.DoesNotExist:
        return redirect('accounts:sign_in')

    if school.status != 'active':
        return redirect('students:school_dashboard')

    search = request.GET.get('q', '').strip()

    # Get teams where leader is from this school
    leader_memberships = TeamMembership.objects.filter(
        student__school=school, role='leader'
    ).select_related('team', 'student__user')

    team_list = []
    for lm in leader_memberships:
        team = lm.team
        if search and search.lower() not in team.name.lower():
            continue

        members = team.memberships.filter(status='active').select_related('student__user')
        member_count = members.count()

        # Get team's idea submission
        idea = IdeaSubmission.objects.filter(student=lm.student).exclude(status='draft').first()
        idea_title = ''
        idea_status = 'no-idea'
        ai_score = None
        if idea:
            idea_title = (idea.title or idea.q3_solution_simple or '')[:50]
            idea_status = idea.status
            try:
                ai_score = idea.ai_evaluation.final_score
            except:
                pass

        team_list.append({
            'id': team.id,
            'name': team.name,
            'code': team.team_code,
            'track': team.get_track_display() if team.track else '',
            'leader_name': lm.student.user.get_full_name(),
            'member_count': member_count,
            'max_members': 3,
            'members': [{'name': m.student.user.get_full_name(), 'initial': m.student.user.first_name[:1].upper() if m.student and m.student.user.first_name else 'S', 'role': m.role} for m in members if m.student],
            'idea_title': idea_title,
            'idea_status': idea_status,
            'ai_score': ai_score,
            'created_at': team.created_at,
        })

    # Stats
    total_teams = len(team_list)
    full_teams = sum(1 for t in team_list if t['member_count'] >= 3)
    with_ideas = sum(1 for t in team_list if t['idea_status'] != 'no-idea')
    avg_size = round(sum(t['member_count'] for t in team_list) / max(total_teams, 1), 1)

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(team_list, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'school': school,
        'teams': page_obj,
        'total_teams': total_teams,
        'full_teams': full_teams,
        'with_ideas': with_ideas,
        'avg_size': avg_size,
        'search_query': search,
    }
    return render(request, 'students/school_teams.html', context)


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
        })

    # Stats
    all_students = Student.objects.filter(school=school)
    total = all_students.count()
    in_teams = sum(1 for sl in student_list if sl['status'] in ['in-team', 'submitted'])
    no_teams = total - in_teams
    submitted = sum(1 for sl in student_list if sl['status'] == 'submitted')

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
    }
    return render(request, 'students/school_students.html', context)


@login_required
def school_submissions(request):
    """School admin — view idea submissions from this school."""
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
    """Student Learning Resources page — 8 module videos."""
    try:
        student = request.user.student_profile
    except:
        student = None
    return render(request, 'students/learning_resources.html', {'student': student})


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
    videos = LearningVideo.objects.filter(is_active=True, is_mandatory=True)

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
                m_watched = VideoProgress.objects.filter(student=m.student, watched=True, video__is_mandatory=True).count()
                team_progress.append({
                    'name': m.student.user.get_full_name() or m.student.user.username,
                    'role': m.role,
                    'watched': m_watched,
                    'total': videos.count(),
                    'complete': m_watched >= videos.count()
                })

    return JsonResponse({'my_progress': my_progress, 'team_progress': team_progress})
