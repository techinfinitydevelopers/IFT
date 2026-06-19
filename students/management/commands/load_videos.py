from django.core.management.base import BaseCommand
from students.models import LearningVideo

class Command(BaseCommand):
    help = 'Load initial learning videos'

    def handle(self, *args, **options):
        videos = [
            {'title': 'IFT Module 1: Introduction', 'youtube_url': 'https://www.youtube.com/watch?v=ZK07eFitOy4', 'youtube_id': 'ZK07eFitOy4', 'order': 1},
            {'title': 'IFT Module 2: Problem Identification', 'youtube_url': 'https://www.youtube.com/watch?v=pFJbtqsoU2g', 'youtube_id': 'pFJbtqsoU2g', 'order': 2},
            {'title': 'IFT Module 3: Solution Design', 'youtube_url': 'https://www.youtube.com/watch?v=vJQcBfaCirs', 'youtube_id': 'vJQcBfaCirs', 'order': 3},
            {'title': 'IFT Module 4: Business Model', 'youtube_url': 'https://www.youtube.com/watch?v=uT7eAdZcTpY', 'youtube_id': 'uT7eAdZcTpY', 'order': 4},
            {'title': 'IFT Module 5: Impact Assessment', 'youtube_url': 'https://www.youtube.com/watch?v=dt9lm0UW5qE', 'youtube_id': 'dt9lm0UW5qE', 'order': 5},
            {'title': 'IFT Module 6: Team Building', 'youtube_url': 'https://www.youtube.com/watch?v=LlRsO_D-zM4', 'youtube_id': 'LlRsO_D-zM4', 'order': 6},
            {'title': 'IFT Module 7: Pitch Preparation', 'youtube_url': 'https://www.youtube.com/watch?v=ayC_GRXYlgc', 'youtube_id': 'ayC_GRXYlgc', 'order': 7},
            {'title': 'IFT Module 8: Submission Guide', 'youtube_url': 'https://www.youtube.com/watch?v=8U2K_kUDV3k', 'youtube_id': '8U2K_kUDV3k', 'order': 8},
        ]
        for v in videos:
            LearningVideo.objects.update_or_create(
                youtube_id=v['youtube_id'],
                defaults=v
            )
            self.stdout.write(f"  ✓ {v['title']}")
        self.stdout.write(self.style.SUCCESS(f'Loaded {len(videos)} videos'))
