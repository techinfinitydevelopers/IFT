from django.db import models
from django.contrib.auth.models import User
from students.models import IdeaSubmission, Student, School


class JuryAssignment(models.Model):
    """Legacy jury assignment — kept for backward compat"""
    submission = models.ForeignKey(IdeaSubmission, on_delete=models.CASCADE, related_name='jury_assignments')
    jury_name = models.CharField(max_length=200)
    jury_org = models.CharField(max_length=200, blank=True, help_text="Organisation / Institution")
    assigned_on = models.DateField(null=True, blank=True)
    evaluated_on = models.DateField(null=True, blank=True)
    jury_score = models.IntegerField(null=True, blank=True, help_text="Score given by jury (0-100)")
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.jury_name} → {self.submission}"

    class Meta:
        ordering = ['-assigned_on']


class EvaluatorAssignment(models.Model):
    """Evaluator assigned to manually review a submission (Top 400)"""
    STATUS_CHOICES = [
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('evaluated', 'Evaluated'),
    ]

    evaluator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='evaluator_assignments')
    submission = models.ForeignKey(IdeaSubmission, on_delete=models.CASCADE, related_name='evaluator_assignments')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')
    assigned_on = models.DateTimeField(auto_now_add=True)
    evaluated_on = models.DateTimeField(null=True, blank=True)
    score = models.IntegerField(null=True, blank=True, help_text="Manual evaluation score (0-100)")
    parameter_scores = models.JSONField(default=dict, blank=True, help_text="Dict of parameter: score")
    is_shortlisted = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.evaluator.get_full_name()} → {self.submission}"

    class Meta:
        ordering = ['-assigned_on']
        unique_together = ['evaluator', 'submission']


class Content(models.Model):
    """Content management for Announcements, FAQs and Training sessions"""
    TYPE_CHOICES = [
        ('announcement', 'Announcement'),
        ('faq', 'FAQ'),
        ('training', 'Upcoming Training Calendar'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('scheduled', 'Scheduled'),
        ('archived', 'Archived'),
    ]
    VISIBILITY_CHOICES = [
        ('all', 'All Users'),
        ('students', 'Students Only'),
        ('evaluators', 'Evaluators Only'),
        ('schools', 'Schools Only'),
        ('admins', 'Admins Only'),
    ]

    content_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=300)
    subtitle = models.CharField(max_length=300, blank=True)
    body = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='all')
    tags = models.CharField(max_length=500, blank=True)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='contents')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    # Training-calendar specific fields
    event_date = models.DateField(null=True, blank=True)
    event_time = models.CharField(max_length=50, blank=True)
    event_mode = models.CharField(max_length=50, blank=True, default='Online')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.get_content_type_display()}] {self.title}"

    class Meta:
        ordering = ['-created_at']


class Phase(models.Model):
    """Competition phase/timeline management"""
    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('active', 'Active'),
        ('completed', 'Completed'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming')
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    @property
    def days_remaining(self):
        from django.utils import timezone
        if self.status == 'completed':
            return 0
        delta = (self.end_date - timezone.now().date()).days
        return max(0, delta)

    class Meta:
        ordering = ['order', 'start_date']


class CertificateIssue(models.Model):
    """Audit record of a certificate emailed to a student (or school).

    One row per send attempt. The batch sender skips students who already have a
    successful row for the same cert_type (unless the admin forces a resend).
    """
    CERT_TYPE_CHOICES = [
        ('participation', 'Participation (Idea Submission)'),
        ('top100', 'Top 100'),
        ('top400', 'Top 400'),
        ('school_champion', 'School Champion'),
    ]
    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='certificates'
    )
    school = models.ForeignKey(
        School, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='certificates'
    )
    cert_type = models.CharField(max_length=30, choices=CERT_TYPE_CHOICES)
    recipient_email = models.EmailField()
    name_used = models.CharField(max_length=300)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='sent')
    error = models.TextField(blank=True)
    is_test = models.BooleanField(default=False)
    sent_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='certificates_sent'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.get_cert_type_display()}] {self.name_used} <{self.recipient_email}> ({self.status})"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['cert_type', 'status']),
            models.Index(fields=['student', 'cert_type']),
        ]


