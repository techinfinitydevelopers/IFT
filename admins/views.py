from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import csv
import io
import uuid
import threading
import secrets
from django.utils import timezone
from django.contrib.auth.models import User
from students.models import IdeaSubmission, Student, School
from ai_assistant.models import AIEvaluation
from accounts.models import UserProfile, JuryProfile
from accounts.emails import send_onboard_credentials
from admins.models import EvaluatorAssignment

# In-memory progress tracker (works for single-server/SQLite setup)
PROGRESS_TRACKER = {}


def is_staff_or_superuser(user):
    """Check if user is staff or superuser"""
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(is_staff_or_superuser)
def admin_dashboard(request):
    """Admin dashboard showing all submissions"""
    submissions = IdeaSubmission.objects.filter(
        status__in=['submitted', 'evaluated']
    ).select_related('student__user', 'ai_summary')
    
    # Try to prefetch evaluations
    try:
        submissions = submissions.prefetch_related('ai_evaluation')
    except:
        pass
    
    # Filter by category if specified
    category = request.GET.get('category')
    if category:
        submissions = submissions.filter(final_category=category)
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        submissions = submissions.filter(
            Q(title__icontains=search_query) |
            Q(problem_statement__icontains=search_query) |
            Q(student__user__first_name__icontains=search_query) |
            Q(student__user__last_name__icontains=search_query)
        )
    
    # Get category statistics
    category_stats = IdeaSubmission.objects.filter(
        status__in=['submitted', 'evaluated']
    ).values('final_category').annotate(count=Count('id')).order_by('-count')
    
    total_submissions = IdeaSubmission.objects.filter(status__in=['submitted', 'evaluated']).count()
    evaluated_count = AIEvaluation.objects.count()
    
    # Paginate submissions
    paginator = Paginator(submissions, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Flatten submissions for template rendering
    submissions_list = []
    for s in page_obj:
        submissions_list.append({
            'id': s.id,
            'title': (s.title or s.q3_solution_simple or s.q2_exact_problem or s.problem_definition or 'Untitled')[:80] + ('...' if len(s.title or s.q3_solution_simple or s.q2_exact_problem or s.problem_definition or '') > 80 else ''),
            'description': (s.problem_description or s.description or '')[:150] + ('...' if len(s.problem_description or s.description or '') > 150 else ''),
            'student_name': s.student.user.get_full_name() or s.student.user.username,
            'school_name': s.student.school_name or '',
            'status': s.status,
            'status_label': 'Evaluated' if s.status in ['evaluated', 'reviewed'] else ('Under Review' if s.status == 'under_review' else 'Pending'),
        })
    
    # Flatten category stats
    stats_list = []
    for stat in category_stats:
        cat_name = stat['final_category'] or 'Uncategorized'
        stats_list.append({
            'category': cat_name.replace('_', ' ').title(),
            'count': stat['count'],
        })
    
    pending_count = IdeaSubmission.objects.filter(
        status='submitted'
    ).exclude(ai_evaluation__isnull=False).count()

    # New KPI stats
    from accounts.models import UserProfile
    total_students = Student.objects.count()
    total_schools = School.objects.filter(status='active').count()
    total_evaluators = UserProfile.objects.filter(role='jury').count()
    total_participants = total_students + total_evaluators

    context = {
        'submissions': submissions_list,
        'category_stats': stats_list,
        'total_submissions': total_submissions,
        'ai_processed_count': evaluated_count,
        'pending_count': pending_count,
        'total_participants': total_participants,
        'total_students': total_students,
        'total_schools': total_schools,
        'total_evaluators': total_evaluators,
        'selected_category': category or '',
        'search_query': search_query or '',
        'page_obj': page_obj,
    }
    
    return render(request, 'admins/admin_dashboard.html', context)



@login_required
@user_passes_test(is_staff_or_superuser)
def submission_detail(request, submission_id):
    """Detailed view of a submission for admin/jury"""
    submission = get_object_or_404(IdeaSubmission, id=submission_id)
    
    # Get AI summary if available
    ai_summary = None
    try:
        ai_summary = submission.ai_summary
    except:
        pass
    
    # Get AI evaluation if available
    ai_evaluation = None
    try:
        ai_evaluation = submission.ai_evaluation
    except:
        pass
    
    # Get all uploaded files
    uploaded_files = submission.uploaded_files.all()
    files_with_text_count = sum(1 for f in uploaded_files if f.extracted_text)
    
    # Pre-calculate for template — Idea Parameters
    un_score = ai_evaluation.uniqueness_score if ai_evaluation else 0
    un_just = ai_evaluation.uniqueness_justification if ai_evaluation else ""
    ease_score = ai_evaluation.ease_of_implementation_score if ai_evaluation else 0
    ease_just = ai_evaluation.ease_of_implementation_justification if ai_evaluation else ""
    feas_score = ai_evaluation.feasibility_score if ai_evaluation else 0
    feas_just = ai_evaluation.feasibility_justification if ai_evaluation else ""
    impact_score = ai_evaluation.impactful_score if ai_evaluation else 0
    impact_just = ai_evaluation.impactful_justification if ai_evaluation else ""
    sust_score = ai_evaluation.sustainable_score if ai_evaluation else 0
    sust_just = ai_evaluation.sustainable_justification if ai_evaluation else ""

    # Team Parameters
    clarity_score = ai_evaluation.conceptual_clarity_score if ai_evaluation else 0
    clarity_just = ai_evaluation.conceptual_clarity_justification if ai_evaluation else ""
    empathy_score = ai_evaluation.empathy_score if ai_evaluation else 0
    empathy_just = ai_evaluation.empathy_justification if ai_evaluation else ""
    creativity_score = ai_evaluation.creativity_score if ai_evaluation else 0
    creativity_just = ai_evaluation.creativity_justification if ai_evaluation else ""
    comm_score = ai_evaluation.communication_score if ai_evaluation else 0
    comm_just = ai_evaluation.communication_justification if ai_evaluation else ""
    flex_score = ai_evaluation.flexible_thinking_score if ai_evaluation else 0
    flex_just = ai_evaluation.flexible_thinking_justification if ai_evaluation else ""

    # Get evaluator assignments
    evaluator_assignments = EvaluatorAssignment.objects.filter(
        submission=submission
    ).select_related('evaluator').order_by('-evaluated_on')

    context = {
        'submission': submission,
        'ai_summary': ai_summary,
        'ai_evaluation': ai_evaluation,
        'uploaded_files': uploaded_files,
        'files_with_text_count': files_with_text_count,
        'evaluator_assignments': evaluator_assignments,
        # Flattened student info
        'student_name': submission.student.user.get_full_name() or submission.student.user.username,
        'school_name': submission.student.school_name,
        'grade': submission.student.grade,
        'status_label': submission.get_status_display(),
        'category_label': submission.get_final_category_display() or submission.get_ai_suggested_category_display() or "Other",
        'submitted_date': submission.submitted_at.strftime("%B %d, %Y") if submission.submitted_at else "Not submitted",

        # Flattened Questions (v3 with fallback to v2)
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

        # Flattened Idea scores
        'un_score': un_score, 'un_just': un_just,
        'ease_score': ease_score, 'ease_just': ease_just,
        'feas_score': feas_score, 'feas_just': feas_just,
        'impact_score': impact_score, 'impact_just': impact_just,
        'sust_score': sust_score, 'sust_just': sust_just,

        # Flattened Team scores
        'clarity_score': clarity_score, 'clarity_just': clarity_just,
        'empathy_score': empathy_score, 'empathy_just': empathy_just,
        'creativity_score': creativity_score, 'creativity_just': creativity_just,
        'comm_score': comm_score, 'comm_just': comm_just,
        'flex_score': flex_score, 'flex_just': flex_just,

        'final_score': ai_evaluation.final_score if ai_evaluation else 0,
        'rank': ai_evaluation.rank if ai_evaluation else None,
        'is_top_400': ai_evaluation.is_top_400 if ai_evaluation else False,
        'is_coherent': ai_evaluation.is_coherent if ai_evaluation else True,
        'is_disqualified': ai_evaluation.is_disqualified if ai_evaluation else False,
        'coherence_checks': (ai_evaluation.coherence_checks or {}).get('checks', []) if ai_evaluation else [],
        'coherence_failures': ai_evaluation.coherence_failures if ai_evaluation else 0,
        'ai_summary_text': ai_summary.summary if ai_summary else "AI Summary is being processed...",
        # Content mismatch
        'attachment_mismatch': ai_evaluation.attachment_mismatch if ai_evaluation else False,
        'mismatch_severity': ai_evaluation.get_mismatch_severity_display() if ai_evaluation else 'None',
        'mismatch_penalty': ai_evaluation.mismatch_penalty if ai_evaluation else 0,
        'mismatch_reasons': ai_evaluation.mismatch_reasons if ai_evaluation else [],
        # Attachment summaries
        'attachment_summaries': ai_evaluation.attachment_summaries if ai_evaluation else {},
        'attachment_file_analyses': (ai_evaluation.attachment_summaries or {}).get('file_analyses', []) if ai_evaluation else [],
        'attachment_missing_types': (ai_evaluation.attachment_summaries or {}).get('missing_types', []) if ai_evaluation else [],
    }

    return render(request, 'admins/submission_detail_v3.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def submission_detail_v2(request, submission_id):
    """Old submission detail view — renders the v2 template"""
    submission = get_object_or_404(IdeaSubmission, id=submission_id)
    ai_summary = None
    try:
        ai_summary = submission.ai_summary
    except:
        pass
    ai_evaluation = None
    try:
        ai_evaluation = submission.ai_evaluation
    except:
        pass
    uploaded_files = submission.uploaded_files.all()
    files_with_text_count = sum(1 for f in uploaded_files if f.extracted_text)
    un_score = ai_evaluation.uniqueness_score if ai_evaluation else 0
    un_just = ai_evaluation.uniqueness_justification if ai_evaluation else ""
    ease_score = ai_evaluation.ease_of_implementation_score if ai_evaluation else 0
    ease_just = ai_evaluation.ease_of_implementation_justification if ai_evaluation else ""
    feas_score = ai_evaluation.feasibility_score if ai_evaluation else 0
    feas_just = ai_evaluation.feasibility_justification if ai_evaluation else ""
    impact_score = ai_evaluation.impactful_score if ai_evaluation else 0
    impact_just = ai_evaluation.impactful_justification if ai_evaluation else ""
    sust_score = ai_evaluation.sustainable_score if ai_evaluation else 0
    sust_just = ai_evaluation.sustainable_justification if ai_evaluation else ""
    clarity_score = ai_evaluation.conceptual_clarity_score if ai_evaluation else 0
    clarity_just = ai_evaluation.conceptual_clarity_justification if ai_evaluation else ""
    empathy_score = ai_evaluation.empathy_score if ai_evaluation else 0
    empathy_just = ai_evaluation.empathy_justification if ai_evaluation else ""
    creativity_score = ai_evaluation.creativity_score if ai_evaluation else 0
    creativity_just = ai_evaluation.creativity_justification if ai_evaluation else ""
    comm_score = ai_evaluation.communication_score if ai_evaluation else 0
    comm_just = ai_evaluation.communication_justification if ai_evaluation else ""
    flex_score = ai_evaluation.flexible_thinking_score if ai_evaluation else 0
    flex_just = ai_evaluation.flexible_thinking_justification if ai_evaluation else ""
    context = {
        'submission': submission, 'ai_summary': ai_summary, 'ai_evaluation': ai_evaluation,
        'uploaded_files': uploaded_files, 'files_with_text_count': files_with_text_count,
        'student_name': submission.student.user.get_full_name() or submission.student.user.username,
        'school_name': submission.student.school_name, 'grade': submission.student.grade,
        'status_label': submission.get_status_display(),
        'category_label': submission.get_final_category_display() or submission.get_ai_suggested_category_display() or "Other",
        'submitted_date': submission.submitted_at.strftime("%B %d, %Y") if submission.submitted_at else "Not submitted",
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
        'un_score': un_score, 'un_just': un_just,
        'ease_score': ease_score, 'ease_just': ease_just,
        'feas_score': feas_score, 'feas_just': feas_just,
        'impact_score': impact_score, 'impact_just': impact_just,
        'sust_score': sust_score, 'sust_just': sust_just,
        'clarity_score': clarity_score, 'clarity_just': clarity_just,
        'empathy_score': empathy_score, 'empathy_just': empathy_just,
        'creativity_score': creativity_score, 'creativity_just': creativity_just,
        'comm_score': comm_score, 'comm_just': comm_just,
        'flex_score': flex_score, 'flex_just': flex_just,
        'final_score': ai_evaluation.final_score if ai_evaluation else 0,
        'rank': ai_evaluation.rank if ai_evaluation else "TBD",
        'is_coherent': ai_evaluation.is_coherent if ai_evaluation else True,
        'is_disqualified': ai_evaluation.is_disqualified if ai_evaluation else False,
        'coherence_checks': (ai_evaluation.coherence_checks or {}).get('checks', []) if ai_evaluation else [],
        'coherence_failures': ai_evaluation.coherence_failures if ai_evaluation else 0,
        'ai_summary_text': ai_summary.summary if ai_summary else "AI Summary is being processed...",
        'attachment_mismatch': ai_evaluation.attachment_mismatch if ai_evaluation else False,
        'mismatch_severity': ai_evaluation.get_mismatch_severity_display() if ai_evaluation else 'None',
        'mismatch_penalty': ai_evaluation.mismatch_penalty if ai_evaluation else 0,
        'mismatch_reasons': ai_evaluation.mismatch_reasons if ai_evaluation else [],
        'attachment_summaries': ai_evaluation.attachment_summaries if ai_evaluation else {},
        'attachment_file_analyses': (ai_evaluation.attachment_summaries or {}).get('file_analyses', []) if ai_evaluation else [],
        'attachment_missing_types': (ai_evaluation.attachment_summaries or {}).get('missing_types', []) if ai_evaluation else [],
    }
    return render(request, 'admins/submission_detail_v2.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def all_submissions_classic(request):
    """Classic/old submissions listing page — passes real model objects"""
    selected_status = request.GET.get('status', '')
    submissions = IdeaSubmission.objects.all().select_related('student__user')
    if selected_status:
        submissions = submissions.filter(status=selected_status)
    return render(request, 'admins/all_submissions.html', {
        'submissions': submissions,
        'selected_status': selected_status,
    })


@login_required
@user_passes_test(is_staff_or_superuser)
def submission_preview_json(request, submission_id):
    """Return full submission data as JSON for the preview drawer"""
    submission = get_object_or_404(IdeaSubmission, id=submission_id)

    ai_evaluation = None
    try:
        ai_evaluation = submission.ai_evaluation
    except:
        pass

    ai_summary = None
    try:
        ai_summary = submission.ai_summary
    except:
        pass

    uploaded_files = list(submission.uploaded_files.values('file_type', 'original_filename', 'file_size'))

    data = {
        'id': submission.id,
        'title': submission.title or submission.q3_solution_simple or submission.q2_exact_problem or 'Untitled',
        'status': submission.status,
        'status_label': submission.get_status_display(),
        'submitted_at': submission.submitted_at.strftime('%b %d, %Y') if submission.submitted_at else '—',
        'category': submission.get_final_category_display() or submission.get_ai_suggested_category_display() or 'Other',
        'is_top_400': getattr(ai_evaluation, 'is_top_400', False),
        'rank': getattr(ai_evaluation, 'rank', None),
        'is_disqualified': getattr(ai_evaluation, 'is_disqualified', False),
        'coherence_failures': getattr(ai_evaluation, 'coherence_failures', 0),

        # Student
        'student_name': submission.student.user.get_full_name() or submission.student.user.username,
        'student_id': submission.student.student_id,
        'school_name': submission.student.school_name or '—',
        'grade': submission.student.grade or '—',

        # Questions
        'q1': submission.q1_target_group or submission.target_user_group or '',
        'q2': submission.q2_exact_problem or submission.problem_definition or '',
        'q3': submission.q3_solution_simple or submission.solution or '',
        'q4': submission.q4_differentiation or '',
        'q5': submission.q5_build_steps or '',
        'q6': submission.q6_resources or '',
        'q7': submission.q7_positive_change or submission.solution_benefits or '',
        'q8': submission.q8_challenges or '',
        'q9': submission.q9_team_fit or submission.why_best_equipped or '',
        'q10': submission.q10_feedback or '',
        'q11': submission.q11_creative_element or '',
        'q12': submission.q12_pitch or '',

        # AI Scores (0-10 each, total /100)
        'final_score': getattr(ai_evaluation, 'final_score', None),
        'uniqueness_score': getattr(ai_evaluation, 'uniqueness_score', None),
        'ease_score': getattr(ai_evaluation, 'ease_of_implementation_score', None),
        'feasibility_score': getattr(ai_evaluation, 'feasibility_score', None),
        'impact_score': getattr(ai_evaluation, 'impactful_score', None),
        'sustainability_score': getattr(ai_evaluation, 'sustainable_score', None),
        'clarity_score': getattr(ai_evaluation, 'conceptual_clarity_score', None),
        'empathy_score': getattr(ai_evaluation, 'empathy_score', None),
        'creativity_score': getattr(ai_evaluation, 'creativity_score', None),
        'communication_score': getattr(ai_evaluation, 'communication_score', None),
        'flex_thinking_score': getattr(ai_evaluation, 'flexible_thinking_score', None),

        # Justifications
        'uniqueness_just': getattr(ai_evaluation, 'uniqueness_justification', ''),
        'ease_just': getattr(ai_evaluation, 'ease_of_implementation_justification', ''),
        'feasibility_just': getattr(ai_evaluation, 'feasibility_justification', ''),
        'impact_just': getattr(ai_evaluation, 'impactful_justification', ''),
        'sustainability_just': getattr(ai_evaluation, 'sustainable_justification', ''),
        'clarity_just': getattr(ai_evaluation, 'conceptual_clarity_justification', ''),
        'empathy_just': getattr(ai_evaluation, 'empathy_justification', ''),
        'creativity_just': getattr(ai_evaluation, 'creativity_justification', ''),
        'communication_just': getattr(ai_evaluation, 'communication_justification', ''),
        'flex_thinking_just': getattr(ai_evaluation, 'flexible_thinking_justification', ''),

        # AI Summary
        'ai_summary': ai_summary.summary if ai_summary else '',

        # Attachments (with URL)
        'files': [
            {
                'file_type': f.file_type,
                'original_filename': f.original_filename,
                'file_size': f.file_size,
                'url': f.file.url if f.file else '',
            }
            for f in submission.uploaded_files.all()
        ],

        # Team members
        'team_members': [
            {
                'name': m.name,
                'role': m.role,
                'role_label': m.get_role_display(),
                'grade': m.grade,
                'school_name': m.school_name,
            }
            for m in submission.team_members.all()
        ],

        # Jury assignments
        'jury_assignments': [
            {
                'jury_name': j.jury_name,
                'jury_org': j.jury_org,
                'assigned_on': j.assigned_on.strftime('%b %d, %Y') if j.assigned_on else '',
                'evaluated_on': j.evaluated_on.strftime('%b %d, %Y') if j.evaluated_on else '',
                'jury_score': j.jury_score,
                'notes': j.notes,
            }
            for j in submission.jury_assignments.all()
        ],
    }
    return JsonResponse(data)


@login_required
@user_passes_test(is_staff_or_superuser)
def update_submission_status(request, submission_id):
    """AJAX endpoint to update submission status"""
    import json
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    submission = get_object_or_404(IdeaSubmission, id=submission_id)
    try:
        data = json.loads(request.body)
        new_status = data.get('status', '')
        valid = ['submitted', 'under_review', 'reviewed', 'evaluated']
        if new_status not in valid:
            return JsonResponse({'error': 'Invalid status'}, status=400)
        submission.status = new_status
        submission.save(update_fields=['status'])
        return JsonResponse({'ok': True, 'status': new_status})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@user_passes_test(is_staff_or_superuser)
def all_submissions(request):
    """View all submissions regardless of status"""
    from django.db.models import Avg

    submissions = IdeaSubmission.objects.all().select_related(
        'student__user', 'ai_summary', 'ai_evaluation'
    )

    # Filters
    status = request.GET.get('status', '')
    category = request.GET.get('category', '')
    search = request.GET.get('search', '')

    if status:
        submissions = submissions.filter(status=status)
    if category:
        submissions = submissions.filter(final_category=category)
    if search:
        submissions = submissions.filter(
            Q(title__icontains=search) |
            Q(q3_solution_simple__icontains=search) |
            Q(student__user__first_name__icontains=search) |
            Q(student__user__last_name__icontains=search) |
            Q(student__school_name__icontains=search)
        )

    # Stats
    all_qs = IdeaSubmission.objects.all()
    stats = {
        'total':        all_qs.count(),
        'draft':        all_qs.filter(status='draft').count(),
        'submitted':    all_qs.filter(status='submitted').count(),
        'under_review': all_qs.filter(status='under_review').count(),
        'evaluated':    all_qs.filter(status='evaluated').count(),
        'top_400':      AIEvaluation.objects.filter(is_top_400=True).count(),
        'avg_score':    round(AIEvaluation.objects.aggregate(a=Avg('final_score'))['a'] or 0, 1),
    }

    # Paginate
    paginator = Paginator(submissions, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # Flatten for template
    rows = []
    for s in page_obj:
        try:
            ev = s.ai_evaluation
            ai_score = ev.final_score
            is_top_400 = ev.is_top_400
            rank = ev.rank
        except Exception:
            ev = None
            ai_score = None
            is_top_400 = False
            rank = None

        # Get team members from Team model for avatar display
        from students.models import TeamMembership
        member_colors = ['#5E2A97', '#E67E22', '#27AE60', '#E74C3C', '#3498DB', '#F39C12']
        members = []
        team_name = s.student.user.get_full_name() or s.student.user.username  # fallback

        leader_membership = TeamMembership.objects.filter(student=s.student, role='leader').select_related('team').first()
        if leader_membership:
            team_name = leader_membership.team.name
            team_memberships = leader_membership.team.memberships.filter(status='active').select_related('student__user')[:4]
            for i, tm in enumerate(team_memberships):
                if tm.student and tm.student.user:
                    fn = tm.student.user.first_name or ''
                    ln = tm.student.user.last_name or ''
                    initials = (fn[:1] + ln[:1]).upper() or 'S'
                else:
                    initials = 'S'
                members.append({'initials': initials, 'color': member_colors[i % len(member_colors)]})
        else:
            # Solo student - no team, show single avatar
            fn = s.student.user.first_name or ''
            ln = s.student.user.last_name or ''
            initials = (fn[:1] + ln[:1]).upper() or 'S'
            members.append({'initials': initials, 'color': member_colors[0]})

        # Get evaluator score
        eval_assignment = EvaluatorAssignment.objects.filter(submission=s, status='evaluated').first()
        evaluator_score = eval_assignment.score if eval_assignment else None
        is_shortlisted = eval_assignment.is_shortlisted if eval_assignment else False

        rows.append({
            'id': s.id,
            'title': (s.title or s.q3_solution_simple or s.q2_exact_problem or 'Untitled')[:60],
            'category': (s.get_final_category_display() or s.get_ai_suggested_category_display() or 'Other'),
            'student_name': team_name,
            'school_name': s.student.school_display_name or '',
            'status': s.status,
            'status_label': s.get_status_display(),
            'ai_score': ai_score,
            'evaluator_score': evaluator_score,
            'is_shortlisted': is_shortlisted,
            'is_top_400': is_top_400,
            'rank': rank,
            'submitted_at': s.submitted_at.strftime('%b %d, %Y') if s.submitted_at else '—',
            'members': members,
        })

    context = {
        'rows': rows,
        'page_obj': page_obj,
        'stats': stats,
        'selected_status': status,
        'selected_category': category,
        'search_query': search,
    }
    
    return render(request, 'admins/all_submissions_v3.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def regenerate_ai_summary(request, submission_id):
    """Regenerate AI summary for a submission."""
    submission = get_object_or_404(IdeaSubmission, id=submission_id)
    
    if request.method == 'POST':
        use_premium = request.POST.get('premium') == '1'
        
        try:
            from ai_assistant.processors import generate_summary, regenerate_summary_premium
            
            if use_premium:
                ai_summary = regenerate_summary_premium(submission)
                messages.success(request, f'Deep Review completed using premium AI model ({ai_summary.model_used}).')
            else:
                ai_summary = generate_summary(submission)
                messages.success(request, f'AI summary regenerated successfully ({ai_summary.model_used}).')
                
        except Exception as e:
            messages.error(request, f'AI processing failed: {str(e)}')
    
    return redirect('admins:submission_detail', submission_id=submission_id)


@csrf_exempt
@login_required
@user_passes_test(is_staff_or_superuser)
def evaluate_submission(request, submission_id):
    """Evaluate a single submission using AI"""
    submission = get_object_or_404(IdeaSubmission, id=submission_id)
    
    if request.method == 'POST':
        force_reevaluate = request.POST.get('force') == '1'
        
        try:
            from ai_assistant.evaluator import evaluate_idea
            
            evaluation = evaluate_idea(submission, force_reevaluate=force_reevaluate)
            messages.success(
                request, 
                f'Evaluation complete! Score: {evaluation.final_score}/100 (Rank: #{evaluation.rank or "TBD"})'
            )
            
        except Exception as e:
            messages.error(request, f'Evaluation failed: {str(e)}')
    
    return redirect('admins:submission_detail', submission_id=submission_id)


@login_required
@user_passes_test(is_staff_or_superuser)
def batch_evaluate_view(request):
    """Batch evaluate all pending submissions"""
    if request.method == 'POST':
        limit = int(request.POST.get('limit', 20))
        
        try:
            from ai_assistant.evaluator import batch_evaluate, update_rankings
            
            results = batch_evaluate(limit=limit)
            success_count = sum(1 for _, e, err in results if e is not None)
            error_count = sum(1 for _, e, err in results if err is not None)
            
            # Update rankings after batch
            update_rankings()
            
            messages.success(
                request, 
                f'Batch evaluation complete: {success_count} succeeded, {error_count} failed.'
            )
            
        except Exception as e:
            messages.error(request, f'Batch evaluation failed: {str(e)}')
    
    return redirect('admins:rankings')


@login_required
@user_passes_test(is_staff_or_superuser)
def rankings_view(request):
    """View rankings leaderboard with two sections: Top 400 and Normal Rankings"""
    from ai_assistant.evaluator import update_rankings
    
    # Update rankings
    update_rankings()
    
    # Get Top 400 evaluations (higher score = better)
    top_400_evaluations = AIEvaluation.objects.select_related(
        'submission', 'submission__student__user'
    ).filter(is_top_400=True).order_by('rank')

    # Get remaining evaluations (not in top 400)
    normal_evaluations = AIEvaluation.objects.select_related(
        'submission', 'submission__student__user'
    ).filter(is_top_400=False).order_by('-final_score')
    
    from students.models import TeamMembership

    def get_team_name(student):
        membership = TeamMembership.objects.filter(student=student, role='leader').select_related('team').first()
        if membership:
            return membership.team.name
        return student.user.get_full_name() or student.user.username

    top_400_data = []
    for e in top_400_evaluations:
        t = e.submission.title or e.submission.q3_solution_simple or e.submission.q2_exact_problem or 'Untitled'
        eval_assignment = EvaluatorAssignment.objects.filter(submission_id=e.submission.id, status='evaluated').first()
        evaluator_score = eval_assignment.score if eval_assignment else None
        is_shortlisted = eval_assignment.is_shortlisted if eval_assignment else False
        top_400_data.append({
            'rank': e.rank,
            'score': e.final_score,
            'evaluator_score': evaluator_score,
            'is_shortlisted': is_shortlisted,
            'title': (t[:30] + '..') if len(t) > 30 else t,
            'name': get_team_name(e.submission.student),
            'id': e.submission.id
        })

    normal_data = []
    for e in normal_evaluations:
        t = e.submission.title or e.submission.q3_solution_simple or e.submission.q2_exact_problem or 'Untitled'
        eval_assignment = EvaluatorAssignment.objects.filter(submission_id=e.submission.id, status='evaluated').first()
        evaluator_score = eval_assignment.score if eval_assignment else None
        is_shortlisted = eval_assignment.is_shortlisted if eval_assignment else False
        normal_data.append({
            'score': e.final_score,
            'evaluator_score': evaluator_score,
            'is_shortlisted': is_shortlisted,
            'title': (t[:30] + '..') if len(t) > 30 else t,
            'name': get_team_name(e.submission.student),
            'id': e.submission.id
        })
    
    context = {
        'top_400_evaluations': top_400_data,
        'normal_evaluations': normal_data,
        'total_evaluated': AIEvaluation.objects.count(),
        'top_400_count': top_400_evaluations.count(),
        'normal_count': normal_evaluations.count(),
        'pending_count': IdeaSubmission.objects.filter(status='submitted').exclude(ai_evaluation__isnull=False).count(),
    }
    
    return render(request, 'admins/rankings_v3.html', context)




@login_required
@user_passes_test(is_staff_or_superuser)
def export_top_400(request):
    """Export Top 400 submissions to CSV"""
    from ai_assistant.evaluator import get_top_n
    
    evaluations = get_top_n(400)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="top_400_ideas.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Rank', 'Final Score', 'Title', 'Student Name', 'School',
        'Uniqueness', 'Ease of Implementation', 'Feasibility', 'Impact', 'Sustainability',
        'Conceptual Clarity', 'Empathy', 'Creativity', 'Communication', 'Flexible Thinking',
        'Coherence Failures', 'Disqualified', 'Confidence'
    ])

    for e in evaluations:
        writer.writerow([
            e.rank,
            e.final_score,
            e.submission.title,
            e.submission.student.user.get_full_name() or e.submission.student.user.username,
            e.submission.student.school_name,
            e.uniqueness_score,
            e.ease_of_implementation_score,
            e.feasibility_score,
            e.impactful_score,
            e.sustainable_score,
            e.conceptual_clarity_score,
            e.empathy_score,
            e.creativity_score,
            e.communication_score,
            e.flexible_thinking_score,
            e.coherence_failures,
            'Yes' if e.is_disqualified else 'No',
            e.confidence_level,
        ])
    
    return response


@login_required
@user_passes_test(is_staff_or_superuser)
def download_template(request):
    """Download CSV template for bulk idea upload"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="idea_upload_template.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'first_name', 'last_name', 'email', 'school_name', 'grade', 'title',
        'q1_target_group', 'q2_exact_problem', 'q3_solution_simple',
        'q4_differentiation', 'q5_build_steps', 'q6_resources',
        'q7_positive_change', 'q8_challenges', 'q9_team_fit',
        'q10_feedback', 'q11_creative_element', 'q12_pitch'
    ])
    # Example row
    writer.writerow([
        'Rahul', 'Sharma', 'rahul.sharma@example.com', 'Delhi Public School', '10',
        'Smart Water Monitor',
        'Urban households who struggle with high water bills and wastage daily.',
        'Water wastage in urban homes. Taps left running, leaks unnoticed. Matters because water scarcity is increasing.',
        'A smart meter on your tap that shows water usage on your phone, like a speedometer for water.',
        'Unlike monthly meters, this shows real-time usage and sends leak alerts instantly.',
        '1. Build IoT sensor prototype 2. Develop mobile app 3. Test in 10 homes 4. Iterate based on feedback.',
        'Need: Arduino sensors, app developer, Rs 50K. Have: IoT skills, science fair experience, mentor support.',
        'Families save 30% water, reduce bills, detect leaks early. At scale, saves millions of liters citywide.',
        'Hardware durability in wet conditions. Will use waterproof casing and cloud backup for data.',
        'Won science fair for similar project. Team has IoT + app development skills. Live in water-scarce area.',
        'Yes, tested with 3 neighbors. They wanted simpler UI, so we redesigned the dashboard to show just one number.',
        'The leak detection AI learns your household pattern and alerts only for unusual usage, reducing false alarms.',
        'Imagine never worrying about a water leak again. Our smart meter watches your water 24/7 and saves you 30% on bills.'
    ])

    return response


@csrf_exempt
@login_required
@user_passes_test(is_staff_or_superuser)
def bulk_upload_ideas(request):
    """Accept CSV file upload, create users/students/ideas in background thread"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    csv_file = request.FILES.get('csv_file')
    if not csv_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)

    try:
        decoded = csv_file.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        return JsonResponse({'error': 'File must be UTF-8 encoded CSV'}, status=400)

    reader = csv.DictReader(io.StringIO(decoded))
    rows = []
    for i, row in enumerate(reader):
        if i >= 50:
            break
        rows.append(row)

    if not rows:
        return JsonResponse({'error': 'CSV file is empty or has no data rows'}, status=400)

    task_id = str(uuid.uuid4())
    PROGRESS_TRACKER[task_id] = {
        'current': 0,
        'total': len(rows),
        'errors': [],
        'status': 'running',
        'message': 'Starting upload...'
    }

    def process_rows(rows, task_id):
        import django
        django.setup()
        from django.db import connection
        tracker = PROGRESS_TRACKER[task_id]
        for i, row in enumerate(rows):
            try:
                email = (row.get('email') or '').strip()
                first_name = (row.get('first_name') or '').strip()
                last_name = (row.get('last_name') or '').strip()
                school_name = (row.get('school_name') or '').strip()
                grade = (row.get('grade') or '').strip()
                title = (row.get('title') or '').strip()

                if not email:
                    tracker['errors'].append(f'Row {i+1}: Missing email')
                    tracker['current'] = i + 1
                    continue
                if not title:
                    tracker['errors'].append(f'Row {i+1}: Missing title')
                    tracker['current'] = i + 1
                    continue

                # Get or create user
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'username': email.split('@')[0] + '_' + str(uuid.uuid4())[:4],
                        'first_name': first_name,
                        'last_name': last_name,
                    }
                )
                if created:
                    user.set_unusable_password()
                    user.save()

                # Get or create student
                student, _ = Student.objects.get_or_create(
                    user=user,
                    defaults={
                        'school_name': school_name or 'Unknown',
                        'grade': grade or 'N/A',
                        'student_id': f'BULK-{uuid.uuid4().hex[:8].upper()}',
                    }
                )

                IdeaSubmission.objects.create(
                    student=student,
                    title=title,
                    q1_target_group=row.get('q1_target_group', '').strip(),
                    q2_exact_problem=row.get('q2_exact_problem', '').strip(),
                    q3_solution_simple=row.get('q3_solution_simple', '').strip(),
                    q4_differentiation=row.get('q4_differentiation', '').strip(),
                    q5_build_steps=row.get('q5_build_steps', '').strip(),
                    q6_resources=row.get('q6_resources', '').strip(),
                    q7_positive_change=row.get('q7_positive_change', '').strip(),
                    q8_challenges=row.get('q8_challenges', '').strip(),
                    q9_team_fit=row.get('q9_team_fit', '').strip(),
                    q10_feedback=row.get('q10_feedback', '').strip(),
                    q11_creative_element=row.get('q11_creative_element', '').strip(),
                    q12_pitch=row.get('q12_pitch', '').strip(),
                    status='submitted',
                    submitted_at=timezone.now(),
                )

                tracker['current'] = i + 1
                tracker['message'] = f'Processing {i+1}/{len(rows)} ideas...'
            except Exception as e:
                tracker['errors'].append(f'Row {i+1}: {str(e)}')
                tracker['current'] = i + 1

        connection.close()
        tracker['status'] = 'completed'
        tracker['message'] = f'Upload complete. {tracker["current"] - len(tracker["errors"])} ideas created.'

    thread = threading.Thread(target=process_rows, args=(rows, task_id))
    thread.daemon = True
    thread.start()

    return JsonResponse({'task_id': task_id, 'total': len(rows)})


