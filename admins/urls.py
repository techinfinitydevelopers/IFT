from django.urls import path
from . import views

app_name = 'admins'

urlpatterns = [
    path('', views.admin_dashboard, name='dashboard'),
    path('submissions/', views.all_submissions, name='all_submissions'),
    path('submission/<int:submission_id>/', views.submission_detail, name='submission_detail'),
    path('submission/<int:submission_id>/regenerate-ai/', views.regenerate_ai_summary, name='regenerate_ai_summary'),
    
    # Evaluation endpoints
    path('submission/<int:submission_id>/evaluate/', views.evaluate_submission, name='evaluate_submission'),
    path('batch-evaluate/', views.batch_evaluate_view, name='batch_evaluate'),
    
    # Rankings
    path('rankings/', views.rankings_view, name='rankings'),
    path('rankings/export/', views.export_top_400, name='export_top_400'),
]