class MilestoneEmailLog(models.Model):
    """Dedup record for automated milestone/journey emails (Top 400, Top 100,
    Top 12, School Winner, Zonal Pitch invite, submission/resubmit reminders).

    One row per (student, milestone) — the sender checks this first so the
    same email is never sent twice, even if the trigger runs repeatedly
    (ranking recompute, daily cron, etc).
    """
    MILESTONE_CHOICES = [
        ('idea_reminder', 'Idea Submission Reminder'),
        ('idea_published', 'Idea Published'),
        ('top400', 'Top 400 Announcement'),
        ('resubmit_reminder', 'Resubmit Reminder'),
        ('school_winner', 'School Winner Announcement'),
        ('top100', 'Top 100 Announcement'),
        ('zonal_pitch', 'Zonal Pitch Fest Invite'),
        ('top12', 'Top 12 Announcement'),
        ('hall_of_fame', 'Hall of Fame / Pitch Ticket'),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='milestone_emails'
    )
    milestone = models.CharField(max_length=30, choices=MILESTONE_CHOICES)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.get_milestone_display()}] {self.student}"

    class Meta:
        ordering = ['-sent_at']
        unique_together = ['student', 'milestone']


class RecurringEmailLog(models.Model):
    """Dedup record for weekly/recurring school-facing broadcasts (e.g. the
    Teacher Mentorship Session reminder, sent every Wednesday). Keyed by
    (school, email_key, sent_date) so the SAME day never double-sends (e.g. if
    the cron runs twice), but the next occurrence (next Wednesday) sends fine
    since the date differs.
    """
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name='recurring_emails'
    )
    email_key = models.CharField(max_length=50)
    sent_date = models.DateField()

    def __str__(self):
        return f"[{self.email_key}] {self.school} ({self.sent_date})"

    class Meta:
        ordering = ['-sent_date']
        unique_together = ['school', 'email_key', 'sent_date']


class HallOfFameEntry(models.Model):
    photo = models.ImageField(upload_to='halloffame/', blank=True, null=True, help_text="Student/team photo (optional)")
    student_name = models.CharField(max_length=300)
    school_name = models.CharField(max_length=300)
    idea_title = models.CharField(max_length=300)
    idea_description = models.TextField(blank=True, help_text="Short description shown on card")
    problem_statement = models.TextField(blank=True)
    proposed_solution = models.TextField(blank=True)
    tags = models.JSONField(default=list, help_text="List of SDG tag strings e.g. ['SDG 11 - Sustainable Cities']")
    rank = models.PositiveIntegerField(help_text="1-24")
    season = models.CharField(max_length=50, default='Season 5', help_text="e.g. Season 5")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['rank']

    def __str__(self):
        return f"#{self.rank} - {self.student_name} ({self.season})"


class DigitalResource(models.Model):
    """Downloadable marketing collateral (WhatsApp templates, flyers,
    brochures, standees, banners, BMC, pitch templates, etc.) shown to
    Students and/or Schools, uploaded/managed by admins."""

    CATEGORY_CHOICES = [
        ('whatsapp_template', 'WhatsApp Template'),
        ('flyer', 'Flyer'),
        ('brochure', 'Brochure'),
        ('standee', 'Standee'),
        ('banner', 'Banner'),
        ('bmc', 'Business Model Canvas (BMC)'),
        ('pitch_template', 'Pitch Template'),
        ('other', 'Other'),
    ]
    VISIBILITY_CHOICES = [
        ('all', 'Students & Schools'),
        ('students', 'Students Only'),
        ('schools', 'Schools Only'),
    ]

    title = models.CharField(max_length=200)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='other')
    description = models.CharField(max_length=300, blank=True)
    file = models.FileField(upload_to='digital_resources/%Y/%m/')
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='all')
    is_active = models.BooleanField(default=True)
    uploaded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='uploaded_resources')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_category_display()}] {self.title}"

    @property
    def file_extension(self):
        name = self.file.name or ''
        return name.rsplit('.', 1)[-1].upper() if '.' in name else ''
