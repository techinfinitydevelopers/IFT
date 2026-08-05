from django.urls import path
from django.shortcuts import redirect
from . import views
from support import views as support_views
from highlights import views as highlights_views

app_name = 'students'

urlpatterns = [
    path('', views.home, name='home'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-service/', views.terms_of_service, name='terms_of_service'),
    path('api/school-inquiry', views.landing_school_inquiry, name='landing_school_inquiry'),
    path('api/partner-inquiry', views.landing_partner_inquiry, name='landing_partner_inquiry'),
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
    path('idea/<int:idea_id>/like/', views.toggle_idea_like, name='toggle_idea_like'),
    path('idea/<int:idea_id>/bookmark/', views.toggle_idea_bookmark, name='toggle_idea_bookmark'),
    path('push/subscribe/', views.push_subscribe, name='push_subscribe'),
    path('hall-of-fame/', views.student_halloffame, name='student_halloffame'),
    path('faq/', views.student_faq, name='student_faq'),
    # Raise a Ticket / Help (shared by students & schools)
    path('help/', support_views.my_tickets, name='my_tickets'),
    path('help/raise/', support_views.raise_ticket, name='raise_ticket'),
    path('help/ticket/<int:ticket_id>/', support_views.ticket_detail, name='ticket_detail'),
    # IFTx Highlights (school/teacher)
    path('iftx-highlights/', highlights_views.my_highlights, name='my_highlights'),
    path('iftx-highlights/upload/', highlights_views.upload_highlight, name='upload_highlight'),
    path('iftx-highlights/<int:highlight_id>/', highlights_views.highlight_detail, name='highlight_detail'),
    path('learning-resources/', views.learning_resources, name='learning_resources'),
    path('digital-resources/', views.digital_resources, name='digital_resources'),
    path('code-ai/', views.code_ai, name='code_ai'),
    path('school/dashboard/', views.school_dashboard, name='school_dashboard'),
    path('school/students/', views.school_students, name='school_students'),
    path('school/teams/', views.school_teams, name='school_teams'),
    path('school/submissions/', views.school_submissions, name='school_submissions'),
    path('school/results/', views.school_results, name='school_results'),
    path('school/reports/', views.school_reports, name='school_reports'),
    path('school/hall-of-fame/', views.school_halloffame, name='school_halloffame'),
    path('school/submission/<int:submission_id>/', views.school_submission_detail, name='school_submission_detail'),
    path('school/learning-resources/', views.school_learning_resources, name='school_learning_resources'),
    path('school/digital-resources/', views.school_digital_resources, name='school_digital_resources'),
    path('school/faq/', views.school_faq, name='school_faq'),
    path('school/profile/', views.school_profile, name='school_profile'),
    path('school/payments/', views.school_payments, name='school_payments'),
    path('school/live-stats/', views.platform_live_stats, name='platform_live_stats'),
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
    # Test payment
    path('test-payment/', views.test_payment, name='test_payment'),
    # Payment
    path('payment/', views.initiate_payment, name='initiate_payment'),
    path('payment/verify/', views.verify_payment, name='verify_payment'),
    path('payment/webhook/', views.razorpay_webhook, name='razorpay_webhook'),
]
