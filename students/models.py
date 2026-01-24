from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Student(models.Model):
    """Student profile linked to Django User model"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField(max_length=50, unique=True, blank=True)
    school_name = models.CharField(max_length=200)
    grade = models.CharField(max_length=20)
    phone = models.CharField(max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.school_name}"
    
    class Meta:
        ordering = ['-created_at']


class IdeaSubmission(models.Model):
    """Main idea submission model"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('evaluated', 'Evaluated'),
        ('reviewed', 'Reviewed'),
    ]
    
    CATEGORY_CHOICES = [
        ('edtech', 'EdTech'),
        ('sustainability', 'Sustainability'),
        ('health', 'Health & Wellness'),
        ('fintech', 'FinTech'),
        ('social_impact', 'Social Impact'),
        ('agriculture', 'Agriculture'),
        ('technology', 'Technology'),
        ('entertainment', 'Entertainment'),
        ('other', 'Other'),
    ]
    
    IDEA_STAGE_CHOICES = [
        ('idea', 'Idea'),
        ('concept_prototype', 'Concept Prototype'),
        ('working_prototype', 'Working Prototype'),
        ('running_business', 'Running Business Idea'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='submissions')
    
    # Question 1: Problem Definition
    problem_definition = models.TextField(
        blank=True, default='',
        help_text="It's always better to define the problem before we attempt to solve it. Be précised in articulating it."
    )
    
    # Question 2: Detailed Problem Description
    problem_description = models.TextField(
        blank=True, default='',
        help_text="Give us a detailed description of the problem."
    )
    
    # Question 3: Target User Group
    target_user_group = models.TextField(
        blank=True, default='',
        help_text="Describe the 'user' group whose problem you are attempting to solve?"
    )
    
    # Question 4: Problem Urgency
    problem_urgency = models.TextField(
        blank=True, default='',
        help_text="Why do you believe that this problem is critical and needs an urgent solution?"
    )
    
    # Question 5: Solution
    solution = models.TextField(
        blank=True, default='',
        help_text="What is your solution?"
    )
    
    # Question 6: Solution Benefits
    solution_benefits = models.TextField(
        blank=True, default='',
        help_text="How your solution gives a distinct benefit to users or reduce their pain?"
    )
    
    # Question 7: Why Best Equipped
    why_best_equipped = models.TextField(
        blank=True, default='',
        help_text="Why do you think you are the best equipped to offer this solution?"
    )
    
    # Question 8: Idea Stage (dropdown)
    idea_stage = models.CharField(
        max_length=30,
        choices=IDEA_STAGE_CHOICES,
        default='idea',
        help_text="Mention the stage of your idea at this moment"
    )
    
    # Legacy fields for backward compatibility (kept for existing data)
    title = models.CharField(max_length=300, blank=True, help_text="[Legacy] Idea title")
    problem_statement = models.TextField(blank=True, help_text="[Legacy] Problem statement")
    proposed_solution = models.TextField(blank=True, help_text="[Legacy] Proposed solution")
    innovation_uniqueness = models.TextField(blank=True, help_text="[Legacy] Innovation uniqueness")
    feasibility_execution = models.TextField(blank=True, help_text="[Legacy] Feasibility execution")
    impact_usefulness = models.TextField(blank=True, help_text="[Legacy] Impact usefulness")
    description = models.TextField(blank=True, help_text="[Legacy] Detailed description of your idea")
    target_audience = models.TextField(blank=True, help_text="[Legacy] Who will benefit from your idea?")
    innovation_aspect = models.TextField(blank=True, help_text="[Legacy] What makes your idea innovative?")
    implementation_plan = models.TextField(blank=True, help_text="[Legacy] How do you plan to implement this idea?")
    impact_assessment = models.TextField(blank=True, help_text="[Legacy] What impact will your idea have?")
    
    # AI-suggested category (can be overridden by admin)
    ai_suggested_category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, blank=True)
    final_category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, blank=True)
    
    # Status and Metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # AI Processing
    ai_processed = models.BooleanField(default=False)
    ai_processing_error = models.TextField(blank=True)
    
    def save(self, *args, **kwargs):
        if self.status == 'submitted' and not self.submitted_at:
            self.submitted_at = timezone.now()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.title} - {self.student.user.username}"
    
    class Meta:
        ordering = ['-submitted_at', '-created_at']
        indexes = [
            models.Index(fields=['status', '-submitted_at']),
            models.Index(fields=['student', '-created_at']),
        ]




class UploadedFile(models.Model):
    """Files uploaded with submission"""
    FILE_TYPE_CHOICES = [
        ('document', 'Document/PPT'),
        ('image', 'Image'),
        ('video', 'Video'),
    ]
    
    submission = models.ForeignKey(IdeaSubmission, on_delete=models.CASCADE, related_name='uploaded_files')
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES)
    file = models.FileField(upload_to='submissions/%Y/%m/%d/')
    original_filename = models.CharField(max_length=255)
    file_size = models.IntegerField(help_text="File size in bytes")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Extracted text (for AI processing)
    extracted_text = models.TextField(blank=True, help_text="Text extracted from file for AI analysis")
    
    def __str__(self):
        return f"{self.original_filename} ({self.file_type})"
    
    class Meta:
        ordering = ['uploaded_at']
