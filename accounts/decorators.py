from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect


def role_required(allowed_roles):
    """Decorator to restrict views to specific roles."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:sign_in')
            try:
                profile = request.user.profile
            except Exception:
                return redirect('accounts:sign_in')
            if profile.role not in allowed_roles:
                return HttpResponseForbidden("You do not have permission to access this page.")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def superadmin_required(view_func):
    return role_required(['superadmin'])(view_func)


def jury_required(view_func):
    return role_required(['jury', 'superadmin'])(view_func)


def student_required(view_func):
    return role_required(['student'])(view_func)
