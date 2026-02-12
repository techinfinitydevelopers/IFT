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
        ('incoherent', 'Incoherent'),
    ]
    
    IDEA_STAGE_CHOICES = [
        ('idea', 'Idea'),
        ('concept_prototype', 'Concept Prototype'),
        ('working_prototype', 'Working Prototype'),
        ('running_business', 'Running Business Idea'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='submissions')
    
    # ===== v3 Questions (12 questions) =====
    q1_target_group = models.TextField(
        blank=True, default='',
        help_text="Describe the person/group you're trying to help. Who are they, what is their daily struggle?"
    )
    q2_exact_problem = models.TextField(
        blank=True, default='',
        help_text="What exact problem are they facing? When, where, and why does this problem matter?"
    )
    q3_solution_simple = models.TextField(
        blank=True, default='',
        help_text="What is your solution, explained simply as if talking to a 10-year-old?"
    )
    q4_differentiation = models.TextField(
        blank=True, default='',
        help_text="How is your solution different from what already exists?"
    )
    q5_build_steps = models.TextField(
        blank=True, default='',
        help_text="What are the key steps required to build and test your solution?"
    )
    q6_resources = models.TextField(
        blank=True, default='',
        help_text="What resources (skills, tools, money, tech, people) are required? Which do you already have?"
    )
    q7_positive_change = models.TextField(
        blank=True, default='',
        help_text="If your solution succeeds, what positive change will it create for users and society?"
    )
    q8_challenges = models.TextField(
        blank=True, default='',
        help_text="What challenges could come while building or using this idea? How will you deal with them?"
    )
    q9_team_fit = models.TextField(
        blank=True, default='',
        help_text="Why do you think your team is rightly placed to solve this problem?"
    )
    q10_feedback = models.TextField(
        blank=True, default='',
        help_text="Have you taken any user feedback? Describe one situation where your thinking changed after feedback."
    )
    q11_creative_element = models.TextField(
        blank=True, default='',
        help_text="What is the most creative or unexpected element in your solution, and why did you think of it?"
    )
    q12_pitch = models.TextField(
        blank=True, default='',
        help_text="If you had 60 seconds to convince someone to try or support your idea, what would you say?"
    )

    # ===== Legacy v2 Questions (kept for backward compatibility) =====
    problem_definition = models.TextField(
        blank=True, default='',
        help_text="[Legacy-v2] Problem definition"
    )
    problem_description = models.TextField(
        blank=True, default='',
        help_text="[Legacy-v2] Detailed problem description"
    )
    target_user_group = models.TextField(
        blank=True, default='',
        help_text="[Legacy-v2] Target user group"
    )
    problem_urgency = models.TextField(
        blank=True, default='',
        help_text="[Legacy-v2] Problem urgency"
    )
    solution = models.TextField(
        blank=True, default='',
        help_text="[Legacy-v2] Solution"
    )
    solution_benefits = models.TextField(
        blank=True, default='',
        help_text="[Legacy-v2] Solution benefits"
    )
    why_best_equipped = models.TextField(
        blank=True, default='',
        help_text="[Legacy-v2] Why best equipped"
    )
    idea_stage = models.CharField(
        max_length=30,
        choices=IDEA_STAGE_CHOICES,
        default='idea',
        help_text="[Legacy-v2] Idea stage"
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