@login_required
@user_passes_test(is_staff_or_superuser)
def get_progress(request, task_id):
    """Return progress for a background task"""
    tracker = PROGRESS_TRACKER.get(task_id)
    if not tracker:
        return JsonResponse({'error': 'Task not found'}, status=404)
    return JsonResponse(tracker)


@csrf_exempt
@login_required
@user_passes_test(is_staff_or_superuser)
def batch_evaluate_async(request):
    """Batch evaluate submissions in background thread with progress tracking"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    limit = int(request.POST.get('limit', 20))

    submissions = list(
        IdeaSubmission.objects.filter(status='submitted')
        .exclude(ai_evaluation__isnull=False)[:limit]
    )

    if not submissions:
        return JsonResponse({'error': 'No pending submissions to evaluate'}, status=400)

    task_id = str(uuid.uuid4())
    PROGRESS_TRACKER[task_id] = {
        'current': 0,
        'total': len(submissions),
        'errors': [],
        'status': 'running',
        'message': 'Starting evaluation...'
    }

    def process_evaluations(submissions, task_id):
        import django
        django.setup()
        from django.db import connection
        from ai_assistant.evaluator import evaluate_idea, update_rankings
        tracker = PROGRESS_TRACKER[task_id]

        for i, submission in enumerate(submissions):
            try:
                evaluate_idea(submission)
                tracker['current'] = i + 1
                tracker['message'] = f'Evaluating {i+1}/{len(submissions)}...'
            except Exception as e:
                tracker['errors'].append(f'{submission.title}: {str(e)}')
                tracker['current'] = i + 1

        try:
            update_rankings()
        except Exception:
            pass

        connection.close()
        success = tracker['current'] - len(tracker['errors'])
        tracker['status'] = 'completed'
        tracker['message'] = f'Done. {success} evaluated, {len(tracker["errors"])} failed.'

    thread = threading.Thread(target=process_evaluations, args=(submissions, task_id))
    thread.daemon = True
    thread.start()

    return JsonResponse({'task_id': task_id, 'total': len(submissions)})


@csrf_exempt
@login_required
@user_passes_test(is_staff_or_superuser)
def evaluate_submission_async(request, submission_id):
    """Evaluate a single submission and return JSON with all scores for animated UI"""
    submission = get_object_or_404(IdeaSubmission, id=submission_id)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    force_reevaluate = request.POST.get('force') == '1'

    try:
        from ai_assistant.evaluator import evaluate_idea, update_rankings

        evaluation = evaluate_idea(submission, force_reevaluate=force_reevaluate)

        # Update rankings after evaluation
        try:
            update_rankings()
            evaluation.refresh_from_db()
        except:
            pass

        # Regenerate AI summary
        try:
            from ai_assistant.processors import generate_summary
            generate_summary(submission)
        except:
            pass

        # Return all scores for animated display
        return JsonResponse({
            'success': True,
            'scores': {
                'uniqueness': {
                    'score': evaluation.uniqueness_score,
                    'justification': evaluation.uniqueness_justification or ''
                },
                'ease_of_implementation': {
                    'score': evaluation.ease_of_implementation_score,
                    'justification': evaluation.ease_of_implementation_justification or ''
                },
                'feasibility': {
                    'score': evaluation.feasibility_score,
                    'justification': evaluation.feasibility_justification or ''
                },
                'impactful': {
                    'score': evaluation.impactful_score,
                    'justification': evaluation.impactful_justification or ''
                },
                'sustainable': {
                    'score': evaluation.sustainable_score,
                    'justification': evaluation.sustainable_justification or ''
                },
                'conceptual_clarity': {
                    'score': evaluation.conceptual_clarity_score,
                    'justification': evaluation.conceptual_clarity_justification or ''
                },
                'empathy': {
                    'score': evaluation.empathy_score,
                    'justification': evaluation.empathy_justification or ''
                },
                'creativity': {
                    'score': evaluation.creativity_score,
                    'justification': evaluation.creativity_justification or ''
                },
                'communication': {
                    'score': evaluation.communication_score,
                    'justification': evaluation.communication_justification or ''
                },
                'flexible_thinking': {
                    'score': evaluation.flexible_thinking_score,
                    'justification': evaluation.flexible_thinking_justification or ''
                },
            },
            'final_score': evaluation.final_score,
            'rank': evaluation.rank,
            'confidence': evaluation.confidence_level or 'medium',
            'coherence': {
                'checks': (evaluation.coherence_checks or {}).get('checks', []),
                'failures': evaluation.coherence_failures,
                'is_disqualified': evaluation.is_disqualified,
            },
            'mismatch': {
                'has_mismatch': evaluation.attachment_mismatch,
                'severity': evaluation.mismatch_severity,
                'penalty': evaluation.mismatch_penalty,
                'reasons': evaluation.mismatch_reasons or [],
            },
            'attachment_summaries': evaluation.attachment_summaries or {},
            'final_score': evaluation.final_score,
            'rank': evaluation.rank,
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ============================================================================
# USER MANAGEMENT VIEWS
# ============================================================================

@login_required
@user_passes_test(is_staff_or_superuser)
def students_list(request):
    """List all students with search and filter."""
    search_query = request.GET.get('q', '').strip()
    selected_school = request.GET.get('school', '')
    selected_grade = request.GET.get('grade', '')

    students = Student.objects.select_related('user').all()

    if search_query:
        students = students.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(student_id__icontains=search_query) |
            Q(school_name__icontains=search_query) |
            Q(phone__icontains=search_query)
        )

    if selected_school:
        students = students.filter(school_name=selected_school)

    if selected_grade:
        students = students.filter(grade=selected_grade)

    # Annotate with submission count and order by latest first
    students = students.annotate(submission_count=Count('submissions')).order_by('-created_at')

    # Pagination
    paginator = Paginator(students, 20)
    page = request.GET.get('page', 1)
    students_page = paginator.get_page(page)

    # Stats
    all_students = Student.objects.all()
    schools = all_students.values_list('school_name', flat=True).distinct().order_by('school_name')
    grades = all_students.values_list('grade', flat=True).distinct().order_by('grade')

    context = {
        'students': students_page,
        'total_students': all_students.count(),
        'active_students': all_students.count(),
        'total_schools': schools.count(),
        'schools': schools,
        'grades': grades,
        'search_query': search_query,
        'selected_school': selected_school,
        'selected_grade': selected_grade,
    }
    return render(request, 'admins/user_management/students_list.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def onboard_student(request):
    """Onboard a new student."""
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        middle_name = request.POST.get('middle_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        gender = request.POST.get('gender', '')
        dob = request.POST.get('date_of_birth', '')
        nationality = request.POST.get('nationality', '')
        school_id = request.POST.get('school_name', '')
        # Resolve school name from ID
        school_obj = None
        try:
            school_obj = School.objects.get(id=school_id)
            school_name = school_obj.name
        except (School.DoesNotExist, ValueError):
            school_name = school_id  # fallback to raw value
        grade = request.POST.get('student_class', '')
        division = request.POST.get('division', '')
        roll_number = request.POST.get('roll_number', '')
        academic_year = request.POST.get('academic_year', '')
        school_branch = request.POST.get('school_branch', '')
        school_board = request.POST.get('school_board', '')
        stream = request.POST.get('stream', '')
        student_email = request.POST.get('student_email', '').strip()
        student_mobile = request.POST.get('student_mobile', '').strip()
        parent_mobile = request.POST.get('parent_mobile', '').strip()
        parent_email = request.POST.get('parent_email', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        pin_code = request.POST.get('pin_code', '').strip()
        gender = request.POST.get('gender', '')
        dob = request.POST.get('date_of_birth', '') or None
        nationality = request.POST.get('nationality', 'Indian')

        if not all([first_name, last_name, school_name, grade, student_email, student_mobile]):
            return JsonResponse({'success': False, 'message': 'Please fill in all required fields including student mobile and email.'}, status=400)

        # Create user
        username = f"{first_name.lower()}.{last_name.lower()}.{roll_number or timezone.now().strftime('%H%M%S')}"
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        user = User.objects.create_user(
            username=username,
            email=student_email,
            first_name=first_name,
            last_name=last_name,
            password=f"ift{roll_number or '2026'}",
        )

        # Create student profile
        student = Student.objects.create(
            user=user,
            student_id=f"IFT-{timezone.now().strftime('%Y')}-{user.id:04d}",
            school=school_obj,
            school_name=school_name,
            school_branch=school_branch,
            middle_name=middle_name,
            gender=gender,
            date_of_birth=dob,
            nationality=nationality,
            grade=grade,
            division=division,
            roll_number=roll_number,
            academic_year=academic_year,
            school_board=school_board,
            stream=stream,
            phone=student_mobile,
            parent_mobile=parent_mobile,
            parent_email=parent_email,
            address=address,
            city=city,
            state=state,
            pin_code=pin_code,
        )

        # Create UserProfile if accounts app exists
        try:
            from accounts.models import UserProfile
            UserProfile.objects.create(user=user, role='student')
        except (ImportError, Exception):
            pass

        return JsonResponse({
            'success': True,
            'message': f'Student {first_name} {last_name} onboarded successfully! Username: {username}',
            'redirect': '/super-admin/user-management/students/'
        })

    schools = School.objects.filter(is_active=True).order_by('name')
    context = {
        'schools': schools,
    }
    return render(request, 'admins/user_management/onboard_student.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def schools_list(request):
    """List all schools with search."""
    search_query = request.GET.get('q', '').strip()

    schools = School.objects.all()

    if search_query:
        schools = schools.filter(
            Q(name__icontains=search_query) |
            Q(city__icontains=search_query) |
            Q(state__icontains=search_query) |
            Q(principal_name__icontains=search_query) |
            Q(board__icontains=search_query)
        )

    # Annotate with student count, latest first
    schools = schools.annotate(students_count=Count('students')).order_by('-created_at')

    # Pagination
    paginator = Paginator(schools, 20)
    page = request.GET.get('page', 1)
    schools_page = paginator.get_page(page)

    context = {
        'schools': schools_page,
        'total_schools': School.objects.count(),
        'active_schools': School.objects.filter(is_active=True).count(),
        'total_students': Student.objects.count(),
        'search_query': search_query,
    }
    return render(request, 'admins/user_management/schools_list.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def onboard_school(request):
    """Onboard a new school."""
    if request.method == 'POST':
        name = request.POST.get('school_name', '').strip()
        branch = request.POST.get('branch', '').strip()
        board = request.POST.get('board', '')
        affiliation_number = request.POST.get('affiliation_number', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        pin_code = request.POST.get('pin_code', '').strip()
        country = request.POST.get('country', 'India').strip()
        principal_name = request.POST.get('principal_name', '').strip()
        principal_email = request.POST.get('principal_email', '').strip()
        contact_email = request.POST.get('school_email', '').strip()
        contact_phone = request.POST.get('school_phone', '').strip()
        website = request.POST.get('website', '').strip()
        established_year = request.POST.get('established_year', '') or None
        total_students = request.POST.get('total_students', '') or None
        school_type = request.POST.get('school_type', '').strip()
        medium = request.POST.get('medium', '').strip()

        if not all([name, board, city, state]):
            return JsonResponse({'success': False, 'message': 'Please fill in all required fields.'}, status=400)

        school = School.objects.create(
            name=name,
            branch=branch,
            board=board,
            affiliation_number=affiliation_number,
            address=address,
            city=city,
            state=state,
            pin_code=pin_code,
            country=country,
            principal_name=principal_name,
            principal_email=principal_email,
            contact_email=contact_email,
            contact_phone=contact_phone,
            website=website,
            established_year=int(established_year) if established_year else None,
            total_students=int(total_students) if total_students else None,
            school_type=school_type,
            medium=medium,
        )

        return JsonResponse({
            'success': True,
            'message': f'School "{name}" onboarded successfully!',
            'redirect': '/super-admin/user-management/schools/'
        })

    return render(request, 'admins/user_management/onboard_school.html')


@login_required
@user_passes_test(is_staff_or_superuser)
def edit_school(request, school_id):
    """Edit an existing school."""
    school = get_object_or_404(School, id=school_id)

    if request.method == 'POST':
        school.name = request.POST.get('school_name', school.name).strip()
        school.branch = request.POST.get('branch', school.branch).strip()
        school.board = request.POST.get('board', school.board)
        school.affiliation_number = request.POST.get('affiliation_number', school.affiliation_number).strip()
        school.address = request.POST.get('address', school.address).strip()
        school.city = request.POST.get('city', school.city).strip()
        school.state = request.POST.get('state', school.state).strip()
        school.pin_code = request.POST.get('pin_code', school.pin_code).strip()
        school.country = request.POST.get('country', school.country).strip()
        school.principal_name = request.POST.get('principal_name', school.principal_name).strip()
        school.principal_email = request.POST.get('principal_email', school.principal_email).strip()
        school.contact_email = request.POST.get('school_email', school.contact_email).strip()
        school.contact_phone = request.POST.get('school_phone', school.contact_phone).strip()
        school.website = request.POST.get('website', school.website).strip()
        established = request.POST.get('established_year', '') or None
        school.established_year = int(established) if established else school.established_year
        total = request.POST.get('total_students', '') or None
        school.total_students = int(total) if total else school.total_students
        school.school_type = request.POST.get('school_type', school.school_type).strip()
        school.medium = request.POST.get('medium', school.medium).strip()
        school.save()

        return JsonResponse({
            'success': True,
            'message': f'School "{school.name}" updated successfully!',
            'redirect': '/super-admin/user-management/schools/'
        })

    context = {'school': school, 'edit_mode': True}
    return render(request, 'admins/user_management/edit_school.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def onboard_evaluator(request):
    """Onboard a new evaluator/jury member."""
    if request.method == 'POST':
        import json as json_mod
        if request.content_type == 'application/json':
            data = json_mod.loads(request.body)
        else:
            data = request.POST

        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        email = data.get('email', '').strip()

        if not all([first_name, last_name, email]):
            return JsonResponse({'success': False, 'message': 'Please fill in all required fields.'}, status=400)

        if User.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'message': 'A user with this email already exists.'}, status=400)

        temp_password = secrets.token_urlsafe(8)

        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=temp_password,
        )
        user.is_staff = True
        user.save(update_fields=['is_staff'])

        UserProfile.objects.create(user=user, role='jury')

        JuryProfile.objects.create(
            user=user,
            # Professional
            designation=data.get('designation', '').strip(),
            organization=data.get('organization', '').strip(),
            industry=data.get('industry', '').strip(),
            experience=data.get('experience', '').strip(),
            qualification=data.get('highest_qualification', '').strip(),
            linkedin_url=data.get('linkedin_url', '').strip(),
            bio=data.get('bio', '').strip(),
            # Expertise
            expertise_area=data.get('primary_expertise', '').strip(),
            secondary_expertise=data.get('secondary_expertise', '').strip(),
            jury_role=data.get('jury_role', '').strip(),
            evaluation_season=data.get('evaluation_season', '').strip(),
            max_ideas_per_week=data.get('max_ideas', '').strip(),
            previous_jury_exp=data.get('previous_jury_exp', '').strip(),
            evaluation_note=data.get('evaluation_note', '').strip(),
            # Contact
            phone=data.get('mobile', '').strip(),
            alternate_phone=data.get('alternate_mobile', '').strip(),
            alternate_email=data.get('alternate_email', '').strip(),
            address=data.get('address', '').strip(),
            pin_code=data.get('pin_code', '').strip(),
            preferred_contact=data.get('preferred_contact', '').strip(),
            # Personal
            gender=data.get('gender', '').strip(),
            date_of_birth=data.get('date_of_birth', '') or None,
            nationality=data.get('nationality', 'Indian').strip(),
            city=data.get('city', '').strip(),
            state=data.get('state', '').strip(),
            # Availability
            available_from=data.get('available_from', '') or None,
            available_to=data.get('available_to', '') or None,
            preferred_time=data.get('preferred_time', '').strip(),
            evaluation_mode=data.get('evaluation_mode', '').strip(),
            willing_to_mentor=data.get('willing_to_mentor', '').strip(),
            willing_to_bootcamp=data.get('willing_to_bootcamp', '').strip(),
            additional_notes=data.get('additional_notes', '').strip(),
        )

        send_onboard_credentials(user, temp_password, 'Evaluator')

        return JsonResponse({
            'success': True,
            'message': f'Evaluator {first_name} {last_name} onboarded successfully! Credentials sent to {email}.',
            'redirect': '/super-admin/user-management/evaluators/'
        })

    return render(request, 'admins/user_management/onboard_evaluator.html')


@login_required
@user_passes_test(is_staff_or_superuser)
def edit_evaluator(request, evaluator_id):
    """Edit an existing evaluator."""
    user = get_object_or_404(User, id=evaluator_id)
    jury = None
    try:
        jury = user.jury_profile
    except JuryProfile.DoesNotExist:
        jury = JuryProfile.objects.create(user=user)

    if request.method == 'POST':
        import json as json_mod
        if request.content_type == 'application/json':
            data = json_mod.loads(request.body)
        else:
            data = request.POST

        user.first_name = data.get('first_name', user.first_name).strip()
        user.last_name = data.get('last_name', user.last_name).strip()
        new_email = data.get('email', user.email).strip()
        if new_email != user.email and User.objects.filter(email=new_email).exclude(id=user.id).exists():
            return JsonResponse({'success': False, 'message': 'A user with this email already exists.'}, status=400)
        user.email = new_email
        user.username = new_email
        user.save()

        # Professional
        jury.designation = data.get('designation', jury.designation).strip()
        jury.organization = data.get('organization', jury.organization).strip()
        jury.industry = data.get('industry', jury.industry).strip()
        jury.experience = data.get('experience', jury.experience).strip()
        jury.qualification = data.get('highest_qualification', jury.qualification).strip()
        jury.linkedin_url = data.get('linkedin_url', jury.linkedin_url).strip()
        jury.bio = data.get('bio', jury.bio).strip()
        # Expertise
        jury.expertise_area = data.get('primary_expertise', jury.expertise_area).strip()
        jury.secondary_expertise = data.get('secondary_expertise', jury.secondary_expertise).strip()
        jury.jury_role = data.get('jury_role', jury.jury_role).strip()
        jury.evaluation_season = data.get('evaluation_season', jury.evaluation_season).strip()
        jury.max_ideas_per_week = data.get('max_ideas', jury.max_ideas_per_week).strip()
        jury.previous_jury_exp = data.get('previous_jury_exp', jury.previous_jury_exp).strip()
        jury.evaluation_note = data.get('evaluation_note', jury.evaluation_note).strip()
        # Contact
        jury.phone = data.get('mobile', jury.phone).strip()
        jury.alternate_phone = data.get('alternate_mobile', jury.alternate_phone).strip()
        jury.alternate_email = data.get('alternate_email', jury.alternate_email).strip()
        jury.address = data.get('address', jury.address).strip()
        jury.pin_code = data.get('pin_code', jury.pin_code).strip()
        jury.preferred_contact = data.get('preferred_contact', jury.preferred_contact).strip()
        # Personal
        jury.gender = data.get('gender', jury.gender).strip()
        dob = data.get('date_of_birth', '')
        if dob:
            jury.date_of_birth = dob
        jury.nationality = data.get('nationality', jury.nationality).strip()
        jury.city = data.get('city', jury.city).strip()
        jury.state = data.get('state', jury.state).strip()
        # Availability
        avail_from = data.get('available_from', '')
        if avail_from:
            jury.available_from = avail_from
        avail_to = data.get('available_to', '')
        if avail_to:
            jury.available_to = avail_to
        jury.preferred_time = data.get('preferred_time', jury.preferred_time).strip()
        jury.evaluation_mode = data.get('evaluation_mode', jury.evaluation_mode).strip()
        jury.willing_to_mentor = data.get('willing_to_mentor', jury.willing_to_mentor).strip()
        jury.willing_to_bootcamp = data.get('willing_to_bootcamp', jury.willing_to_bootcamp).strip()
        jury.additional_notes = data.get('additional_notes', jury.additional_notes).strip()
        jury.save()

        return JsonResponse({
            'success': True,
            'message': f'Evaluator {user.first_name} {user.last_name} updated successfully!',
            'redirect': '/super-admin/user-management/evaluators/'
        })

    evaluator_data = {
        'id': user.id,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'designation': jury.designation, 'organization': jury.organization,
        'industry': jury.industry, 'experience': jury.experience,
        'qualification': jury.qualification, 'linkedin_url': jury.linkedin_url,
        'bio': jury.bio, 'expertise_area': jury.expertise_area,
        'secondary_expertise': jury.secondary_expertise, 'jury_role': jury.jury_role,
        'evaluation_season': jury.evaluation_season, 'max_ideas_per_week': jury.max_ideas_per_week,
        'previous_jury_exp': jury.previous_jury_exp, 'evaluation_note': jury.evaluation_note,
        'phone': jury.phone, 'alternate_phone': jury.alternate_phone,
        'alternate_email': jury.alternate_email, 'address': jury.address,
        'pin_code': jury.pin_code, 'preferred_contact': jury.preferred_contact,
        'gender': jury.gender, 'date_of_birth': str(jury.date_of_birth) if jury.date_of_birth else '',
        'nationality': jury.nationality, 'city': jury.city, 'state': jury.state,
        'available_from': str(jury.available_from) if jury.available_from else '',
        'available_to': str(jury.available_to) if jury.available_to else '',
        'preferred_time': jury.preferred_time, 'evaluation_mode': jury.evaluation_mode,
        'willing_to_mentor': jury.willing_to_mentor, 'willing_to_bootcamp': jury.willing_to_bootcamp,
        'additional_notes': jury.additional_notes,
    }
    context = {'evaluator': evaluator_data, 'edit_mode': True}
    return render(request, 'admins/user_management/edit_evaluator.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def evaluators_list(request):
    """List all evaluators (jury members) with search."""
    search_query = request.GET.get('q', '').strip()

    # Get all users with role='jury'
    profiles = UserProfile.objects.filter(role='jury').select_related('user')

    if search_query:
        profiles = profiles.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(user__jury_profile__organization__icontains=search_query) |
            Q(user__jury_profile__expertise_area__icontains=search_query)
        )

    profiles = profiles.order_by('-created_at')

    # Build evaluator dicts with JuryProfile data
    evaluators_data = []
    for profile in profiles:
        user = profile.user
        jury = None
        try:
            jury = user.jury_profile
        except JuryProfile.DoesNotExist:
            pass

        evaluators_data.append({
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            # Professional
            'designation': jury.designation if jury else '',
            'organization': jury.organization if jury else '',
            'industry': jury.industry if jury else '',
            'experience': jury.experience if jury else '',
            'qualification': jury.qualification if jury else '',
            'linkedin_url': jury.linkedin_url if jury else '',
            'bio': jury.bio if jury else '',
            # Expertise
            'expertise_area': jury.expertise_area if jury else '',
            'secondary_expertise': jury.secondary_expertise if jury else '',
            'jury_role': jury.jury_role if jury else '',
            'evaluation_season': jury.evaluation_season if jury else '',
            'max_ideas_per_week': jury.max_ideas_per_week if jury else '',
            'previous_jury_exp': jury.previous_jury_exp if jury else '',
            'evaluation_note': jury.evaluation_note if jury else '',
            # Contact
            'phone': jury.phone if jury else '',
            'alternate_phone': jury.alternate_phone if jury else '',
            'alternate_email': jury.alternate_email if jury else '',
            'address': jury.address if jury else '',
            'pin_code': jury.pin_code if jury else '',
            'preferred_contact': jury.preferred_contact if jury else '',
            # Personal
            'gender': jury.gender if jury else '',
            'nationality': jury.nationality if jury else '',
            'city': jury.city if jury else '',
            'state': jury.state if jury else '',
            # Availability
            'available_from': str(jury.available_from) if jury and jury.available_from else '',
            'available_to': str(jury.available_to) if jury and jury.available_to else '',
            'preferred_time': jury.preferred_time if jury else '',
            'evaluation_mode': jury.evaluation_mode if jury else '',
            'willing_to_mentor': jury.willing_to_mentor if jury else '',
            'willing_to_bootcamp': jury.willing_to_bootcamp if jury else '',
            'additional_notes': jury.additional_notes if jury else '',
            'is_active': jury.is_active if jury else user.is_active,
            'created_at': profile.created_at,
        })

    # Stats
    total_evaluators = len(evaluators_data)
    active_evaluators = sum(1 for e in evaluators_data if e['is_active'])

    # Pagination
    paginator = Paginator(evaluators_data, 20)
    page = request.GET.get('page', 1)
    evaluators_page = paginator.get_page(page)

    context = {
        'evaluators': evaluators_page,
        'total_evaluators': total_evaluators,
        'active_evaluators': active_evaluators,
        'search_query': search_query,
    }
    return render(request, 'admins/user_management/evaluators_list.html', context)


# ── Evaluator Management ──────────────────────────────────────────────

@login_required
@user_passes_test(is_staff_or_superuser)
def evaluator_management(request):
    """Evaluator management dashboard with workload tracking."""
    from admins.models import EvaluatorAssignment

    # Get all evaluators
    evaluator_profiles = UserProfile.objects.filter(role='jury').select_related('user')

    evaluators = []
    for profile in evaluator_profiles:
        user = profile.user
        jury = None
        try:
            jury = user.jury_profile
        except JuryProfile.DoesNotExist:
            pass

        assignments = EvaluatorAssignment.objects.filter(evaluator=user)
        total_assigned = assignments.count()
        evaluated = assignments.filter(status='evaluated').count()
        pending = assignments.filter(status__in=['assigned', 'in_progress']).count()

        # Calculate capacity (assume max 50 ideas per evaluator)
        max_capacity = 50
        capacity_pct = round((total_assigned / max_capacity) * 100) if max_capacity > 0 else 0

        # Workload category
        if capacity_pct > 95:
            workload = 'overloaded'
        elif capacity_pct > 80:
            workload = 'moderate'
        elif capacity_pct >= 50:
            workload = 'optimal'
        else:
            workload = 'idle'

        full_name = f"{user.first_name} {user.last_name}".strip() or user.email
        initials = (user.first_name[:1] + user.last_name[:1]).upper() if user.first_name else user.email[:2].upper()
        expertise = jury.expertise_area if jury else ''
        org = jury.organization if jury else ''
        active = jury.is_active if jury else True

        evaluators.append({
            'id': user.id,
            'name': full_name,
            'initials': initials,
            'email': user.email,
            'organization': org,
            'expertise_area': expertise,
            'expertise_list': [e.strip() for e in expertise.split(',') if e.strip()] if expertise else [],
            'status': 'Active' if active else 'Inactive',
            'is_active': active,
            'assigned_count': total_assigned,
            'evaluated_count': evaluated,
            'pending_count': pending,
            'capacity_percent': min(capacity_pct, 100),
            'workload_level': workload,
            'avatar_color': '#5E2A97',
        })

    # Stats
    total_evaluators = len(evaluators)
    active_evaluators = sum(1 for e in evaluators if e['is_active'])
    overloaded = sum(1 for e in evaluators if e['workload_level'] == 'overloaded')
    idle = sum(1 for e in evaluators if e['workload_level'] == 'idle')
    total_assigned = EvaluatorAssignment.objects.count()

    # Get top 400 ideas for assignment
    from ai_assistant.models import AIEvaluation
    top_400_ids = AIEvaluation.objects.filter(is_top_400=True).values_list('submission_id', flat=True)
    unassigned_count = IdeaSubmission.objects.filter(id__in=top_400_ids).exclude(
        evaluator_assignments__isnull=False
    ).count()

    shortlisted_count = EvaluatorAssignment.objects.filter(is_shortlisted=True).count()

    context = {
        'evaluators': evaluators,
        'total_evaluators': total_evaluators,
        'active_evaluators': active_evaluators,
        'overloaded': overloaded,
        'idle': idle,
        'total_assigned': total_assigned,
        'unassigned_count': unassigned_count,
        'shortlisted_count': shortlisted_count,
    }
    return render(request, 'admins/evaluator_management.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def assign_ideas(request):
    """Assign ideas to an evaluator. POST with evaluator_id and submission_ids."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json
    from admins.models import EvaluatorAssignment

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        # Form data fallback
        data = request.POST

    evaluator_id = data.get('evaluator_id')
    submission_ids = data.get('submission_ids', [])

    if not evaluator_id or not submission_ids:
        return JsonResponse({'success': False, 'message': 'Evaluator and submissions required.'}, status=400)

    evaluator = User.objects.get(id=evaluator_id)
    created = 0
    skipped = 0
    for sid in submission_ids:
        _, was_created = EvaluatorAssignment.objects.get_or_create(
            evaluator=evaluator,
            submission_id=sid,
            defaults={'status': 'assigned'}
        )
        if was_created:
            created += 1
        else:
            skipped += 1

    return JsonResponse({
        'success': True,
        'message': f'{created} ideas assigned to {evaluator.get_full_name()}. {skipped} already assigned.',
    })


