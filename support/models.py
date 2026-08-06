from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

# SLA response window (in hours) by priority. Overdue = unresolved past this.
SLA_HOURS = {'urgent': 8, 'high': 24, 'medium': 48, 'low': 72}
# A resolved/closed ticket may be reopened by the user within this many days.
REOPEN_WINDOW_DAYS = 7
_OPEN_STATES = ('open', 'in_progress', 'waiting_user', 'reopened')


class Ticket(models.Model):
    """A support ticket raised by a student or a teacher/school."""

    CATEGORY_CHOICES = [
        ('technical', 'Technical Issue'),
        ('login', 'Login Issue'),
        ('payment', 'Payment'),
        ('course', 'Course'),
        ('school_support', 'School Support'),
        ('other', 'Other'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('waiting_user', 'Waiting for User'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('reopened', 'Reopened'),
    ]
    CREATOR_CHOICES = [
        ('student', 'Student'),
        ('school', 'School / Teacher'),
    ]

    ticket_number = models.CharField(max_length=20, unique=True, blank=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tickets_created')
    creator_type = models.CharField(max_length=10, choices=CREATOR_CHOICES, default='student')

    subject = models.CharField(max_length=300)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    description = models.TextField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tickets_assigned')
    # Assign to an external support email (e.g. rayaan@/pinky@) that has no login.
    assigned_email = models.EmailField(blank=True)

    resolution_note = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    # Set when this ticket is merged as a duplicate into another ticket.
    merged_into = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='merged_from')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.ticket_number} - {self.subject}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Assign a stable, human-readable number once the PK exists.
        if not self.ticket_number:
            self.ticket_number = f'TKT-{self.pk:06d}'
            super().save(update_fields=['ticket_number'])

    @property
    def sla_due_at(self):
        return self.created_at + timedelta(hours=SLA_HOURS.get(self.priority, 48))

    @property
    def is_overdue(self):
        return self.status in _OPEN_STATES and timezone.now() > self.sla_due_at

    @property
    def assignee_label(self):
        if self.assigned_to:
            return self.assigned_to.get_full_name() or self.assigned_to.username
        return self.assigned_email or 'Not assigned'

    @property
    def can_reopen(self):
        """User may reopen a resolved/closed ticket within the reopen window."""
        if self.status not in ('resolved', 'closed'):
            return False
        ref = self.resolved_at or self.updated_at
        if ref is None:
            return True
        return timezone.now() <= ref + timedelta(days=REOPEN_WINDOW_DAYS)

    @property
    def status_badge_class(self):
        return {
            'open': 'open',
            'in_progress': 'progress',
            'waiting_user': 'waiting',
            'resolved': 'resolved',
            'closed': 'closed',
            'reopened': 'reopened',
        }.get(self.status, 'open')


class TicketMessage(models.Model):
    """A reply in a ticket's conversation thread."""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='ticket_messages')
    body = models.TextField()
    # Reserved for Phase 2 internal/private admin notes; always False in Phase 1.
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Msg on {self.ticket.ticket_number} by {self.author_id}'


class TicketAttachment(models.Model):
    """A file attached to a ticket or one of its messages."""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='attachments')
    message = models.ForeignKey(
        TicketMessage, on_delete=models.CASCADE, null=True, blank=True, related_name='attachments')
    file = models.FileField(upload_to='tickets/%Y/%m/')
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='ticket_attachments')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name or (self.file.name if self.file else 'attachment')


class TicketEvent(models.Model):
    """An audit-trail entry for a ticket's action timeline."""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='events')
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='ticket_events')
    # e.g. created, assigned, replied, status, priority, resolved, reopened, closed, merged, note
    verb = models.CharField(max_length=20)
    detail = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.ticket_id}:{self.verb}'

    @property
    def icon(self):
        return {
            'created': 'add_circle', 'assigned': 'person', 'replied': 'reply',
            'status': 'sync', 'priority': 'flag', 'resolved': 'task_alt',
            'reopened': 'restart_alt', 'closed': 'lock', 'merged': 'merge',
            'note': 'sticky_note_2',
        }.get(self.verb, 'radio_button_checked')
