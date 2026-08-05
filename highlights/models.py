from django.conf import settings
from django.db import models

# Per-type upload size caps (MB) — enforced in the upload view.
MAX_MB = {'image': 5, 'video': 250, 'ppt': 25, 'pdf': 25, 'doc': 5}

# Map file extension -> media_type used for validation + display.
EXT_TYPE = {
    'jpg': 'image', 'jpeg': 'image', 'png': 'image', 'gif': 'image', 'webp': 'image', 'heic': 'image',
    'mp4': 'video', 'mov': 'video', 'avi': 'video', 'mkv': 'video', 'webm': 'video',
    'ppt': 'ppt', 'pptx': 'ppt',
    'pdf': 'pdf',
    'doc': 'doc', 'docx': 'doc',
}


class IFTxHighlight(models.Model):
    """An IFTx activity/event write-up uploaded by a school/teacher."""

    school = models.ForeignKey(
        'students.School', on_delete=models.CASCADE, related_name='iftx_highlights', null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='iftx_highlights')

    title = models.CharField(max_length=300)
    event_date = models.DateField()
    summary = models.TextField(blank=True)

    is_reviewed = models.BooleanField(default=False)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-event_date', '-created_at']

    def __str__(self):
        return f'{self.title} ({self.event_date})'

    @property
    def school_name(self):
        return self.school.name if self.school else (
            self.created_by.get_full_name() or self.created_by.username if self.created_by else '—')


class HighlightMedia(models.Model):
    """A photo / video / document attached to a highlight."""

    highlight = models.ForeignKey(IFTxHighlight, on_delete=models.CASCADE, related_name='media')
    file = models.FileField(upload_to='iftx_highlights/%Y/%m/')
    media_type = models.CharField(max_length=10, default='image')  # image/video/ppt/pdf/doc
    original_name = models.CharField(max_length=255, blank=True)
    size_bytes = models.BigIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name or (self.file.name if self.file else 'media')

    @property
    def size_mb(self):
        return round((self.size_bytes or 0) / (1024 * 1024), 2)

    @property
    def is_image(self):
        return self.media_type == 'image'

    @property
    def is_video(self):
        return self.media_type == 'video'


class HighlightParticipant(models.Model):
    """A student who took part in the highlighted activity (captured for admin)."""

    highlight = models.ForeignKey(IFTxHighlight, on_delete=models.CASCADE, related_name='participants')
    student_name = models.CharField(max_length=200)
    grade = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.student_name
