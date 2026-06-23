from django.contrib import admin
from .models import Student, IdeaSubmission, UploadedFile, TeamMember, LearningVideo, VideoProgress, School, Team, TeamMembership, IdeaSuggestion, Notification


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'user', 'school_name', 'grade', 'created_at')
    search_fields = ('student_id', 'user__username', 'user__email', 'school_name')
    list_filter = ('grade', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(IdeaSubmission)
class IdeaSubmissionAdmin(admin.ModelAdmin):
    list_display = ('title', 'student', 'status', 'final_category', 'submitted_at', 'ai_processed')
    search_fields = ('title', 'student__user__username')
    list_filter = ('status', 'final_category', 'ai_processed', 'submitted_at')
    readonly_fields = ('submitted_at', 'created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('student', 'title', 'status')
        }),
        ('V3 Questionnaire (12 Questions)', {
            'fields': (
                'q1_target_group', 'q2_exact_problem', 'q3_solution_simple',
                'q4_differentiation', 'q5_build_steps', 'q6_resources',
                'q7_positive_change', 'q8_challenges', 'q9_team_fit',
                'q10_feedback', 'q11_creative_element', 'q12_pitch',
            )
        }),
        ('Legacy V2 Fields', {
            'fields': (
                'problem_definition', 'problem_description', 'target_user_group',
                'problem_urgency', 'solution', 'solution_benefits',
                'why_best_equipped', 'idea_stage',
            ),
            'classes': ('collapse',)
        }),
        ('Categories', {
            'fields': ('ai_suggested_category', 'final_category')
        }),
        ('AI Processing', {
            'fields': ('ai_processed', 'ai_processing_error')
        }),
        ('Timestamps', {
            'fields': ('submitted_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'submission', 'file_type', 'file_size', 'uploaded_at')
    search_fields = ('original_filename', 'submission__title')
    list_filter = ('file_type', 'uploaded_at')
    readonly_fields = ('uploaded_at', 'file_size')


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'submission', 'role', 'grade', 'school_name')
    search_fields = ('name', 'submission__title')
    list_filter = ('role',)


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'board', 'city', 'state', 'status', 'is_active', 'created_at')
    search_fields = ('name', 'city', 'contact_email', 'principal_name')
    list_filter = ('board', 'status', 'is_active', 'state')


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'team_code', 'leader', 'created_at')
    search_fields = ('name', 'team_code')


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = ('team', 'student', 'role', 'status')
    list_filter = ('role', 'status')


@admin.register(IdeaSuggestion)
class IdeaSuggestionAdmin(admin.ModelAdmin):
    list_display = ('submission', 'suggested_by', 'field_name', 'status', 'created_at')
    list_filter = ('status',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read')


@admin.register(LearningVideo)
class LearningVideoAdmin(admin.ModelAdmin):
    list_display = ['title', 'order', 'is_mandatory', 'is_active']
    list_editable = ['order', 'is_mandatory', 'is_active']


@admin.register(VideoProgress)
class VideoProgressAdmin(admin.ModelAdmin):
    list_display = ['student', 'video', 'watched', 'watched_at']
    list_filter = ['watched', 'video']
