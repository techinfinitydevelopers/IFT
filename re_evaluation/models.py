from django.db import models
from django.utils import timezone


class LightSubmission(models.Model):
    """A simplified idea submission for re-evaluation comparison.
    Contains only project name, description, and attachments (no 12 questions).
    Completely separate from the main IdeaSubmission model."""

    project_name = models.CharField(max_length=300)
    idea_description = models.TextField(help_text="Short idea description from the re-evaluation sheet")
    industry = models.CharField(max_length=100, blank=True, default='')
    student_name = models.CharField(max_length=200, blank=True, default='')

    # AI Evaluation scores (0-10 each, max 100)
    uniqueness_score = models.IntegerField(default=0)
    ease_of_implementation_score = models.IntegerField(default=0)
    feasibility_score = models.IntegerField(default=0)
    impactful_score = models.IntegerField(default=0)
    sustainable_score = models.IntegerField(default=0)
    conceptual_clarity_score = models.IntegerField(default=0)
    empathy_score = models.IntegerField(default=0)
    creativity_score = models.IntegerField(default=0)
    communication_score = models.IntegerField(default=0)
    flexible_thinking_score = models.IntegerField(default=0)
    ai_total_score = models.IntegerField(default=0)

    # AI justifications
    uniqueness_justification = models.TextField(blank=True)
    ease_of_implementation_justification = models.TextField(blank=True)
    feasibility_justification = models.TextField(blank=True)
    impactful_justification = models.TextField(blank=True)
    sustainable_justification = models.TextField(blank=True)
    conceptual_clarity_justification = models.TextField(blank=True)
    empathy_justification = models.TextField(blank=True)
    creativity_justification = models.TextField(blank=True)
    communication_justification = models.TextField(blank=True)
    flexible_thinking_justification = models.TextField(blank=True)
    overall_justification = models.TextField(blank=True)

    # AI metadata
    ai_confidence = models.CharField(max_length=10, blank=True, default='')
    ai_model_used = models.CharField(max_length=100, blank=True, default='')
    ai_raw_response = models.TextField(blank=True)
    is_evaluated = models.BooleanField(default=False)
    evaluated_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.is_evaluated:
            self.ai_total_score = (
                self.uniqueness_score +
                self.ease_of_implementation_score +
                self.feasibility_score +
                self.impactful_score +
                self.sustainable_score +
                self.conceptual_clarity_score +
                self.empathy_score +
                self.creativity_score +
                self.communication_score +
                self.flexible_thinking_score
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.project_name} ({self.student_name})"

    class Meta:
        ordering = ['-created_at']


class LightSubmissionFile(models.Model):
    """Attachments for light submissions"""
    FILE_TYPE_CHOICES = [
        ('document', 'Document/PPT'),
        ('image', 'Image'),
        ('video', 'Video'),
    ]

    submission = models.ForeignKey(LightSubmission, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='re_evaluation/%Y/%m/%d/')
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES)
    original_filename = models.CharField(max_length=255)
    extracted_text = models.TextField(blank=True, help_text="Text extracted from document for AI analysis")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_filename


class MentorScore(models.Model):
    """Mentor's manual scores for comparison with AI"""

    submission = models.OneToOneField(LightSubmission, on_delete=models.CASCADE, related_name='mentor_score')
    mentor_name = models.CharField(max_length=200, blank=True, default='')

    # Mentor scores (0-10 each)
    uniqueness_score = models.IntegerField(default=0)
    ease_of_implementation_score = models.IntegerField(default=0)
    feasibility_score = models.IntegerField(default=0)
    impactful_score = models.IntegerField(default=0)
    sustainable_score = models.IntegerField(default=0)
    conceptual_clarity_score = models.IntegerField(default=0)
    empathy_score = models.IntegerField(default=0)
    creativity_score = models.IntegerField(default=0)
    communication_score = models.IntegerField(default=0)
    flexible_thinking_score = models.IntegerField(default=0)
    mentor_total_score = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.mentor_total_score = (
            self.uniqueness_score +
            self.ease_of_implementation_score +
            self.feasibility_score +
            self.impactful_score +
            self.sustainable_score +
            self.conceptual_clarity_score +
            self.empathy_score +
            self.creativity_score +
            self.communication_score +
            self.flexible_thinking_score
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Mentor score for {self.submission.project_name} by {self.mentor_name}"