@login_required
@user_passes_test(is_staff_or_superuser)
def bulk_assign_ideas(request):
    """Auto-distribute unassigned top 400 ideas among active evaluators."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    from admins.models import EvaluatorAssignment
    from ai_assistant.models import AIEvaluation

    # Get active evaluators
    active_profiles = UserProfile.objects.filter(role='jury').select_related('user')
    active_evaluators = []
    for p in active_profiles:
        try:
            if p.user.jury_profile.is_active:
                active_evaluators.append(p.user)
        except JuryProfile.DoesNotExist:
            active_evaluators.append(p.user)

    if not active_evaluators:
        return JsonResponse({'success': False, 'message': 'No active evaluators found.'}, status=400)

    # Get unassigned top 400 ideas
    top_400_ids = AIEvaluation.objects.filter(is_top_400=True).values_list('submission_id', flat=True)
    assigned_ids = EvaluatorAssignment.objects.values_list('submission_id', flat=True).distinct()
    unassigned = IdeaSubmission.objects.filter(id__in=top_400_ids).exclude(id__in=assigned_ids)

    # Round-robin distribution
    created = 0
    for i, submission in enumerate(unassigned):
        evaluator = active_evaluators[i % len(active_evaluators)]
        EvaluatorAssignment.objects.create(
            evaluator=evaluator,
            submission=submission,
            status='assigned',
        )
        created += 1

    return JsonResponse({
        'success': True,
        'message': f'{created} ideas distributed among {len(active_evaluators)} evaluators.',
    })


@login_required
@user_passes_test(is_staff_or_superuser)
def get_unassigned_ideas(request):
    """Return unassigned top 400 ideas as JSON for assignment modal."""
    from ai_assistant.models import AIEvaluation
    from admins.models import EvaluatorAssignment

    evaluator_id = request.GET.get('evaluator_id', '')

    top_400 = AIEvaluation.objects.filter(is_top_400=True).select_related('submission', 'submission__student__user')

    # If evaluator specified, exclude their already-assigned ideas
    if evaluator_id:
        assigned_ids = EvaluatorAssignment.objects.filter(evaluator_id=evaluator_id).values_list('submission_id', flat=True)
        top_400 = top_400.exclude(submission_id__in=assigned_ids)

    ideas = []
    for ev in top_400[:50]:  # limit to 50
        s = ev.submission
        ideas.append({
            'id': s.id,
            'title': (s.title or s.q3_solution_simple or 'Untitled')[:60],
            'student': s.student.user.get_full_name(),
            'school': s.student.school_display_name,
            'ai_score': ev.final_score,
            'rank': ev.rank,
        })

    return JsonResponse(ideas, safe=False)


@login_required
@user_passes_test(is_staff_or_superuser)
def evaluator_detail_api(request, evaluator_id):
    """Return evaluator details + assigned ideas as JSON for sidebar."""
    from admins.models import EvaluatorAssignment

    user = User.objects.get(id=evaluator_id)
    jury = None
    try:
        jury = user.jury_profile
    except JuryProfile.DoesNotExist:
        pass

    assignments = EvaluatorAssignment.objects.filter(
        evaluator=user
    ).select_related('submission', 'submission__student__user').order_by('-assigned_on')

    ideas = []
    for a in assignments:
        s = a.submission
        ideas.append({
            'id': s.id,
            'title': (s.title or s.q3_solution_simple or 'Untitled')[:60],
            'student': s.student.user.get_full_name(),
            'status': a.status,
            'score': a.score,
            'is_shortlisted': a.is_shortlisted,
            'parameter_scores': a.parameter_scores or {},
            'notes': a.notes or '',
            'ai_score': getattr(s, 'ai_evaluation', None) and s.ai_evaluation.final_score or None,
            'assigned_on': a.assigned_on.strftime('%b %d, %Y') if a.assigned_on else '',
        })

    data = {
        'name': user.get_full_name() or user.email,
        'email': user.email,
        'expertise': jury.expertise_area if jury else '',
        'organization': jury.organization if jury else '',
        'phone': jury.phone if jury else '',
        'total': assignments.count(),
        'evaluated': assignments.filter(status='evaluated').count(),
        'pending': assignments.exclude(status='evaluated').count(),
        'ideas': ideas,
        # Personal
        'gender': jury.gender if jury else '',
        'nationality': jury.nationality if jury else '',
        'city': jury.city if jury else '',
        'state': jury.state if jury else '',
        # Professional
        'designation': jury.designation if jury else '',
        'industry': jury.industry if jury else '',
        'experience': jury.experience if jury else '',
        'qualification': jury.qualification if jury else '',
        'linkedin_url': jury.linkedin_url if jury else '',
        'bio': jury.bio if jury else '',
        # Expertise
        'secondary_expertise': jury.secondary_expertise if jury else '',
        'jury_role': jury.jury_role if jury else '',
        'evaluation_season': jury.evaluation_season if jury else '',
        'max_ideas_per_week': jury.max_ideas_per_week if jury else '',
        'previous_jury_exp': jury.previous_jury_exp if jury else '',
        # Contact
        'alternate_phone': jury.alternate_phone if jury else '',
        'alternate_email': jury.alternate_email if jury else '',
        'address': jury.address if jury else '',
        'pin_code': jury.pin_code if jury else '',
        'preferred_contact': jury.preferred_contact if jury else '',
        # Availability
        'available_from': str(jury.available_from) if jury and jury.available_from else '',
        'available_to': str(jury.available_to) if jury and jury.available_to else '',
        'preferred_time': jury.preferred_time if jury else '',
        'evaluation_mode': jury.evaluation_mode if jury else '',
        'willing_to_mentor': jury.willing_to_mentor if jury else '',
        'willing_to_bootcamp': jury.willing_to_bootcamp if jury else '',
        'additional_notes': jury.additional_notes if jury else '',
    }

    return JsonResponse(data)


# ──────────────────────────────────────────────
# Content Management Views
# ──────────────────────────────────────────────

@login_required
@user_passes_test(is_staff_or_superuser)
def content_list(request):
    """Content management - list announcements and FAQs."""
    from admins.models import Content

    content_type = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')
    search = request.GET.get('q', '').strip()

    # Auto-publish scheduled content whose time has passed
    Content.objects.filter(
        status='scheduled',
        scheduled_at__lte=timezone.now()
    ).update(status='published')

    items = Content.objects.all()

    if content_type:
        items = items.filter(content_type=content_type)
    if status_filter:
        items = items.filter(status=status_filter)
    if search:
        items = items.filter(Q(title__icontains=search) | Q(body__icontains=search))

    # Stats
    all_content = Content.objects.all()
    stats = {
        'total': all_content.count(),
        'announcements': all_content.filter(content_type='announcement').count(),
        'faqs': all_content.filter(content_type='faq').count(),
        'published': all_content.filter(status='published').count(),
        'draft': all_content.filter(status='draft').count(),
    }

    paginator = Paginator(items, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'items': page_obj,
        'stats': stats,
        'selected_type': content_type,
        'selected_status': status_filter,
        'search_query': search,
    }
    return render(request, 'admins/content/content_list.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def content_create(request):
    """Create new announcement or FAQ."""
    from admins.models import Content

    if request.method == 'POST':
        import json as json_mod
        if request.content_type == 'application/json':
            data = json_mod.loads(request.body)
        else:
            data = request.POST

        content_type = data.get('content_type', '')
        title = data.get('title', '').strip()
        subtitle = data.get('subtitle', '').strip()
        body = data.get('body', '').strip()
        status = data.get('status', 'draft')
        visibility = data.get('visibility', 'all')
        tags = data.get('tags', '').strip()
        scheduled_at = data.get('scheduled_at', '') or None

        if not all([content_type, title]):
            return JsonResponse({'success': False, 'message': 'Title and content type are required.'}, status=400)

        Content.objects.create(
            content_type=content_type,
            title=title,
            subtitle=subtitle,
            body=body,
            status=status,
            visibility=visibility,
            tags=tags,
            author=request.user,
            scheduled_at=scheduled_at,
        )

        return JsonResponse({
            'success': True,
            'message': f'{content_type.title()} created successfully!',
            'redirect': '/super-admin/content/'
        })

    return render(request, 'admins/content/content_create.html')


@login_required
@user_passes_test(is_staff_or_superuser)
def content_edit(request, content_id):
    """Edit existing content."""
    from admins.models import Content

    content = get_object_or_404(Content, id=content_id)

    if request.method == 'POST':
        import json as json_mod
        if request.content_type == 'application/json':
            data = json_mod.loads(request.body)
        else:
            data = request.POST

        title = data.get('title', '').strip()
        subtitle = data.get('subtitle', '').strip()
        body = data.get('body', '').strip()
        status = data.get('status', content.status)
        visibility = data.get('visibility', content.visibility)
        tags = data.get('tags', '').strip()
        scheduled_at = data.get('scheduled_at', '') or None

        if not title:
            return JsonResponse({'success': False, 'message': 'Title is required.'}, status=400)

        content.title = title
        content.subtitle = subtitle
        content.body = body
        content.status = status
        content.visibility = visibility
        content.tags = tags
        content.scheduled_at = scheduled_at
        content.save()

        return JsonResponse({
            'success': True,
            'message': 'Content updated successfully!',
            'redirect': '/super-admin/content/'
        })

    context = {'content': content}
    return render(request, 'admins/content/content_edit.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def content_delete(request, content_id):
    """Delete content."""
    from admins.models import Content

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    content = get_object_or_404(Content, id=content_id)
    content.delete()

    return JsonResponse({'success': True, 'message': 'Content deleted successfully!'})


@login_required
@user_passes_test(is_staff_or_superuser)
def content_toggle_status(request, content_id):
    """Toggle content between published and draft."""
    from admins.models import Content

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    content = get_object_or_404(Content, id=content_id)
    if content.status == 'published':
        content.status = 'draft'
    else:
        content.status = 'published'
    content.save(update_fields=['status'])

    return JsonResponse({'success': True, 'status': content.status, 'message': f'Content {content.status}!'})


# ═══════════════════════════════════════════════════
#  Schedule & Timeline Management
# ═══════════════════════════════════════════════════

@login_required
@user_passes_test(is_staff_or_superuser)
def schedule_view(request):
    from admins.models import Phase
    from django.utils import timezone

    phases = Phase.objects.all()

    # Auto-update statuses based on dates
    today = timezone.now().date()
    for phase in phases:
        if phase.end_date < today and phase.status != 'completed':
            phase.status = 'completed'
            phase.save(update_fields=['status'])
        elif phase.start_date <= today <= phase.end_date and phase.status == 'upcoming':
            phase.status = 'active'
            phase.save(update_fields=['status'])

    phases = Phase.objects.all()  # refresh
    current_phase = phases.filter(status='active').first()

    context = {
        'phases': phases,
        'total_phases': phases.count(),
        'current_phase': current_phase.name if current_phase else 'None',
        'days_remaining': current_phase.days_remaining if current_phase else 0,
    }
    return render(request, 'admins/schedule.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def phase_create(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json as json_mod
    from django.db import models as db_models
    from admins.models import Phase

    if request.content_type == 'application/json':
        data = json_mod.loads(request.body)
    else:
        data = request.POST

    name = data.get('name', '').strip()
    start_date = data.get('start_date', '')
    end_date = data.get('end_date', '')
    description = data.get('description', '').strip()
    status = data.get('status', 'upcoming')

    if not all([name, start_date, end_date]):
        return JsonResponse({'success': False, 'message': 'Name, start date and end date are required.'}, status=400)

    # Auto order
    max_order = Phase.objects.aggregate(db_models.Max('order'))['order__max'] or 0

    Phase.objects.create(
        name=name,
        start_date=start_date,
        end_date=end_date,
        description=description,
        status=status,
        order=max_order + 1,
    )

    return JsonResponse({'success': True, 'message': f'Phase "{name}" created successfully!'})


@login_required
@user_passes_test(is_staff_or_superuser)
def phase_edit(request, phase_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json as json_mod
    from admins.models import Phase

    phase = get_object_or_404(Phase, id=phase_id)

    if request.content_type == 'application/json':
        data = json_mod.loads(request.body)
    else:
        data = request.POST

    phase.name = data.get('name', phase.name).strip()
    phase.start_date = data.get('start_date', phase.start_date)
    phase.end_date = data.get('end_date', phase.end_date)
    phase.description = data.get('description', phase.description).strip()
    phase.status = data.get('status', phase.status)
    phase.save()

    return JsonResponse({'success': True, 'message': f'Phase "{phase.name}" updated successfully!'})


@login_required
@user_passes_test(is_staff_or_superuser)
def phase_delete(request, phase_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    from admins.models import Phase
    phase = get_object_or_404(Phase, id=phase_id)
    phase.delete()

    return JsonResponse({'success': True, 'message': 'Phase deleted successfully!'})


@login_required
@user_passes_test(is_staff_or_superuser)
def reports_view(request):
    """Reports & Analytics dashboard with real DB stats."""
    from django.db.models import Avg, Count, Q, F
    from django.db.models.functions import TruncMonth
    from datetime import timedelta

    now = timezone.now()

    # ── Submission counts ──
    total_submissions = IdeaSubmission.objects.count()
    draft_count = IdeaSubmission.objects.filter(status='draft').count()
    submitted_count = IdeaSubmission.objects.filter(status='submitted').count()
    evaluated_count = IdeaSubmission.objects.filter(status='evaluated').count()
    under_review_count = IdeaSubmission.objects.filter(status='under_review').count()
    reviewed_count = IdeaSubmission.objects.filter(status='reviewed').count()
    pending_count = submitted_count + under_review_count  # not yet evaluated

    # ── Top 400 ──
    top_400_count = AIEvaluation.objects.filter(is_top_400=True).count()

    # ── Schools ──
    total_schools = School.objects.filter(status='active').count()

    # ── Average AI Score ──
    avg_score_data = AIEvaluation.objects.filter(final_score__gt=0).aggregate(avg=Avg('final_score'))
    avg_ai_score = round(avg_score_data['avg'] or 0, 1)

    # ── Completion percentages (for circle charts) ──
    submitted_pct = round((submitted_count + evaluated_count + under_review_count + reviewed_count) / max(total_submissions, 1) * 100)
    evaluated_pct = round((evaluated_count + reviewed_count) / max(total_submissions, 1) * 100)

    # ── School-wise top 10 ──
    top_schools = (
        IdeaSubmission.objects
        .filter(student__school__isnull=False)
        .values('student__school__name')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )
    # Calculate max for progress bar widths
    max_school_count = top_schools[0]['count'] if top_schools else 1

    # ── Category breakdown ──
    category_stats = (
        IdeaSubmission.objects
        .exclude(final_category='')
        .values('final_category')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    # Fallback to ai_suggested_category if final_category is mostly empty
    if not category_stats:
        category_stats = (
            IdeaSubmission.objects
            .exclude(ai_suggested_category='')
            .values('ai_suggested_category')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
    max_category_count = category_stats[0]['count'] if category_stats else 1

    # Category display names mapping
    category_names = dict(IdeaSubmission.CATEGORY_CHOICES)

    # ── Status distribution ──
    status_distribution = (
        IdeaSubmission.objects
        .values('status')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    status_names = dict(IdeaSubmission.STATUS_CHOICES)

    # ── Recent submissions (last 10) ──
    recent_submissions = (
        IdeaSubmission.objects
        .select_related('student__user', 'student__school')
        .order_by('-created_at')[:10]
    )

    # ── Monthly trend (last 6 months) ──
    six_months_ago = now - timedelta(days=180)
    monthly_trend = (
        IdeaSubmission.objects
        .filter(created_at__gte=six_months_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    max_monthly = max((m['count'] for m in monthly_trend), default=1)

    # ── Evaluator stats ──
    from admins.models import EvaluatorAssignment
    shortlisted_count = EvaluatorAssignment.objects.filter(is_shortlisted=True).count()
    total_evaluators = JuryProfile.objects.count()
    active_evaluators = EvaluatorAssignment.objects.values('evaluator').distinct().count()
    total_assignments = EvaluatorAssignment.objects.count()
    completed_assignments = EvaluatorAssignment.objects.filter(status='evaluated').count()

    # ── Daily trend (last 30 days) ──
    from django.db.models.functions import TruncDate
    thirty_days_ago = now - timedelta(days=30)
    daily_trend_qs = (
        IdeaSubmission.objects
        .filter(created_at__gte=thirty_days_ago)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    daily_trend = list(daily_trend_qs)
    daily_max = max((d['count'] for d in daily_trend), default=1)
    daily_average = round(sum(d['count'] for d in daily_trend) / max(len(daily_trend), 1))
    daily_peak = max((d['count'] for d in daily_trend), default=0)
    daily_lowest = min((d['count'] for d in daily_trend), default=0)
    daily_75 = round(daily_max * 0.75)
    daily_50 = round(daily_max * 0.50)
    daily_25 = round(daily_max * 0.25)

    # Build SVG path data for daily trend line chart
    daily_trend_line_path = ''
    daily_trend_area_path = ''
    daily_trend_points = []
    daily_trend_x_labels = []
    if daily_trend:
        n = len(daily_trend)
        safe_daily_max = daily_max or 1
        points = []
        for i, d in enumerate(daily_trend):
            x = round(i * 900 / max(n - 1, 1))
            y = round(240 - (d['count'] / safe_daily_max * 240))
            points.append((x, y))
            # Show every ~5th point for clarity
            if i % max(n // 10, 1) == 0 or i == n - 1:
                daily_trend_points.append({
                    'x': x, 'y': y,
                    'count': d['count'],
                    'label': d['day'].strftime('%b %d'),
                })
        line_parts = ' '.join(f"{'M' if i == 0 else 'L'} {x} {y}" for i, (x, y) in enumerate(points))
        daily_trend_line_path = line_parts
        daily_trend_area_path = line_parts + f' L 900 240 L 0 240 Z'
        # X-axis labels: show ~6 evenly spaced
        step = max(n // 5, 1)
        for i in range(0, n, step):
            daily_trend_x_labels.append(daily_trend[i]['day'].strftime('%b %d'))
        if len(daily_trend_x_labels) < 6 and daily_trend:
            last_label = daily_trend[-1]['day'].strftime('%b %d')
            if daily_trend_x_labels[-1] != last_label:
                daily_trend_x_labels.append(last_label)

    # ── Evaluator distribution (jury scoring patterns) ──
    evaluator_high_scorer = 0
    evaluator_moderate = 0
    evaluator_conservative = 0
    try:
        jury_avg_scores = (
            EvaluatorAssignment.objects
            .filter(status='evaluated', score__isnull=False)
            .values('evaluator')
            .annotate(avg_score=Avg('score'))
        )
        for j in jury_avg_scores:
            avg = j['avg_score'] or 0
            if avg >= 75:
                evaluator_high_scorer += 1
            elif avg >= 50:
                evaluator_moderate += 1
            else:
                evaluator_conservative += 1
    except Exception:
        pass

    # Avoid division by zero in template widthratio tags
    safe_total = total_submissions or 1

    context = {
        'total_submissions': safe_total,
        'draft_count': draft_count,
        'submitted_count': submitted_count,
        'evaluated_count': evaluated_count,
        'under_review_count': under_review_count,
        'reviewed_count': reviewed_count,
        'pending_count': pending_count,
        'top_400_count': top_400_count,
        'total_schools': total_schools,
        'avg_ai_score': avg_ai_score,
        'submitted_pct': submitted_pct,
        'evaluated_pct': evaluated_pct,
        'top_schools': top_schools,
        'max_school_count': max_school_count,
        'category_stats': category_stats,
        'max_category_count': max_category_count,
        'category_names': category_names,
        'status_distribution': status_distribution,
        'status_names': status_names,
        'recent_submissions': recent_submissions,
        'monthly_trend': monthly_trend,
        'max_monthly': max_monthly,
        'total_evaluators': total_evaluators,
        'active_evaluators': active_evaluators,
        'total_assignments': total_assignments,
        'completed_assignments': completed_assignments,
        'shortlisted_count': shortlisted_count,
        # Daily trend
        'daily_trend': daily_trend,
        'daily_max': daily_max,
        'daily_average': daily_average,
        'daily_peak': daily_peak,
        'daily_lowest': daily_lowest,
        'daily_75': daily_75,
        'daily_50': daily_50,
        'daily_25': daily_25,
        'daily_trend_line_path': daily_trend_line_path,
        'daily_trend_area_path': daily_trend_area_path,
        'daily_trend_points': daily_trend_points,
        'daily_trend_x_labels': daily_trend_x_labels,
        # Evaluator distribution
        'evaluator_high_scorer': evaluator_high_scorer,
        'evaluator_moderate': evaluator_moderate,
        'evaluator_conservative': evaluator_conservative,
    }

    # ── Filter data (Board, Grade, City, Domain) ──

    # Board-wise
    board_counts = dict(
        Student.objects.filter(school__isnull=False)
        .values_list('school__board')
        .annotate(c=Count('id'))
        .values_list('school__board', 'c')
    )
    context['board_cbse'] = board_counts.get('CBSE', 0)
    context['board_icse'] = board_counts.get('ICSE', 0)
    context['board_state'] = board_counts.get('SSC', 0)
    context['board_ib'] = board_counts.get('IB', 0) + board_counts.get('IGCSE', 0)

    # Grade-wise
    all_students = Student.objects.all()
    context['grade_9_10'] = all_students.filter(grade__in=['9', '10', 'Class 9', 'Class 10']).count()
    context['grade_11_12'] = all_students.filter(grade__in=['11', '12', 'Class 11', 'Class 12']).count()
    context['grade_6_8'] = all_students.filter(grade__in=['6', '7', '8', 'Class 6', 'Class 7', 'Class 8']).count()
    context['grade_others'] = all_students.exclude(
        grade__in=['6', '7', '8', '9', '10', '11', '12', 'Class 6', 'Class 7', 'Class 8', 'Class 9', 'Class 10', 'Class 11', 'Class 12']
    ).count()

    # City-wise (from School)
    city_counts = list(
        School.objects.filter(status='active', city__gt='')
        .values('city')
        .annotate(c=Count('students'))
        .order_by('-c')[:10]
    )
    context['city_delhi'] = sum(c['c'] for c in city_counts if 'delhi' in (c['city'] or '').lower() or 'noida' in (c['city'] or '').lower() or 'gurugram' in (c['city'] or '').lower() or 'ghaziabad' in (c['city'] or '').lower())
    context['city_mumbai'] = sum(c['c'] for c in city_counts if 'mumbai' in (c['city'] or '').lower())
    context['city_bangalore'] = sum(c['c'] for c in city_counts if 'bangalore' in (c['city'] or '').lower() or 'bengaluru' in (c['city'] or '').lower())
    context['city_others'] = all_students.count() - context['city_delhi'] - context['city_mumbai'] - context['city_bangalore']

    # Top 10 cities
    for i, c in enumerate(city_counts[:4]):
        context[f'top_city_{i+1}'] = f"{c['city']} ({c['c']})"

    # Domain-wise (from submission categories)
    domain_map = {'education': 0, 'agriculture': 0, 'healthcare': 0, 'technology': 0}
    for s in IdeaSubmission.objects.values_list('final_category', flat=True):
        cat = (s or '').lower()
        if 'edu' in cat or 'learn' in cat:
            domain_map['education'] += 1
        elif 'agri' in cat:
            domain_map['agriculture'] += 1
        elif 'health' in cat or 'medical' in cat:
            domain_map['healthcare'] += 1
        else:
            domain_map['technology'] += 1
    context['domain_education'] = domain_map['education']
    context['domain_agriculture'] = domain_map['agriculture']
    context['domain_healthcare'] = domain_map['healthcare']
    context['domain_technology'] = domain_map['technology']

    # Student count
    context['student_count'] = all_students.count()
    context['evaluator_count'] = total_evaluators

    return render(request, 'admins/reports.html', context)
