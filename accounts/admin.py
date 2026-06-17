from django.contrib import admin
from .models import UserProfile, JuryProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'created_at']
    list_filter = ['role']
    search_fields = ['user__username', 'user__email']


@admin.register(JuryProfile)
class JuryProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'expertise_area', 'organization', 'is_active']
    list_filter = ['is_active']
    search_fields = ['user__username', 'user__email']
