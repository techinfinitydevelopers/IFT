from django.contrib import admin
from .models import JuryAssignment, HallOfFameEntry


@admin.register(JuryAssignment)
class JuryAssignmentAdmin(admin.ModelAdmin):
    list_display = ('jury_name', 'jury_org', 'submission', 'assigned_on', 'evaluated_on', 'jury_score')
    search_fields = ('jury_name', 'submission__title')
    list_filter = ('assigned_on', 'evaluated_on')


@admin.register(HallOfFameEntry)
class HallOfFameEntryAdmin(admin.ModelAdmin):
    list_display = ['rank', 'student_name', 'idea_title', 'season', 'is_active']
    list_filter = ['season', 'is_active']
    ordering = ['rank']
