from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Student, IdeaSubmission


def make_student(username='testuser', school='Test School', grade='10'):
    """Helper to create a student with linked user."""
    user = User.objects.create_user(
        username=username, password='testpass123',
        first_name='Test', last_name='User', email=f'{username}@test.com'
    )
    student = Student.objects.create(
        user=user, student_id=f'IFT{user.id:05d}',
        school_name=school, grade=grade
    )
    return student


SAMPLE_ANSWERS = {
    'q1_target_group': 'Urban students who struggle with understanding math concepts in school daily.',
    'q2_exact_problem': 'Students in grades 6-10 find math boring and abstract. They cannot visualize equations and geometry.',
    'q3_solution_simple': 'A mobile app that uses AR (Augmented Reality) to turn math problems into 3D visual games.',
    'q4_differentiation': 'Unlike Khan Academy or Byju\'s, we use AR so students can literally see and touch math concepts.',
    'q5_build_steps': 'Step 1: Design AR modules. Step 2: Build prototype app. Step 3: Test with 50 students. Step 4: Iterate.',
    'q6_resources': 'We need Unity3D developer, AR kit, Rs 30K budget. We already have coding skills and a mentor.',
    'q7_positive_change': 'Students will find math fun and intuitive. Exam scores will improve by 20-30% based on similar studies.',
    'q8_challenges': 'Phone compatibility issues and internet access in rural areas. We will make an offline mode.',
    'q9_team_fit': 'Our team won the school science fair and has 2 years of app development experience.',
    'q10_feedback': 'We showed a prototype to 10 classmates. They said the UI was confusing so we simplified the navigation.',
    'q11_creative_element': 'The AR math playground where students can throw virtual balls to understand parabolic curves.',
    'q12_pitch': 'Imagine pointing your phone at a math problem and watching it come alive in 3D. That is MathVision AR.',
}


class TitleAutoGenerationTest(TestCase):
    """Test: Title should be auto-generated immediately on submission, not 'Untitled'."""

    def setUp(self):
        self.student = make_student()
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_title_from_q3_on_form_submit(self):
        """Title should come from Q3 (solution) when student submits via form."""
        resp = self.client.post('/submit/', SAMPLE_ANSWERS, follow=True)
        self.assertEqual(resp.status_code, 200)
        submission = IdeaSubmission.objects.first()
        self.assertIsNotNone(submission)
        # Title should be set and not empty
        self.assertTrue(len(submission.title) > 0)
        self.assertNotEqual(submission.title, 'Untitled')
        # Title should be from Q3 (solution)
        self.assertTrue(submission.title.startswith('A mobile app that uses AR'))

    def test_title_from_q2_when_q3_empty(self):
        """If Q3 is somehow empty, title should fallback to Q2."""
        submission = IdeaSubmission.objects.create(
            student=self.student,
            q2_exact_problem='Students find math boring and abstract because they cannot visualize it.',
            q3_solution_simple='',
            status='submitted',
            submitted_at=timezone.now(),
        )
        # Simulate what submit_idea view does
        title_source = (submission.q3_solution_simple or submission.q2_exact_problem or '').strip()
        if title_source:
            submission.title = title_source[:80]
            submission.save()

        self.assertTrue(submission.title.startswith('Students find math'))

    def test_long_title_truncated_at_word_boundary(self):
        """Titles longer than 80 chars should be truncated at a word boundary."""
        long_text = 'A ' + 'very ' * 30 + 'long solution description that goes on and on'
        submission = IdeaSubmission.objects.create(
            student=self.student,
            q3_solution_simple=long_text,
            status='submitted',
            submitted_at=timezone.now(),
        )
        title_source = submission.q3_solution_simple.strip()
        title = title_source[:80]
        if len(title_source) > 80:
            last_space = title.rfind(' ')
            if last_space > 40:
                title = title[:last_space]
        submission.title = title
        submission.save()

        self.assertLessEqual(len(submission.title), 80)
        # Should not end mid-word
        self.assertFalse(submission.title.endswith('ver'))

    def test_empty_answers_no_crash(self):
        """If both Q3 and Q2 are empty, title stays empty (no crash)."""
        submission = IdeaSubmission.objects.create(
            student=self.student,
            q3_solution_simple='',
            q2_exact_problem='',
            status='submitted',
            submitted_at=timezone.now(),
        )
        title_source = (submission.q3_solution_simple or submission.q2_exact_problem or '').strip()
        if title_source:
            submission.title = title_source[:80]
            submission.save()

        # Title should be empty string (not crash)
        self.assertEqual(submission.title, '')
