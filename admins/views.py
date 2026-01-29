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
            'title': (s.problem_definition or s.title or 'Untitled')[:80] + ('...' if len(s.problem_definition or s.title or '') > 80 else ''),
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
    
    # Pre-calculate for template
    un_score = ai_evaluation.uniqueness_score if ai_evaluation else 0
    un_just = ai_evaluation.uniqueness_justification if ai_evaluation else ""
    ease_score = ai_evaluation.ease_of_implementation_score if ai_evaluation else 0
    ease_just = ai_evaluation.ease_of_implementation_justification if ai_evaluation else ""
    scale_score = ai_evaluation.scalable_score if ai_evaluation else 0
    scale_just = ai_evaluation.scalable_justification if ai_evaluation else ""
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
        
        # Flattened Questions
        'q1_problem': submission.problem_definition or submission.problem_statement or "Not provided",
        'q2_description': submission.problem_description or submission.description or "Not provided",
        'q3_target': submission.target_user_group or submission.target_audience or "Not provided",
        'q4_urgency': submission.problem_urgency or "Not provided",
        'q5_solution': submission.solution or submission.proposed_solution or "Not provided",
        'q6_benefits': submission.solution_benefits or submission.impact_assessment or "Not provided",
        'q7_why': submission.why_best_equipped or "Not provided",
        'q8_stage': submission.get_idea_stage_display(),
        
        # Flattened Idea scores
        'un_score': un_score, 'un_just': un_just,
        'ease_score': ease_score, 'ease_just': ease_just,
        'scale_score': scale_score, 'scale_just': scale_just,
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
        'ai_summary_text': ai_summary.summary if ai_summary else "AI Summary is being processed...",
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
                f'Evaluation complete! Score: {evaluation.final_score}/50 (Rank: #{evaluation.rank or "TBD"})'
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
        top_400_data.append({
            'rank': e.rank,
            'score': e.final_score,
            'title': (e.submission.title[:30] + '..') if len(e.submission.title) > 30 else e.submission.title,
            'name': e.submission.student.user.get_full_name() or e.submission.student.user.username,
            'id': e.submission.id
        })

    normal_data = []
    for e in normal_evaluations:
        normal_data.append({
            'score': e.final_score,
            'title': (e.submission.title[:30] + '..') if len(e.submission.title) > 30 else e.submission.title,
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
        'Uniqueness', 'Ease of Implementation', 'Scalable', 'Impactful', 'Sustainable',
        'Conceptual Clarity', 'Empathy', 'Creativity', 'Communication', 'Flexible Thinking',
        'Idea Stage', 'Confidence'
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
            e.scalable_score,
            e.impactful_score,
            e.sustainable_score,
            e.conceptual_clarity_score,
            e.empathy_score,
            e.creativity_score,
            e.communication_score,
            e.flexible_thinking_score,
            e.submission.get_idea_stage_display(),
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
        'problem_definition', 'problem_description', 'target_user_group',
        'problem_urgency', 'solution', 'solution_benefits',
        'why_best_equipped', 'idea_stage'
    ])
    # Example row
    writer.writerow([
        'Rahul', 'Sharma', 'rahul.sharma@example.com', 'Delhi Public School', '10',
        'Smart Water Monitor', 'Water wastage in urban households',
        'Many households waste water due to lack of real-time monitoring of usage.',
        'Urban households and apartment complexes',
        'Water scarcity is increasing and current meters only show monthly usage.',
        'An IoT-based smart water meter that tracks real-time usage via a mobile app.',
        'Users save 30% water and get alerts for leaks, reducing bills and waste.',
        'I have experience building IoT prototypes and won a science fair for a similar project.',
        'concept_prototype'
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
        valid_stages = ['idea', 'concept_prototype', 'working_prototype', 'running_business']

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

                idea_stage = (row.get('idea_stage') or 'idea').strip()
                if idea_stage not in valid_stages:
                    idea_stage = 'idea'

                IdeaSubmission.objects.create(
                    student=student,
                    title=title,
                    problem_definition=row.get('problem_definition', '').strip(),
                    problem_description=row.get('problem_description', '').strip(),
                    target_user_group=row.get('target_user_group', '').strip(),
                    problem_urgency=row.get('problem_urgency', '').strip(),
                    solution=row.get('solution', '').strip(),
                    solution_benefits=row.get('solution_benefits', '').strip(),
                    why_best_equipped=row.get('why_best_equipped', '').strip(),
                    idea_stage=idea_stage,
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
