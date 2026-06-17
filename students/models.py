from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Student(models.Model):
    """Student profile linked to Django User model"""
    GENDER_CHOICES = [('male', 'Male'), ('female', 'Female'), ('other', 'Other')]
    BOARD_CHOICES = [('CBSE', 'CBSE'), ('ICSE', 'ICSE'), ('SSC', 'SSC'), ('IB', 'IB'), ('IGCSE', 'IGCSE')]
    STREAM_CHOICES = [('science', 'Science'), ('commerce', 'Commerce'), ('arts', 'Arts/Humanities'), ('na', 'Not Applicable')]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField(max_length=50, unique=True, blank=True)
    school = models.ForeignKey('School', on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    school_name = models.CharField(max_length=200)  # kept for backward compat
    school_branch = models.CharField(max_length=200, blank=True)

    # Personal
    middle_name = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=100, blank=True, default='Indian')

    # Academic
    grade = models.CharField(max_length=20)
    division = models.CharField(max_length=10, blank=True)
    roll_number = models.CharField(max_length=50, blank=True)
    academic_year = models.CharField(max_length=20, blank=True)
    school_board = models.CharField(max_length=10, choices=BOARD_CHOICES, blank=True)
    stream = models.CharField(max_length=20, choices=STREAM_CHOICES, blank=True)

    # Contact
    phone = models.CharField(max_length=15, blank=True)  # student mobile
    parent_mobile = models.CharField(max_length=15, blank=True)
    parent_email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pin_code = models.CharField(max_length=10, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def school_display_name(self):
        return self.school.name if self.school else self.school_name

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.school_display_name}"

    class Meta:
        ordering = ['-created_at']


