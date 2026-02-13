from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from students.models import Student, IdeaSubmission
from ai_assistant.models import AIEvaluation


def make_student(username='student1', school='Test School', grade='10'):
    user = User.objects.create_user(
        username=username, password='pass123',
        first_name='Rahul', last_name='Sharma', email=f'{username}@test.com'
    )
    return Student.objects.create(
        user=user, student_id=f'IFT{user.id:05d}',
        school_name=school, grade=grade
    )


def make_admin(username='admin1'):
    return User.objects.create_superuser(
        username=username, password='admin123', email=f'{username}@admin.com'
    )


def make_submission(student, title='', q3='Test solution with enough characters here', q2='Test problem with enough chars here', status='submitted'):
    return IdeaSubmission.objects.create(
        student=student,
        title=title,
        q3_solution_simple=q3,
        q2_exact_problem=q2,
        q1_target_group='Students in urban schools',
        q4_differentiation='Unlike others we use AI for personalized learning',
        q5_build_steps='Step 1 build prototype, Step 2 test with users',
        q6_resources='We need a developer and Rs 20K budget available',
        q7_positive_change='Students will learn faster and enjoy studying more',
        q8_challenges='Internet access issues, we will build offline mode',
        q9_team_fit='Team won science fair and has coding experience',
        q10_feedback='Users said UI was confusing so we redesigned it',
        q11_creative_element='AI adapts difficulty based on student mood detection',
        q12_pitch='Imagine an app that knows exactly how you learn best',
        status=status,
        submitted_at=timezone.now(),
    )


class AdminDashboardTitleTest(TestCase):
    """Test: Admin dashboard should show meaningful titles, never 'Untitled' for v3 submissions."""

    def setUp(self):
        self.admin_user = make_admin()
        self.student = make_student()
        self.client = Client()
        self.client.login(username='admin1', password='admin123')

    def test_title_shown_when_set(self):
        """If title is set, it should show in dashboard."""
        make_submission(self.student, title='Smart Water Monitor')
        resp = self.client.get('/jury/')
        self.assertEqual(resp.status_code, 200)
        # Check that the title appears in context
        submissions = resp.context['submissions']
        self.assertEqual(len(submissions), 1)
        self.assertIn('Smart Water Monitor', submissions[0]['title'])

    def test_fallback_to_q3_when_no_title(self):
        """If title is empty, should fallback to Q3 (solution)."""
        make_submission(self.student, title='', q3='AR Math App that makes learning fun and interactive')
        resp = self.client.get('/jury/')
        submissions = resp.context['submissions']
        self.assertIn('AR Math App', submissions[0]['title'])
        self.assertNotIn('Untitled', submissions[0]['title'])

    def test_fallback_to_q2_when_no_title_no_q3(self):
        """If both title and Q3 are empty, fallback to Q2."""
        make_submission(self.student, title='', q3='', q2='Math learning is boring for students in grade 6 to 10')
        resp = self.client.get('/jury/')
        submissions = resp.context['submissions']
        self.assertIn('Math learning', submissions[0]['title'])
        self.assertNotIn('Untitled', submissions[0]['title'])

    def test_untitled_only_when_all_empty(self):
        """'Untitled' should only appear when title, Q3, Q2, and problem_definition are all empty."""
        sub = make_submission(self.student, title='', q3='', q2='')
        sub.problem_definition = ''
        sub.save()
        resp = self.client.get('/jury/')
        submissions = resp.context['submissions']
        self.assertEqual(submissions[0]['title'], 'Untitled')

    def test_title_truncated_at_80_chars(self):
        """Long titles should be truncated at 80 chars with '...'."""
        long_q3 = 'A' * 100
        make_submission(self.student, title='', q3=long_q3)
        resp = self.client.get('/jury/')
        submissions = resp.context['submissions']
        self.assertLessEqual(len(submissions[0]['title']), 83)  # 80 + '...'


class RankingsTitleTest(TestCase):
    """Test: Rankings should handle empty titles gracefully."""

    def setUp(self):
        self.admin_user = make_admin('admin2')
        self.student = make_student('student2')
        self.client = Client()
        self.client.login(username='admin2', password='admin123')

    def test_ranking_with_title(self):
        """Rankings should show title when available."""
        sub = make_submission(self.student, title='Smart Water Monitor')
        AIEvaluation.objects.create(
            submission=sub, uniqueness_score=7, ease_of_implementation_score=6,
            feasibility_score=7, impactful_score=8, sustainable_score=6,
            conceptual_clarity_score=7, empathy_score=6, creativity_score=7,
            communication_score=7, flexible_thinking_score=5,
            is_top_400=True, rank=1
        )
        resp = self.client.get('/jury/rankings/')
        self.assertEqual(resp.status_code, 200)

    def test_ranking_without_title_uses_fallback(self):
        """Rankings should use Q3/Q2 fallback when title is empty."""
        sub = make_submission(self.student, title='', q3='Solar powered water purifier for villages')
        sub.status = 'evaluated'
        sub.save()
        AIEvaluation.objects.create(
            submission=sub, uniqueness_score=8, ease_of_implementation_score=7,
            feasibility_score=7, impactful_score=9, sustainable_score=7,
            conceptual_clarity_score=8, empathy_score=7, creativity_score=8,
            communication_score=7, flexible_thinking_score=6,
        )
        resp = self.client.get('/jury/rankings/')
        self.assertEqual(resp.status_code, 200)
        # Should not crash even with empty title
        top_400 = resp.context['top_400_evaluations']
        normal = resp.context['normal_evaluations']
        all_evals = top_400 + normal
        for ev in all_evals:
            self.assertNotEqual(ev['title'], '')
            self.assertIsNotNone(ev['title'])
