from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Student, IdeaSubmission, UploadedFile
from .forms import StudentRegistrationForm, IdeaSubmissionForm
from ai_assistant.processors import generate_summary
import os


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
    """Student dashboard showing their submissions"""
    try:
        student = request.user.student_profile
        submissions = student.submissions.all()
    except Student.DoesNotExist:
        # Create student profile if it doesn't exist
        student = Student.objects.create(
            user=request.user,
            student_id=f"IFT{request.user.id:05d}",
            school_name="Not specified",
            grade="Not specified"
        )
        submissions = []
    
    # Calculate counts for stats
    submitted_count = sum(1 for s in submissions if s.status == 'submitted')
    reviewed_count = sum(1 for s in submissions if s.status == 'reviewed')
    
    return render(request, 'students/dashboard.html', {
        'student': student,
        'submissions': submissions,
        'submitted_count': submitted_count,
        'reviewed_count': reviewed_count,
    })


import threading

@login_required
def submit_idea(request):
    """Idea submission form"""
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, 'Please complete your profile first.')
        return redirect('students:dashboard')
    
    if request.method == 'POST':
        form = IdeaSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            # Create submission
            submission = form.save(commit=False)
            submission.student = student
            submission.status = 'submitted'
            submission.submitted_at = timezone.now()

            # Auto-generate title from solution (Q3) or problem (Q2) immediately
            title_source = (submission.q3_solution_simple or submission.q2_exact_problem or '').strip()
            if title_source:
                title = title_source[:80]
                if len(title_source) > 80:
                    last_space = title.rfind(' ')
                    if last_space > 40:
                        title = title[:last_space]
                submission.title = title

            submission.save()
            
            # Handle file uploads
            files_data = [
                ('document_file', 'document'),
                ('image_file', 'image'),
                ('video_file', 'video'),
            ]
            
            for field_name, file_type in files_data:
                uploaded_file = request.FILES.get(field_name)
                if uploaded_file:
                    UploadedFile.objects.create(
                        submission=submission,
                        file_type=file_type,
                        file=uploaded_file,
                        original_filename=uploaded_file.name,
                        file_size=uploaded_file.size
                    )
            
            # Trigger AI processing in background to avoid timeout
            def run_ai(sub_id):
                try:
                    from .models import IdeaSubmission
                    sub = IdeaSubmission.objects.get(id=sub_id)
                    generate_summary(sub)
                    sub.ai_processed = True
                    sub.ai_processing_error = ''
                    sub.save(update_fields=['ai_processed', 'ai_processing_error'])
                except Exception as e:
                    try:
                        from .models import IdeaSubmission
                        sub = IdeaSubmission.objects.get(id=sub_id)
                        sub.ai_processing_error = str(e)[:500]
                        sub.save(update_fields=['ai_processing_error'])
                    except Exception:
                        pass

            threading.Thread(target=run_ai, args=(submission.id,), daemon=True).start()
            
            messages.success(request, 'Your idea has been submitted successfully! AI analysis is running in the background.')
            return redirect('students:submission_confirmation', submission_id=submission.id)
    else:
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
    """View details of a specific submission"""
    submission = get_object_or_404(IdeaSubmission, id=submission_id, student__user=request.user)
    
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
    
    return render(request, 'students/submission_detail_v2.html', context)
