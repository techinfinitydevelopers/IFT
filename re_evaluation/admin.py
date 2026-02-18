from django.contrib import admin
from .models import LightSubmission, LightSubmissionFile, MentorScore

admin.site.register(LightSubmission)
admin.site.register(LightSubmissionFile)
admin.site.register(MentorScore)
