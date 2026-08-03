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
    path('user-management/students/export/', views.export_students_csv, name='export_students_csv'),
    path('user-management/onboard-student/', views.onboard_student, name='onboard_student'),
    path('user-management/student/<int:student_id>/edit/', views.edit_student, name='edit_student'),
    path('user-management/student/<int:student_id>/delete/', views.delete_student, name='delete_student'),
    path('user-management/student/<int:student_id>/reset-password/', views.reset_student_password, name='reset_student_password'),
    path('user-management/students/bulk-toggle-status/', views.bulk_toggle_student_status, name='bulk_toggle_student_status'),
    path('user-management/students/bulk-delete/', views.bulk_delete_students, name='bulk_delete_students'),
    path('user-management/schools/', views.schools_list, name='schools_list'),
    path('user-management/schools/export/', views.export_schools_csv, name='export_schools_csv'),
    path('user-management/schools/import/', views.import_schools_csv, name='import_schools_csv'),
    path('user-management/schools/sample-csv/', views.download_schools_sample_csv, name='download_schools_sample_csv'),
    path('user-management/onboard-school/', views.onboard_school, name='onboard_school'),
    path('user-management/onboard-evaluator/', views.onboard_evaluator, name='onboard_evaluator'),
    path('user-management/evaluators/', views.evaluators_list, name='evaluators_list'),
    path('user-management/evaluator/<int:evaluator_id>/edit/', views.edit_evaluator, name='edit_evaluator'),
    path('user-management/school/<int:school_id>/edit/', views.edit_school, name='edit_school'),
    path('user-management/school/<int:school_id>/delete/', views.delete_school, name='delete_school'),
    path('user-management/delete-test-data/', views.delete_test_data, name='delete_test_data'),
    path('user-management/school/<int:school_id>/reset-password/', views.reset_school_password, name='reset_school_password'),
    path('user-management/school/<int:school_id>/toggle-status/', views.toggle_school_status, name='toggle_school_status'),
    path('user-management/schools/bulk-toggle-status/', views.bulk_toggle_school_status, name='bulk_toggle_school_status'),

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

    # Digital Resources
    path('digital-resources/', views.digital_resources_list, name='digital_resources_list'),
    path('digital-resources/upload/', views.digital_resource_upload, name='digital_resource_upload'),
    path('digital-resources/<int:resource_id>/edit/', views.digital_resource_edit, name='digital_resource_edit'),
    path('digital-resources/<int:resource_id>/delete/', views.digital_resource_delete, name='digital_resource_delete'),
    path('digital-resources/<int:resource_id>/toggle-status/', views.digital_resource_toggle_status, name='digital_resource_toggle_status'),

    # Hall of Fame
    path('hall-of-fame/', views.halloffame_list, name='halloffame_list'),
    path('hall-of-fame/create/', views.halloffame_create, name='halloffame_create'),
    path('hall-of-fame/<int:entry_id>/edit/', views.halloffame_edit, name='halloffame_edit'),
    path('hall-of-fame/<int:entry_id>/delete/', views.halloffame_delete, name='halloffame_delete'),

    # Schedule & Timeline
    path('schedule/', views.schedule_view, name='schedule'),
    path('schedule/create/', views.phase_create, name='phase_create'),
    path('schedule/<int:phase_id>/edit/', views.phase_edit, name='phase_edit'),
    path('schedule/<int:phase_id>/delete/', views.phase_delete, name='phase_delete'),

    # Reports
    path('reports/', views.reports_view, name='reports'),

    # Certificates
    path('certificates/', views.certificates_view, name='certificates'),
    path('certificates/preview/<str:cert_type>/', views.preview_certificate, name='preview_certificate'),
    path('certificates/send-test/', views.send_test_certificate, name='send_test_certificate'),
    path('certificates/send-batch/', views.send_certificates_batch, name='send_certificates_batch'),
    path('certificates/suggest/<str:cert_type>/', views.certificate_suggestions, name='certificate_suggestions'),
    path('certificates/send-one/', views.send_single_certificate, name='send_single_certificate'),
]
