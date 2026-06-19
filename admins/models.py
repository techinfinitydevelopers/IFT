from django.db import models
from django.contrib.auth.models import User
from students.models import IdeaSubmission


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
    """Content management for Announcements and FAQs"""
    TYPE_CHOICES = [
        ('announcement', 'Announcement'),
        ('faq', 'FAQ'),
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
