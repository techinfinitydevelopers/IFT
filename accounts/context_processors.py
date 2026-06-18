def user_role(request):
    if request.user.is_authenticated:
        try:
            return {'user_role': request.user.profile.role}
        except Exception:
            return {'user_role': 'student'}
    return {'user_role': None}


def student_has_submission(request):
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            if profile.role == 'student':
                from students.models import IdeaSubmission
                has_sub = IdeaSubmission.objects.filter(student=request.user.student_profile).exists()
                return {'student_has_submission': has_sub}
        except Exception:
            pass
    return {'student_has_submission': False}
