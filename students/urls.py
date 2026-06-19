from django.urls import path
from django.shortcuts import redirect
from . import views

app_name = 'students'

urlpatterns = [
    path('', views.home, name='home'),
    # Old auth URLs — redirect to new accounts app
    path('register/', lambda r: redirect('accounts:sign_up'), name='register'),
    path('login/', lambda r: redirect('accounts:sign_in'), name='login'),
    path('logout/', lambda r: redirect('accounts:sign_out'), name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.student_profile, name='student_profile'),
    path('submit/', views.submit_idea, name='submit_idea'),
    path('submit/classic/', views.submit_idea_classic, name='submit_idea_classic'),
    path('submission/<int:submission_id>/', views.submission_detail, name='submission_detail'),
    path('submission/<int:submission_id>/confirmation/', views.submission_confirmation, name='submission_confirmation'),
    path('my-idea/', views.my_idea, name='my_idea'),
    path('team/', views.team_page, name='team_page'),
    path('team/create/', views.create_team, name='create_team'),
    path('team/join/', views.join_team, name='join_team'),
    path('team/invite/', views.invite_member, name='invite_member'),
    path('team/remove-member/', views.remove_team_member, name='remove_team_member'),
    path('idea-corner/', views.idea_corner, name='idea_corner'),
    path('hall-of-fame/', views.student_halloffame, name='student_halloffame'),
    path('school/dashboard/', views.school_dashboard, name='school_dashboard'),
    path('school/students/', views.school_students, name='school_students'),
    path('school/teams/', views.school_teams, name='school_teams'),
    path('school/submissions/', views.school_submissions, name='school_submissions'),
    path('school/results/', views.school_results, name='school_results'),
    path('school/reports/', views.school_reports, name='school_reports'),
    path('school/hall-of-fame/', views.school_halloffame, name='school_halloffame'),
    path('school/faq/', views.school_faq, name='school_faq'),
    path('school/profile/', views.school_profile, name='school_profile'),
    path('evaluator/dashboard/', views.evaluator_dashboard, name='evaluator_dashboard'),
    path('evaluator/assigned-ideas/', views.evaluator_assigned_ideas, name='evaluator_assigned_ideas'),
    path('evaluator/evaluate/<int:assignment_id>/', views.evaluator_evaluate_idea, name='evaluator_evaluate'),
    path('evaluator/profile/', views.evaluator_profile, name='evaluator_profile'),
    path('evaluator/hall-of-fame/', views.evaluator_halloffame, name='evaluator_halloffame'),
    path('evaluator/faq/', views.evaluator_faq, name='evaluator_faq'),
    path('idea/<int:submission_id>/publish/', views.publish_idea, name='publish_idea'),
    # Collaborative editing
    path('idea/<int:submission_id>/suggest/', views.suggest_edit, name='suggest_edit'),
    path('idea/<int:submission_id>/suggestions/', views.review_suggestions, name='review_suggestions'),
    path('suggestion/<int:suggestion_id>/handle/', views.handle_suggestion, name='handle_suggestion'),
    # Notifications
    path('notifications/', views.notifications_page, name='notifications_page'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_read'),
    # Video tracking
    path('video/<int:video_id>/watched/', views.mark_video_watched, name='mark_video_watched'),
    path('video-status/', views.video_completion_status, name='video_completion_status'),
]
