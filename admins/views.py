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
from django.utils import timezone
from django.contrib.auth.models import User
from students.models import IdeaSubmission, Student
from ai_assistant.models import AIEvaluation

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
    
    context = {
        'submissions': submissions_list,
        'category_stats': stats_list,
        'total_submissions': total_submissions,
        'ai_processed_count': evaluated_count,
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

    context = {
        'submission': submission,
        'ai_summary': ai_summary,
        'ai_evaluation': ai_evaluation,
        'uploaded_files': uploaded_files,
        'files_with_text_count': files_with_text_count,
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
        'rank': ai_evaluation.rank if ai_evaluation else "TBD",
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

    return render(request, 'admins/submission_detail_v2.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def all_submissions(request):
    """View all submissions regardless of status"""
    submissions = IdeaSubmission.objects.all().select_related('student__user', 'ai_summary')
    
    # Status filter
    status = request.GET.get('status')
    if status:
        submissions = submissions.filter(status=status)
    
    context = {
        'submissions': submissions,
        'selected_status': status,
    }
    
    return render(request, 'admins/all_submissions.html', context)


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
    
    top_400_data = []
    for e in top_400_evaluations:
        t = e.submission.title or e.submission.q3_solution_simple or e.submission.q2_exact_problem or 'Untitled'
        top_400_data.append({
            'rank': e.rank,
            'score': e.final_score,
            'title': (t[:30] + '..') if len(t) > 30 else t,
            'name': e.submission.student.user.get_full_name() or e.submission.student.user.username,
            'id': e.submission.id
        })

    normal_data = []
    for e in normal_evaluations:
        t = e.submission.title or e.submission.q3_solution_simple or e.submission.q2_exact_problem or 'Untitled'
        normal_data.append({
            'score': e.final_score,
            'title': (t[:30] + '..') if len(t) > 30 else t,
            'name': e.submission.student.user.get_full_name() or e.submission.student.user.username,
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
    
    return render(request, 'admins/rankings_v2.html', context)




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
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
