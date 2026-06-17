from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('sign-in/', views.sign_in, name='sign_in'),
    path('sign-up/', views.sign_up, name='sign_up'),
    path('sign-out/', views.sign_out, name='sign_out'),
    path('redirect/', views.role_redirect, name='role_redirect'),
    path('school-sign-up/', views.school_sign_up, name='school_sign_up'),
    path('api/schools/', views.school_search_api, name='school_search_api'),

    # Password reset
    path('forgot-password/', views.ForgotPasswordView.as_view(), name='password_reset'),
    path('forgot-password/done/', views.ForgotPasswordDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', views.ResetPasswordConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', views.ResetPasswordCompleteView.as_view(), name='password_reset_complete'),
]
