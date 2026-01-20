from django.contrib import admin
from .models import AISummary


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
