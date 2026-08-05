from django.contrib import admin

from .models import IFTxHighlight, HighlightMedia, HighlightParticipant


class HighlightMediaInline(admin.TabularInline):
    model = HighlightMedia
    extra = 0


class HighlightParticipantInline(admin.TabularInline):
    model = HighlightParticipant
    extra = 0


@admin.register(IFTxHighlight)
class IFTxHighlightAdmin(admin.ModelAdmin):
    list_display = ('title', 'school', 'event_date', 'is_reviewed', 'created_by', 'created_at')
    list_filter = ('is_reviewed', 'event_date')
    search_fields = ('title', 'summary', 'school__name')
    inlines = [HighlightMediaInline, HighlightParticipantInline]
