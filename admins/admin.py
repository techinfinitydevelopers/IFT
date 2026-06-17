from django.contrib import admin
from .models import JuryAssignment


@admin.register(JuryAssignment)
class JuryAssignmentAdmin(admin.ModelAdmin):
    list_display = ('jury_name', 'jury_org', 'submission', 'assigned_on', 'evaluated_on', 'jury_score')
    search_fields = ('jury_name', 'submission__title')
    list_filter = ('assigned_on', 'evaluated_on')
