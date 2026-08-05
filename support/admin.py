from django.contrib import admin

from .models import Ticket, TicketMessage, TicketAttachment


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0


class TicketAttachmentInline(admin.TabularInline):
    model = TicketAttachment
    extra = 0


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'subject', 'creator_type', 'category',
                    'priority', 'status', 'assigned_to', 'created_at')
    list_filter = ('status', 'priority', 'category', 'creator_type')
    search_fields = ('ticket_number', 'subject', 'created_by__username', 'created_by__email')
    inlines = [TicketMessageInline, TicketAttachmentInline]
