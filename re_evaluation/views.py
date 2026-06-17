import os
import uuid
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import LightSubmission, LightSubmissionFile, MentorScore
from .forms import LightSubmissionForm, MentorScoreForm

# In-memory tracker for background evaluations
EVAL_TRACKER = {}

# In-memory tracker for batch evaluations
BATCH_TRACKER = {}


def is_staff_or_superuser(user):
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(is_staff_or_superuser)
def reeval_list(request):
    """List all re-evaluation submissions with comparison summary"""
    submissions = LightSubmission.objects.all().order_by('-created_at')

    items = []
    for s in submissions:
        try:
            mentor = s.mentor_score
        except MentorScore.DoesNotExist:
            mentor = None

        items.append({
            'submission': s,
            'mentor': mentor,
            'diff': (s.ai_total_score - mentor.mentor_total_score) if (s.is_evaluated and mentor) else None,
        })

    pending_count = submissions.filter(is_evaluated=False).count()

    # Calculate comparison stats
    compared = 0
    total_ai = 0
    total_mentor = 0
    total_abs_diff = 0
    within_5 = 0
    within_10 = 0
    within_15 = 0
    within_20 = 0
    max_diff = 0

    for item in items:
        s = item['submission']
        m = item['mentor']
        if s.is_evaluated and m:
            ai = s.ai_total_score
            mentor_total = m.mentor_total_score
            diff = abs(ai - mentor_total)
            compared += 1
            total_ai += ai
            total_mentor += mentor_total
            total_abs_diff += diff
            if diff <= 5: within_5 += 1
            if diff <= 10: within_10 += 1
            if diff <= 15: within_15 += 1
            if diff <= 20: within_20 += 1
            if diff > max_diff: max_diff = diff

    stats = None
    param_stats = []
    if compared > 0:
        above_20 = compared - within_20
        stats = {
            'compared': compared,
            'avg_ai': round(total_ai / compared, 1),
            'avg_mentor': round(total_mentor / compared, 1),
            'avg_diff': round(total_abs_diff / compared, 1),
            'within_5': within_5,
            'within_5_pct': round(within_5 / compared * 100),
            'within_10': within_10,
            'within_10_pct': round(within_10 / compared * 100),
            'within_15': within_15,
            'within_15_pct': round(within_15 / compared * 100),
            'within_20': within_20,
            'within_20_pct': round(within_20 / compared * 100),
            'above_20': above_20,
            'above_20_pct': round(above_20 / compared * 100),
        }

        # Parameter-wise comparison
        param_fields = [
            ('Uniqueness', 'uniqueness_score'),
            ('Ease of Implementation', 'ease_of_implementation_score'),
            ('Feasibility', 'feasibility_score'),
            ('Impact', 'impactful_score'),
            ('Sustainability', 'sustainable_score'),
            ('Conceptual Clarity', 'conceptual_clarity_score'),
            ('Empathy', 'empathy_score'),
            ('Creativity', 'creativity_score'),
            ('Communication', 'communication_score'),
            ('Flexible Thinking', 'flexible_thinking_score'),
        ]
        for label, field in param_fields:
            ai_vals = []
            mentor_vals = []
            for item in items:
                s = item['submission']
                m = item['mentor']
                if s.is_evaluated and m and m.mentor_total_score > 0:
                    ai_vals.append(getattr(s, field, 0) or 0)
                    mentor_vals.append(getattr(m, field, 0) or 0)
            if ai_vals:
                mode_ai_p = Counter(ai_vals).most_common(1)[0][0]
                mode_mentor_p = Counter(mentor_vals).most_common(1)[0][0]
                mode_diff_p = mode_ai_p - mode_mentor_p
                param_stats.append({
                    'label': label,
                    'avg_ai': mode_ai_p,
                    'avg_mentor': mode_mentor_p,
                    'diff': mode_diff_p,
                    'abs_diff': abs(mode_diff_p),
                })

    context = {
        'items': items,
        'total': submissions.count(),
        'evaluated': submissions.filter(is_evaluated=True).count(),
        'with_mentor': MentorScore.objects.count(),
        'pending_count': pending_count,
        'total_count': submissions.count(),
        'stats': stats,
        'param_stats': param_stats,
    }
    return render(request, 're_evaluation/list.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def reeval_submit(request):
    """Submit a new light idea for re-evaluation"""
    if request.method == 'POST':
        form = LightSubmissionForm(request.POST)
        if form.is_valid():
            submission = form.save()

            files = request.FILES.getlist('attachments')
            for f in files:
                ext = f.name.lower().split('.')[-1]
                if ext in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
                    file_type = 'image'
                elif ext in ('mp4', 'webm', 'mov', 'mpeg', 'mpg'):
                    file_type = 'video'
                else:
                    file_type = 'document'

                LightSubmissionFile.objects.create(
                    submission=submission,
                    file=f,
                    file_type=file_type,
                    original_filename=f.name,
                )

            messages.success(request, f'Idea "{submission.project_name}" submitted successfully.')
            return redirect('re_evaluation:detail', pk=submission.pk)
    else:
        form = LightSubmissionForm()

    return render(request, 're_evaluation/submit.html', {'form': form})


@login_required
@user_passes_test(is_staff_or_superuser)
def reeval_detail(request, pk):
    """Detail view with AI evaluation, mentor score input, and comparison"""
    submission = get_object_or_404(LightSubmission, pk=pk)

    try:
        mentor = submission.mentor_score
    except MentorScore.DoesNotExist:
        mentor = None

    params = [
        ('Uniqueness', 'uniqueness_score', 'uniqueness_justification'),
        ('Ease of Implementation', 'ease_of_implementation_score', 'ease_of_implementation_justification'),
        ('Feasibility', 'feasibility_score', 'feasibility_justification'),
        ('Impact', 'impactful_score', 'impactful_justification'),
        ('Sustainability', 'sustainable_score', 'sustainable_justification'),
        ('Conceptual Clarity', 'conceptual_clarity_score', 'conceptual_clarity_justification'),
        ('Empathy', 'empathy_score', 'empathy_justification'),
        ('Creativity', 'creativity_score', 'creativity_justification'),
        ('Communication', 'communication_score', 'communication_justification'),
        ('Flexible Thinking', 'flexible_thinking_score', 'flexible_thinking_justification'),
    ]

    comparison = []
    for label, score_field, just_field in params:
        ai_score = getattr(submission, score_field) if submission.is_evaluated else None
        mentor_score = getattr(mentor, score_field) if mentor else None
        diff = (ai_score - mentor_score) if (ai_score is not None and mentor_score is not None) else None
        comparison.append({
            'label': label,
            'ai_score': ai_score,
            'mentor_score': mentor_score,
            'diff': diff,
            'justification': getattr(submission, just_field, ''),
        })

    mentor_form = MentorScoreForm(instance=mentor) if mentor else MentorScoreForm()

    context = {
        'submission': submission,
        'mentor': mentor,
        'comparison': comparison,
        'mentor_form': mentor_form,
        'files': submission.files.all(),
    }
    return render(request, 're_evaluation/detail.html', context)


@csrf_exempt
@login_required
@user_passes_test(is_staff_or_superuser)
def reeval_evaluate(request, pk):
    """Start AI evaluation in background thread, return task_id for polling."""
    submission = get_object_or_404(LightSubmission, pk=pk)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    task_id = str(uuid.uuid4())
    EVAL_TRACKER[task_id] = {
        'status': 'running',
        'step': 'Starting evaluation...',
        'submission_pk': pk,
        'error': None,
    }

    def run_evaluation(submission_pk, task_id):
        import django
        django.setup()
        from django.db import connection
        tracker = EVAL_TRACKER[task_id]

        try:
            from .evaluator import evaluate_light_submission
            from .models import LightSubmission as LS

            sub = LS.objects.get(pk=submission_pk)
            tracker['step'] = 'Analyzing attachments with AI...'
            sub = evaluate_light_submission(sub)
            tracker['status'] = 'completed'
            tracker['step'] = 'Done'
        except Exception as e:
            tracker['status'] = 'failed'
            tracker['error'] = str(e)
            tracker['step'] = f'Failed: {str(e)[:100]}'
        finally:
            connection.close()

    thread = threading.Thread(target=run_evaluation, args=(pk, task_id))
    thread.daemon = True
    thread.start()

    return JsonResponse({'task_id': task_id})


@login_required
@user_passes_test(is_staff_or_superuser)
def reeval_eval_status(request, task_id):
    """Poll evaluation progress."""
    tracker = EVAL_TRACKER.get(task_id)
    if not tracker:
        return JsonResponse({'error': 'Task not found'}, status=404)

    response = {
        'status': tracker['status'],
        'step': tracker['step'],
    }

    if tracker['status'] == 'completed':
        # Return scores
        try:
            sub = LightSubmission.objects.get(pk=tracker['submission_pk'])
            response['scores'] = {
                'uniqueness': {'score': sub.uniqueness_score, 'justification': sub.uniqueness_justification},
                'ease_of_implementation': {'score': sub.ease_of_implementation_score, 'justification': sub.ease_of_implementation_justification},
                'feasibility': {'score': sub.feasibility_score, 'justification': sub.feasibility_justification},
                'impactful': {'score': sub.impactful_score, 'justification': sub.impactful_justification},
                'sustainable': {'score': sub.sustainable_score, 'justification': sub.sustainable_justification},
                'conceptual_clarity': {'score': sub.conceptual_clarity_score, 'justification': sub.conceptual_clarity_justification},
                'empathy': {'score': sub.empathy_score, 'justification': sub.empathy_justification},
                'creativity': {'score': sub.creativity_score, 'justification': sub.creativity_justification},
                'communication': {'score': sub.communication_score, 'justification': sub.communication_justification},
                'flexible_thinking': {'score': sub.flexible_thinking_score, 'justification': sub.flexible_thinking_justification},
            }
            response['total_score'] = sub.ai_total_score
            response['confidence'] = sub.ai_confidence
            response['overall_justification'] = sub.overall_justification
        except LightSubmission.DoesNotExist:
            response['status'] = 'failed'
            response['error'] = 'Submission not found'

    elif tracker['status'] == 'failed':
        response['error'] = tracker['error']

    return JsonResponse(response)


@login_required
@user_passes_test(is_staff_or_superuser)
def reeval_save_mentor(request, pk):
    """Save mentor scores for a submission"""
    submission = get_object_or_404(LightSubmission, pk=pk)

    if request.method != 'POST':
        return redirect('re_evaluation:detail', pk=pk)

    try:
        mentor = submission.mentor_score
        form = MentorScoreForm(request.POST, instance=mentor)
    except MentorScore.DoesNotExist:
        form = MentorScoreForm(request.POST)

    if form.is_valid():
        mentor = form.save(commit=False)
        mentor.submission = submission
        mentor.save()
        messages.success(request, f'Mentor scores saved for "{submission.project_name}".')
    else:
        messages.error(request, 'Invalid scores. Please check all fields are 0-10.')

    return redirect('re_evaluation:detail', pk=pk)


@login_required
@user_passes_test(is_staff_or_superuser)
def reeval_delete(request, pk):
    """Delete a light submission"""
    submission = get_object_or_404(LightSubmission, pk=pk)
    if request.method == 'POST':
        name = submission.project_name
        submission.delete()
        messages.success(request, f'"{name}" deleted.')
        return redirect('re_evaluation:list')
    return redirect('re_evaluation:detail', pk=pk)


@csrf_exempt
@login_required
@user_passes_test(is_staff_or_superuser)
def reeval_batch_evaluate(request):
    """Start batch AI evaluation for all pending submissions."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    # Check if a batch is already running
    for tid, tracker in BATCH_TRACKER.items():
        if tracker['status'] == 'running':
            return JsonResponse({
                'error': 'A batch evaluation is already running.',
                'task_id': tid,
            }, status=409)

    force_all = request.POST.get('force_all', 'false') == 'true'
    if force_all:
        pending = LightSubmission.objects.all()
    else:
        pending = LightSubmission.objects.filter(is_evaluated=False)
    pending_ids = list(pending.values_list('pk', flat=True))

    if not pending_ids:
        return JsonResponse({'error': 'No ideas to evaluate.'}, status=400)

    # Number of parallel workers (5 ideas evaluate simultaneously)
    parallel_count = 5

    task_id = str(uuid.uuid4())
    BATCH_TRACKER[task_id] = {
        'status': 'running',
        'total': len(pending_ids),
        'completed': 0,
        'failed': 0,
        'in_progress': [],
        'errors': [],
        'results': [],
    }

    def evaluate_single(pk, tracker):
        """Evaluate a single submission. Runs inside a thread pool worker."""
        import django
        django.setup()
        from django.db import connection

        name = ''
        try:
            from .evaluator import evaluate_light_submission
            from .models import LightSubmission as LS

            sub = LS.objects.get(pk=pk)
            name = sub.project_name
            tracker['in_progress'].append(name)

            sub = evaluate_light_submission(sub)

            tracker['completed'] += 1
            tracker['results'].append({
                'pk': pk,
                'name': sub.project_name,
                'score': sub.ai_total_score,
                'status': 'success',
            })
        except Exception as e:
            tracker['failed'] += 1
            tracker['errors'].append({'pk': pk, 'error': str(e)[:200]})
            tracker['results'].append({
                'pk': pk,
                'name': name,
                'score': None,
                'status': 'failed',
                'error': str(e)[:100],
            })
        finally:
            if name in tracker['in_progress']:
                tracker['in_progress'].remove(name)
            connection.close()

    def run_batch_parallel(pending_ids, task_id):
        tracker = BATCH_TRACKER[task_id]
        with ThreadPoolExecutor(max_workers=parallel_count) as pool:
            futures = {
                pool.submit(evaluate_single, pk, tracker): pk
                for pk in pending_ids
            }
            for future in as_completed(futures):
                pass  # results already tracked inside evaluate_single

        tracker['status'] = 'completed'
        tracker['in_progress'] = []

    thread = threading.Thread(target=run_batch_parallel, args=(pending_ids, task_id))
    thread.daemon = True
    thread.start()

    return JsonResponse({
        'task_id': task_id,
        'total': len(pending_ids),
        'parallel': parallel_count,
    })


@login_required
@user_passes_test(is_staff_or_superuser)
def reeval_batch_status(request, task_id):
    """Poll batch evaluation progress."""
    tracker = BATCH_TRACKER.get(task_id)
    if not tracker:
        return JsonResponse({'error': 'Task not found'}, status=404)

    response = {
        'status': tracker['status'],
        'total': tracker['total'],
        'completed': tracker['completed'],
        'failed': tracker['failed'],
        'in_progress': list(tracker.get('in_progress', [])),
        'progress_pct': round((tracker['completed'] + tracker['failed']) / max(tracker['total'], 1) * 100),
    }

    if tracker['status'] == 'completed':
        response['results'] = tracker['results']
        response['errors'] = tracker['errors']

    return JsonResponse(response)
