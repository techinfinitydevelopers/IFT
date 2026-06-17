from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('jury', 'Evaluator'),
        ('school', 'School'),
        ('superadmin', 'Super Admin'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def is_student(self):
        return self.role == 'student'

    @property
    def is_jury(self):
        return self.role == 'jury'

    @property
    def is_school(self):
        return self.role == 'school'

    @property
    def is_superadmin(self):
        return self.role == 'superadmin'


class JuryProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='jury_profile')

    # Professional
    designation = models.CharField(max_length=200, blank=True)
    organization = models.CharField(max_length=200, blank=True)
    industry = models.CharField(max_length=100, blank=True)
    experience = models.CharField(max_length=20, blank=True)
    qualification = models.CharField(max_length=100, blank=True)
    linkedin_url = models.URLField(blank=True)
    bio = models.TextField(blank=True)

    # Expertise
    expertise_area = models.CharField(max_length=200, blank=True)
    secondary_expertise = models.CharField(max_length=200, blank=True)
    jury_role = models.CharField(max_length=50, blank=True)
    evaluation_season = models.CharField(max_length=50, blank=True)
    max_ideas_per_week = models.CharField(max_length=20, blank=True)
    previous_jury_exp = models.CharField(max_length=50, blank=True)
    evaluation_note = models.TextField(blank=True)

    # Contact
    phone = models.CharField(max_length=15, blank=True)
    alternate_phone = models.CharField(max_length=15, blank=True)
    alternate_email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    pin_code = models.CharField(max_length=10, blank=True)
    preferred_contact = models.CharField(max_length=20, blank=True)

    # Personal
    gender = models.CharField(max_length=10, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=100, blank=True, default='Indian')
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)

    # Availability
    available_from = models.DateField(null=True, blank=True)
    available_to = models.DateField(null=True, blank=True)
    preferred_time = models.CharField(max_length=50, blank=True)
    evaluation_mode = models.CharField(max_length=20, blank=True)
    willing_to_mentor = models.CharField(max_length=10, blank=True)
    willing_to_bootcamp = models.CharField(max_length=50, blank=True)
    additional_notes = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Evaluator: {self.user.get_full_name() or self.user.username}"
