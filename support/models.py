from django.conf import settings
from django.db import models


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

    resolution_note = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

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
    def can_reopen(self):
        return self.status in ('resolved', 'closed')

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
