from django.urls import path
from . import views

app_name = 'admins'

urlpatterns = [
    path('', views.admin_dashboard, name='dashboard'),
    path('submissions/', views.all_submissions, name='all_submissions'),
    path('submissions/classic/', views.all_submissions_classic, name='all_submissions_classic'),
    path('submission/<int:submission_id>/', views.submission_detail, name='submission_detail'),
    path('submission/<int:submission_id>/classic/', views.submission_detail_v2, name='submission_detail_classic'),
    path('submission/<int:submission_id>/preview.json', views.submission_preview_json, name='submission_preview_json'),
    path('submission/<int:submission_id>/update-status/', views.update_submission_status, name='update_submission_status'),
    path('submission/<int:submission_id>/regenerate-ai/', views.regenerate_ai_summary, name='regenerate_ai_summary'),
    
    # Evaluation endpoints
    path('submission/<int:submission_id>/evaluate/', views.evaluate_submission, name='evaluate_submission'),
    path('submission/<int:submission_id>/evaluate-async/', views.evaluate_submission_async, name='evaluate_submission_async'),
    path('batch-evaluate/', views.batch_evaluate_view, name='batch_evaluate'),
    
    # Rankings
    path('rankings/', views.rankings_view, name='rankings'),
    path('rankings/export/', views.export_top_400, name='export_top_400'),
    path('rankings/download-template/', views.download_template, name='download_template'),
    path('rankings/bulk-upload/', views.bulk_upload_ideas, name='bulk_upload_ideas'),
    path('rankings/progress/<str:task_id>/', views.get_progress, name='get_progress'),
    path('rankings/batch-evaluate-async/', views.batch_evaluate_async, name='batch_evaluate_async'),

    # User Management
    path('user-management/students/', views.students_list, name='students_list'),
    path('user-management/onboard-student/', views.onboard_student, name='onboard_student'),
    path('user-management/schools/', views.schools_list, name='schools_list'),
    path('user-management/onboard-school/', views.onboard_school, name='onboard_school'),
    path('user-management/onboard-evaluator/', views.onboard_evaluator, name='onboard_evaluator'),
    path('user-management/evaluators/', views.evaluators_list, name='evaluators_list'),

    # Evaluator Management
    path('evaluator-management/', views.evaluator_management, name='evaluator_management'),
    path('evaluator-management/assign/', views.assign_ideas, name='assign_ideas'),
    path('evaluator-management/bulk-assign/', views.bulk_assign_ideas, name='bulk_assign_ideas'),
    path('evaluator-management/unassigned-ideas/', views.get_unassigned_ideas, name='get_unassigned_ideas'),
    path('evaluator-management/detail/<int:evaluator_id>/', views.evaluator_detail_api, name='evaluator_detail_api'),

    # Content Management
    path('content/', views.content_list, name='content_list'),
    path('content/create/', views.content_create, name='content_create'),
    path('content/<int:content_id>/edit/', views.content_edit, name='content_edit'),
    path('content/<int:content_id>/delete/', views.content_delete, name='content_delete'),
    path('content/<int:content_id>/toggle-status/', views.content_toggle_status, name='content_toggle_status'),

    # Schedule & Timeline
    path('schedule/', views.schedule_view, name='schedule'),
    path('schedule/create/', views.phase_create, name='phase_create'),
    path('schedule/<int:phase_id>/edit/', views.phase_edit, name='phase_edit'),
    path('schedule/<int:phase_id>/delete/', views.phase_delete, name='phase_delete'),

    # Reports
    path('reports/', views.reports_view, name='reports'),
]
