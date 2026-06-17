def user_role(request):
    if request.user.is_authenticated:
        try:
            return {'user_role': request.user.profile.role}
        except Exception:
            return {'user_role': 'student'}
    return {'user_role': None}
