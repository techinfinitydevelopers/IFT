from django.contrib import admin
from .models import AISummary, AIEvaluation


@admin.register(AIEvaluation)
class AIEvaluationAdmin(admin.ModelAdmin):
    """Top 12 / Zonal Pitch have no scoring formula — a staff member selects
    them here by ticking the box. Saving (ticking + Save) is what fires the
    one-time milestone email (see ai_assistant/signals.py)."""
    list_display = ('submission', 'final_score', 'rank', 'is_top_400',
                     'is_top_12', 'zonal_pitch_invited', 'is_disqualified')
    list_editable = ('is_top_12', 'zonal_pitch_invited')
    list_filter = ('is_top_400', 'is_top_12', 'zonal_pitch_invited', 'is_disqualified')
    search_fields = ('submission__title', 'submission__student__user__email',
                      'submission__student__user__first_name',
                      'submission__student__user__last_name')
    readonly_fields = ('final_score', 'rank')


@admin.register(AISummary)
class AISummaryAdmin(admin.ModelAdmin):
    list_display = ('submission', 'is_complete', 'model_used', 'tokens_used', 'created_at')
    search_fields = ('submission__title', 'summary')
    list_filter = ('is_complete', 'model_used', 'created_at')
    readonly_fields = ('created_at', 'processing_time', 'tokens_used')
    fieldsets = (
        ('Summary', {
            'fields': ('submission', 'summary', 'suggested_tags')
        }),
        ('Validation', {
            'fields': ('is_complete', 'completeness_notes')
        }),
        ('Processing Metadata', {
            'fields': ('model_used', 'tokens_used', 'processing_time', 'raw_response', 'created_at'),
            'classes': ('collapse',)
        }),
    )
