from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Count
from students.models import IdeaSubmission, Student


def is_staff_or_superuser(user):
    """Check if user is staff or superuser"""
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(is_staff_or_superuser)
def admin_dashboard(request):
    """Admin dashboard showing all submissions"""
    submissions = IdeaSubmission.objects.filter(status='submitted').select_related('student__user', 'ai_summary')
    
    # Filter by category if specified
    category = request.GET.get('category')
    if category:
        submissions = submissions.filter(final_category=category)
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        submissions = submissions.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(student__user__first_name__icontains=search_query) |
            Q(student__user__last_name__icontains=search_query)
        )
    
    # Get category statistics
    category_stats = IdeaSubmission.objects.filter(status='submitted').values('final_category').annotate(
        count=Count('id')
    ).order_by('-count')
    
    total_submissions = IdeaSubmission.objects.filter(status='submitted').count()
    ai_processed_count = IdeaSubmission.objects.filter(status='submitted', ai_processed=True).count()
    
    context = {
        'submissions': submissions,
        'category_stats': category_stats,
        'total_submissions': total_submissions,
        'ai_processed_count': ai_processed_count,
        'selected_category': category,
        'search_query': search_query,
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
    
    # Get all uploaded files
    uploaded_files = submission.uploaded_files.all()
    
    # Count files with extracted text (included in AI analysis)
    files_with_text_count = sum(1 for f in uploaded_files if f.extracted_text)
    
    context = {
        'submission': submission,
        'ai_summary': ai_summary,
        'uploaded_files': uploaded_files,
        'files_with_text_count': files_with_text_count,
    }
    
    return render(request, 'admins/submission_detail.html', context)


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
    """
    Regenerate AI summary for a submission.
    Accepts query param 'premium=1' to use premium model (Deep Review).
    """
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

