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


class AIEvaluation(models.Model):
    """AI-generated evaluation scores using 10-parameter jury rubric (50 point scale)"""
    
    CONFIDENCE_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    
    submission = models.OneToOneField(IdeaSubmission, on_delete=models.CASCADE, related_name='ai_evaluation')
    
    # ===== IDEA PARAMETERS (5 params, 0-5 scale each, 0 = incoherent) =====
    uniqueness_score = models.IntegerField(default=0, help_text="Uniqueness (0-5, 0=incoherent)")
    ease_of_implementation_score = models.IntegerField(default=0, help_text="Ease of Implementation (0-5, 0=incoherent)")
    scalable_score = models.IntegerField(default=0, help_text="Scalable (0-5, 0=incoherent)")
    impactful_score = models.IntegerField(default=0, help_text="Impactful (0-5, 0=incoherent)")
    sustainable_score = models.IntegerField(default=0, help_text="Sustainable (0-5, 0=incoherent)")

    # ===== TEAM PARAMETERS (5 params, 0-5 scale each, 0 = incoherent) =====
    conceptual_clarity_score = models.IntegerField(default=0, help_text="Conceptual Clarity & Comprehensiveness (0-5, 0=incoherent)")
    empathy_score = models.IntegerField(default=0, help_text="Empathy (0-5, 0=incoherent)")
    creativity_score = models.IntegerField(default=0, help_text="Creativity (0-5, 0=incoherent)")
    communication_score = models.IntegerField(default=0, help_text="Communication (0-5, 0=incoherent)")
    flexible_thinking_score = models.IntegerField(default=0, help_text="Flexible Thinking (0-5, 0=incoherent)")
    
    # Final calculated score (max 50)
    final_score = models.IntegerField(default=0, help_text="Total score out of 50")

    # Coherence check - do all fields relate to the same idea?
    is_coherent = models.BooleanField(default=True, help_text="Do all submission fields relate to the same idea?")

    # Content mismatch - do attachments match the idea?
    MISMATCH_SEVERITY_CHOICES = [
        ('none', 'None'),
        ('minor', 'Minor Mismatch'),
        ('severe', 'Severe Mismatch'),
        ('missing', 'No Attachments'),
    ]
    attachment_mismatch = models.BooleanField(default=False, help_text="Are attachments mismatched with idea?")
    mismatch_severity = models.CharField(max_length=10, choices=MISMATCH_SEVERITY_CHOICES, default='none')
    mismatch_penalty = models.IntegerField(default=0, help_text="Marks deducted for attachment mismatch")
    mismatch_reasons = models.JSONField(default=list, blank=True, help_text="Reasons for attachment mismatch")
    attachment_summaries = models.JSONField(default=dict, blank=True, help_text="Per-file analysis: summaries, relevance, missing types")

    # Ranking position
    rank = models.IntegerField(null=True, blank=True, help_text="Position in overall ranking")
    is_top_400 = models.BooleanField(default=False, help_text="Selected in Top 400")
    
    # ===== JUSTIFICATIONS =====
    uniqueness_justification = models.TextField(blank=True)
    ease_of_implementation_justification = models.TextField(blank=True)
    scalable_justification = models.TextField(blank=True)
    impactful_justification = models.TextField(blank=True)
    sustainable_justification = models.TextField(blank=True)
    conceptual_clarity_justification = models.TextField(blank=True)
    empathy_justification = models.TextField(blank=True)
    creativity_justification = models.TextField(blank=True)
    communication_justification = models.TextField(blank=True)
    flexible_thinking_justification = models.TextField(blank=True)
    overall_justification = models.TextField(blank=True, help_text="Overall evaluation summary")
    
    # Confidence level
    confidence_level = models.CharField(
        max_length=10, 
        choices=CONFIDENCE_CHOICES, 
        default='medium',
        help_text="AI confidence in this evaluation"
    )
    
    # Metadata
    model_used = models.CharField(max_length=100, default='anthropic/claude-3.5-sonnet')
    tokens_used = models.IntegerField(default=0)
    processing_time = models.FloatField(default=0, help_text="Processing time in seconds")
    evaluated_at = models.DateTimeField(auto_now_add=True)
    
    # Raw AI response (for debugging)
    raw_response = models.TextField(blank=True)
    
    def save(self, *args, **kwargs):
        # Calculate total score from all 10 parameters (each 0-5, max 50)
        raw_score = (
            self.uniqueness_score +
            self.ease_of_implementation_score +
            self.scalable_score +
            self.impactful_score +
            self.sustainable_score +
            self.conceptual_clarity_score +
            self.empathy_score +
            self.creativity_score +
            self.communication_score +
            self.flexible_thinking_score
        )
        # Apply mismatch penalty (never go below 0)
        self.final_score = max(0, raw_score - self.mismatch_penalty)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Evaluation for: {self.submission.title} (Score: {self.final_score}/50)"
    
    class Meta:
        verbose_name_plural = "AI Evaluations"
        ordering = ['-final_score', '-uniqueness_score', '-impactful_score']
        indexes = [
            models.Index(fields=['-final_score']),
            models.Index(fields=['rank']),
        ]
