from django.urls import path
from . import views

app_name = 're_evaluation'

urlpatterns = [
    path('', views.reeval_list, name='list'),
    path('submit/', views.reeval_submit, name='submit'),
    path('batch-evaluate/', views.reeval_batch_evaluate, name='batch_evaluate'),
    path('batch-status/<str:task_id>/', views.reeval_batch_status, name='batch_status'),
    path('<int:pk>/', views.reeval_detail, name='detail'),
    path('<int:pk>/evaluate/', views.reeval_evaluate, name='evaluate'),
    path('<int:pk>/mentor/', views.reeval_save_mentor, name='save_mentor'),
    path('<int:pk>/delete/', views.reeval_delete, name='delete'),
    path('eval-status/<str:task_id>/', views.reeval_eval_status, name='eval_status'),
]
