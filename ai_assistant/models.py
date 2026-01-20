from django.db import models
from students.models import IdeaSubmission


class AISummary(models.Model):
    """AI-generated summary and analysis for idea submissions"""
    submission = models.OneToOneField(IdeaSubmission, on_delete=models.CASCADE, related_name='ai_summary')
    
    # AI-generated content
    summary = models.TextField(help_text="2-3 sentence neutral summary")
    suggested_tags = models.JSONField(default=list, help_text="AI-suggested category tags")
    
    # File content summaries (dict: filename -> summary)
    file_summaries = models.JSONField(default=dict, blank=True, help_text="Summaries of uploaded file contents")
    
    # Consistency check - does uploaded content match idea text?
    is_consistent = models.BooleanField(default=True, help_text="Do uploaded files match the idea description?")
    inconsistency_reasons = models.JSONField(default=list, blank=True, help_text="Reasons why content may be inconsistent")
    
    # Validation results
    is_complete = models.BooleanField(default=True)
    completeness_notes = models.TextField(blank=True, help_text="Notes about missing information")
    
    # Metadata
    model_used = models.CharField(max_length=100, default='deepseek/deepseek-chat')
    tokens_used = models.IntegerField(default=0)
    processing_time = models.FloatField(default=0, help_text="Processing time in seconds")
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Raw AI response (for debugging)
    raw_response = models.TextField(blank=True)
    
    def __str__(self):
        return f"AI Summary for: {self.submission.title}"
    
    class Meta:
        verbose_name_plural = "AI Summaries"
        ordering = ['-created_at']