class School(models.Model):
    """School information model"""
    BOARD_CHOICES = [
        ('CBSE', 'CBSE'),
        ('ICSE', 'ICSE'),
        ('SSC', 'SSC'),
        ('IB', 'IB'),
        ('IGCSE', 'IGCSE'),
        ('Other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('inactive', 'Inactive'),
        ('active', 'Active'),
    ]

    SCHOOL_TYPE_CHOICES = [
        ('private', 'Private'),
        ('government', 'Government'),
        ('aided', 'Aided'),
        ('other', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='school_profile')
    name = models.CharField(max_length=300)
    branch = models.CharField(max_length=200, blank=True)
    board = models.CharField(max_length=10, choices=BOARD_CHOICES, blank=True)
    affiliation_number = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pin_code = models.CharField(max_length=10, blank=True)
    country = models.CharField(max_length=100, blank=True, default='India')
    principal_name = models.CharField(max_length=200, blank=True)
    principal_email = models.EmailField(blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=15, blank=True)
    website = models.URLField(blank=True)
    established_year = models.IntegerField(null=True, blank=True)
    total_students = models.IntegerField(null=True, blank=True)
    school_type = models.CharField(max_length=20, choices=SCHOOL_TYPE_CHOICES, blank=True)
    medium = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


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

    # Competition Track
    TRACK_CHOICES = [
        ('sustainable-energy', 'Sustainable Energy'),
        ('healthcare', 'Healthcare'),
        ('education', 'Education'),
        ('fintech', 'FinTech'),
        ('agriculture', 'Agriculture'),
        ('smart-cities', 'Smart Cities'),
    ]
    competition_track = models.CharField(max_length=30, choices=TRACK_CHOICES, blank=True)

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




class Team(models.Model):
    """Standalone team model - max 3 members"""
    TRACK_CHOICES = [
        ('sustainable-energy', 'Sustainable Energy'),
        ('healthcare', 'Healthcare'),
        ('education', 'Education'),
        ('fintech', 'FinTech'),
        ('agriculture', 'Agriculture'),
        ('smart-cities', 'Smart Cities'),
    ]

    name = models.CharField(max_length=100)
    tagline = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    track = models.CharField(max_length=30, choices=TRACK_CHOICES, blank=True)
    team_code = models.CharField(max_length=10, unique=True)
    leader = models.OneToOneField(User, on_delete=models.CASCADE, related_name='led_team')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def member_count(self):
        return self.memberships.count()

    @property
    def slots_available(self):
        return max(0, 3 - self.member_count)

    @property
    def is_full(self):
        return self.member_count >= 3

    def __str__(self):
        return f"{self.name} ({self.team_code})"

    class Meta:
        ordering = ['-created_at']


class TeamMembership(models.Model):
    """Team membership - links students to teams"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending', 'Pending'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='memberships')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True, related_name='team_memberships')
    email = models.EmailField(blank=True)
    role = models.CharField(max_length=20, default='member')  # 'leader' or 'member'
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    joined_at = models.DateTimeField(auto_now_add=True)

    @property
    def display_name(self):
        """Name for display - full name if active, email-derived if pending."""
        if self.student:
            return self.student.user.get_full_name() or self.student.user.username
        if self.email:
            local = self.email.split('@')[0]
            return local.replace('.', ' ').replace('_', ' ').title()
        return 'Unknown'

    def __str__(self):
        if self.student:
            return f"{self.student} in {self.team.name}"
        return f"{self.email} (pending) in {self.team.name}"

    class Meta:
        ordering = ['role', 'joined_at']


class TeamMember(models.Model):
    """Legacy team members for idea submission (kept for backward compat)"""
    ROLE_CHOICES = [
        ('leader', 'Team Leader'),
        ('member', 'Member'),
    ]
    submission = models.ForeignKey(IdeaSubmission, on_delete=models.CASCADE, related_name='team_members')
    name = models.CharField(max_length=200)
    grade = models.CharField(max_length=20, blank=True)
    school_name = models.CharField(max_length=200, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.get_role_display()}) — {self.submission}"

    class Meta:
        ordering = ['role', 'name']


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


class IdeaSuggestion(models.Model):
    """Suggestion/PR from team member to edit the idea. Leader approves/rejects."""
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    submission = models.ForeignKey(IdeaSubmission, on_delete=models.CASCADE, related_name='suggestions')
    suggested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='idea_suggestions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    message = models.TextField(blank=True, help_text="What changed and why")
    reject_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_suggestions')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Store suggested changes as JSON — field_name: new_value
    changes = models.JSONField(default=dict, help_text="Dict of field_name: new_value")

    @property
    def changed_fields_display(self):
        """Human-readable list of changed fields."""
        labels = {
            'q1_target_group': 'Q1 - Target Group & Struggle',
            'q2_exact_problem': 'Q2 - Exact Problem',
            'q3_solution_simple': 'Q3 - Solution',
            'q4_differentiation': 'Q4 - Differentiation',
            'q5_build_steps': 'Q5 - Build Steps',
            'q6_resources': 'Q6 - Resources',
            'q7_positive_change': 'Q7 - Positive Change',
            'q8_challenges': 'Q8 - Challenges',
            'q9_team_fit': 'Q9 - Team Fit',
            'q10_feedback': 'Q10 - Feedback',
            'q11_creative_element': 'Q11 - Creative Element',
            'q12_pitch': 'Q12 - Pitch',
            'title': 'Project Title',
        }
        return [labels.get(f, f) for f in self.changes.keys()]

    def apply_changes(self):
        """Merge approved changes into the submission."""
        for field, value in self.changes.items():
            if hasattr(self.submission, field):
                setattr(self.submission, field, value)
        self.submission.save()

    def __str__(self):
        return f"Suggestion by {self.suggested_by.get_full_name()} on {self.submission} ({self.status})"

    class Meta:
        ordering = ['-created_at']


class Notification(models.Model):
    """Student notifications"""
    TYPE_CHOICES = [
        ('team', 'Team'),
        ('submission', 'Submission'),
        ('announcement', 'Announcement'),
        ('system', 'System'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='system')
    title = models.CharField(max_length=300)
    message = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='notifications')  # Material icon name
    is_read = models.BooleanField(default=False)
    action_url = models.CharField(max_length=500, blank=True)  # optional link
    action_label = models.CharField(max_length=100, blank=True)  # button text
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} \u2192 {self.user.username}"

    class Meta:
        ordering = ['-created_at']
