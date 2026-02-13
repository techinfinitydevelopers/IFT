from unittest.mock import patch, MagicMock
import json
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from students.models import Student, IdeaSubmission
from ai_assistant.models import AIEvaluation, AISummary
from ai_assistant.evaluator import (
    parse_evaluation_response,
    get_submission_questions,
    apply_coherence_penalties,
    evaluate_idea,
    update_rankings,
    COHERENCE_PENALTY_MAP,
)


def make_student(username='ai_test_user'):
    user = User.objects.create_user(
        username=username, password='pass123',
        first_name='Test', last_name='Student', email=f'{username}@test.com'
    )
    return Student.objects.create(
        user=user, student_id=f'IFT{user.id:05d}',
        school_name='Test School', grade='10'
    )


def make_submission(student, **kwargs):
    defaults = {
        'q1_target_group': 'Urban students struggling with math concepts daily in schools.',
        'q2_exact_problem': 'Students in grades 6-10 find math boring. They cannot visualize equations and geometry.',
        'q3_solution_simple': 'A mobile app using AR to turn math into 3D visual games students can interact with.',
        'q4_differentiation': 'Unlike Byju\'s or Khan Academy, we use AR so students can see and touch math.',
        'q5_build_steps': 'Step 1: Design AR modules. Step 2: Build prototype. Step 3: Test with 50 students.',
        'q6_resources': 'Need Unity3D dev, AR kit, Rs 30K. Already have coding skills and a mentor.',
        'q7_positive_change': 'Students find math fun and intuitive. Exam scores improve by 20-30%.',
        'q8_challenges': 'Phone compatibility and internet access. We will build an offline mode.',
        'q9_team_fit': 'Team won science fair, has 2 years of app development experience.',
        'q10_feedback': 'Showed prototype to 10 classmates. They said UI was confusing so we simplified.',
        'q11_creative_element': 'AR math playground where students throw virtual balls to understand parabolas.',
        'q12_pitch': 'Point your phone at a math problem and watch it come alive in 3D. That is MathVision.',
        'status': 'submitted',
        'submitted_at': timezone.now(),
    }
    defaults.update(kwargs)
    return IdeaSubmission.objects.create(student=student, **defaults)


# --- Fake AI response for mocking ---
FAKE_EVAL_RESPONSE = {
    'content': json.dumps({
        'parameter_scores': [
            {'parameter_name': 'Uniqueness', 'score': 7, 'reason': 'AR for math is moderately novel.'},
            {'parameter_name': 'Ease of Implementation', 'score': 6, 'reason': 'Clear steps but AR dev is complex.'},
            {'parameter_name': 'Feasibility', 'score': 6, 'reason': 'Resources partially available.'},
            {'parameter_name': 'Impact', 'score': 8, 'reason': 'Wide student base, clear benefit.'},
            {'parameter_name': 'Sustainability', 'score': 5, 'reason': 'Revenue model not clear.'},
            {'parameter_name': 'Conceptual Clarity', 'score': 7, 'reason': 'Problem-solution link is clear.'},
            {'parameter_name': 'Empathy', 'score': 6, 'reason': 'Understands student struggles.'},
            {'parameter_name': 'Creativity', 'score': 7, 'reason': 'AR playground is creative.'},
            {'parameter_name': 'Communication', 'score': 7, 'reason': 'Well-structured pitch.'},
            {'parameter_name': 'Flexible Thinking', 'score': 5, 'reason': 'Some feedback adaptation shown.'},
        ],
        'total_score': 64,
        'overall_justification': 'Solid idea with AR novelty but needs clearer revenue model.',
        'confidence': 'medium'
    }),
    'model': 'anthropic/claude-3.5-sonnet',
    'tokens': 1500,
    'time': 15.0,
    'raw_response': '{}'
}

FAKE_COHERENCE_RESPONSE = {
    'content': json.dumps({
        'checks': [
            {'name': 'User-Problem Fit', 'passed': True, 'reason': 'Target matches problem.'},
            {'name': 'Problem-Solution Fit', 'passed': True, 'reason': 'Solution addresses problem.'},
            {'name': 'Difference Validity', 'passed': True, 'reason': 'Difference is visible.'},
            {'name': 'Execution Reality', 'passed': True, 'reason': 'Steps match solution.'},
            {'name': 'Resources Alignment', 'passed': True, 'reason': 'Resources support steps.'},
            {'name': 'Risk Awareness', 'passed': True, 'reason': 'Risks are realistic.'},
            {'name': 'Impact Continuity', 'passed': True, 'reason': 'No contradiction.'},
            {'name': 'Sustainability Logic', 'passed': True, 'reason': 'Team supports impact.'},
            {'name': 'Team Fit', 'passed': True, 'reason': 'Team has skills.'},
            {'name': 'Learning Loop', 'passed': True, 'reason': 'Feedback influenced solution.'},
        ]
    }),
    'model': 'anthropic/claude-3.5-sonnet',
    'tokens': 800,
    'time': 10.0,
    'raw_response': '{}'
}

FAKE_COHERENCE_5_FAILS = {
    'content': json.dumps({
        'checks': [
            {'name': 'User-Problem Fit', 'passed': False, 'reason': 'Mismatch.'},
            {'name': 'Problem-Solution Fit', 'passed': False, 'reason': 'No link.'},
            {'name': 'Difference Validity', 'passed': False, 'reason': 'Not visible.'},
            {'name': 'Execution Reality', 'passed': False, 'reason': 'Steps unrelated.'},
            {'name': 'Resources Alignment', 'passed': False, 'reason': 'No match.'},
            {'name': 'Risk Awareness', 'passed': False, 'reason': 'Unrealistic.'},
            {'name': 'Impact Continuity', 'passed': True, 'reason': 'OK.'},
            {'name': 'Sustainability Logic', 'passed': True, 'reason': 'OK.'},
            {'name': 'Team Fit', 'passed': True, 'reason': 'OK.'},
            {'name': 'Learning Loop', 'passed': True, 'reason': 'OK.'},
        ]
    }),
    'model': 'anthropic/claude-3.5-sonnet',
    'tokens': 800,
    'time': 10.0,
    'raw_response': '{}'
}


class ParseEvaluationResponseTest(TestCase):
    """Test AI response JSON parsing."""

    def test_valid_json(self):
        data = parse_evaluation_response(FAKE_EVAL_RESPONSE['content'])
        self.assertIn('parameter_scores', data)
        self.assertEqual(len(data['parameter_scores']), 10)

    def test_json_with_extra_text(self):
        """Parser should extract JSON even with extra text around it."""
        text = 'Here is my evaluation:\n' + FAKE_EVAL_RESPONSE['content'] + '\nDone.'
        data = parse_evaluation_response(text)
        self.assertIn('parameter_scores', data)

    def test_invalid_json_raises(self):
        with self.assertRaises(ValueError):
            parse_evaluation_response('This is not JSON at all')

    def test_missing_parameter_scores_raises(self):
        with self.assertRaises(ValueError):
            parse_evaluation_response('{"some_other_key": "value"}')


class GetSubmissionQuestionsTest(TestCase):
    """Test question extraction with v3/v2 fallback."""

    def setUp(self):
        self.student = make_student('q_test')

    def test_v3_fields_used(self):
        sub = make_submission(self.student)
        questions = get_submission_questions(sub)
        self.assertIn('Urban students', questions['q1'])
        self.assertEqual(len(questions), 12)

    def test_v2_fallback(self):
        """If v3 fields are empty, should fallback to v2 legacy fields."""
        sub = make_submission(self.student, q1_target_group='', q2_exact_problem='')
        sub.target_user_group = 'Farmers in rural India'
        sub.problem_definition = 'Lack of irrigation technology'
        sub.save()
        questions = get_submission_questions(sub)
        self.assertEqual(questions['q1'], 'Farmers in rural India')
        self.assertEqual(questions['q2'], 'Lack of irrigation technology')


class CoherencePenaltyTest(TestCase):
    """Test coherence penalty application logic."""

    def test_no_failures_no_penalty(self):
        scores = {'uniqueness': 7, 'empathy': 6, 'conceptual_clarity': 7,
                  'impactful': 8, 'ease_of_implementation': 6, 'feasibility': 6,
                  'sustainable': 5, 'creativity': 7, 'communication': 7,
                  'flexible_thinking': 5}
        checks = [{'name': n, 'passed': True, 'reason': 'OK'} for n in COHERENCE_PENALTY_MAP.keys()]
        result, failures, disq = apply_coherence_penalties(scores, checks)
        self.assertEqual(failures, 0)
        self.assertFalse(disq)
        self.assertEqual(result['uniqueness'], 7)  # No change

    def test_single_failure_applies_penalty(self):
        """Difference Validity fail should deduct -1 from Uniqueness."""
        scores = {'uniqueness': 7, 'empathy': 6, 'conceptual_clarity': 7,
                  'impactful': 8, 'ease_of_implementation': 6, 'feasibility': 6,
                  'sustainable': 5, 'creativity': 7, 'communication': 7,
                  'flexible_thinking': 5}
        checks = [{'name': n, 'passed': True, 'reason': 'OK'} for n in COHERENCE_PENALTY_MAP.keys()]
        # Fail "Difference Validity" -> penalizes uniqueness
        checks[2] = {'name': 'Difference Validity', 'passed': False, 'reason': 'Not visible'}
        result, failures, disq = apply_coherence_penalties(scores, checks)
        self.assertEqual(failures, 1)
        self.assertFalse(disq)
        self.assertEqual(result['uniqueness'], 6)  # 7 - 1

    def test_user_problem_fit_fail_penalizes_two(self):
        """User-Problem Fit fail should deduct -1 from both Empathy and Conceptual Clarity."""
        scores = {'uniqueness': 7, 'empathy': 6, 'conceptual_clarity': 7,
                  'impactful': 8, 'ease_of_implementation': 6, 'feasibility': 6,
                  'sustainable': 5, 'creativity': 7, 'communication': 7,
                  'flexible_thinking': 5}
        checks = [{'name': n, 'passed': True, 'reason': 'OK'} for n in COHERENCE_PENALTY_MAP.keys()]
        checks[0] = {'name': 'User-Problem Fit', 'passed': False, 'reason': 'Mismatch'}
        result, failures, disq = apply_coherence_penalties(scores, checks)
        self.assertEqual(failures, 1)
        self.assertEqual(result['empathy'], 5)  # 6 - 1
        self.assertEqual(result['conceptual_clarity'], 6)  # 7 - 1

    def test_more_than_5_failures_disqualifies(self):
        """More than 5 failures = all scores become 0."""
        scores = {'uniqueness': 7, 'empathy': 6, 'conceptual_clarity': 7,
                  'impactful': 8, 'ease_of_implementation': 6, 'feasibility': 6,
                  'sustainable': 5, 'creativity': 7, 'communication': 7,
                  'flexible_thinking': 5}
        checks = [{'name': n, 'passed': False, 'reason': 'Fail'} for n in COHERENCE_PENALTY_MAP.keys()]
        # All 10 fail
        result, failures, disq = apply_coherence_penalties(scores, checks)
        self.assertEqual(failures, 10)
        self.assertTrue(disq)
        for v in result.values():
            self.assertEqual(v, 0)

    def test_exactly_5_failures_not_disqualified(self):
        """Exactly 5 failures = penalties applied but NOT disqualified."""
        scores = {'uniqueness': 7, 'empathy': 6, 'conceptual_clarity': 7,
                  'impactful': 8, 'ease_of_implementation': 6, 'feasibility': 6,
                  'sustainable': 5, 'creativity': 7, 'communication': 7,
                  'flexible_thinking': 5}
        check_names = list(COHERENCE_PENALTY_MAP.keys())
        checks = []
        for i, name in enumerate(check_names):
            checks.append({'name': name, 'passed': i >= 5, 'reason': 'test'})
        result, failures, disq = apply_coherence_penalties(scores, checks)
        self.assertEqual(failures, 5)
        self.assertFalse(disq)  # 5 is NOT > 5

    def test_score_never_goes_below_zero(self):
        """Penalty should not push a score below 0."""
        scores = {'uniqueness': 0, 'empathy': 0, 'conceptual_clarity': 0,
                  'impactful': 0, 'ease_of_implementation': 0, 'feasibility': 0,
                  'sustainable': 0, 'creativity': 0, 'communication': 0,
                  'flexible_thinking': 0}
        checks = [{'name': 'Difference Validity', 'passed': False, 'reason': 'Fail'}]
        result, failures, disq = apply_coherence_penalties(scores, checks)
        self.assertEqual(result['uniqueness'], 0)  # max(0, 0-1) = 0


class FinalScoreCalculationTest(TestCase):
    """Test AIEvaluation.save() correctly calculates final_score."""

    def setUp(self):
        self.student = make_student('score_test')
        self.submission = make_submission(self.student)

    def test_final_score_sum_of_params(self):
        """Final score = sum of 10 params - mismatch penalty."""
        ev = AIEvaluation.objects.create(
            submission=self.submission,
            uniqueness_score=7, ease_of_implementation_score=6,
            feasibility_score=6, impactful_score=8, sustainable_score=5,
            conceptual_clarity_score=7, empathy_score=6, creativity_score=7,
            communication_score=7, flexible_thinking_score=5,
            mismatch_penalty=0,
        )
        self.assertEqual(ev.final_score, 64)  # 7+6+6+8+5+7+6+7+7+5 = 64

    def test_final_score_with_penalty(self):
        ev = AIEvaluation.objects.create(
            submission=self.submission,
            uniqueness_score=7, ease_of_implementation_score=6,
            feasibility_score=6, impactful_score=8, sustainable_score=5,
            conceptual_clarity_score=7, empathy_score=6, creativity_score=7,
            communication_score=7, flexible_thinking_score=5,
            mismatch_penalty=3,
        )
        self.assertEqual(ev.final_score, 61)  # 64 - 3

    def test_final_score_never_below_zero(self):
        ev = AIEvaluation.objects.create(
            submission=self.submission,
            uniqueness_score=1, ease_of_implementation_score=1,
            feasibility_score=1, impactful_score=1, sustainable_score=1,
            conceptual_clarity_score=1, empathy_score=1, creativity_score=1,
            communication_score=1, flexible_thinking_score=1,
            mismatch_penalty=5,
        )
        self.assertEqual(ev.final_score, 5)  # 10 - 5 = 5

    def test_disqualified_score_zero(self):
        ev = AIEvaluation.objects.create(
            submission=self.submission,
            uniqueness_score=7, ease_of_implementation_score=6,
            feasibility_score=6, impactful_score=8, sustainable_score=5,
            conceptual_clarity_score=7, empathy_score=6, creativity_score=7,
            communication_score=7, flexible_thinking_score=5,
            is_disqualified=True,
        )
        self.assertEqual(ev.final_score, 0)

    def test_max_score_100(self):
        ev = AIEvaluation.objects.create(
            submission=self.submission,
            uniqueness_score=10, ease_of_implementation_score=10,
            feasibility_score=10, impactful_score=10, sustainable_score=10,
            conceptual_clarity_score=10, empathy_score=10, creativity_score=10,
            communication_score=10, flexible_thinking_score=10,
            mismatch_penalty=0,
        )
        self.assertEqual(ev.final_score, 100)

    def test_penalty_capped_at_5(self):
        """Even if penalty > 5, it should be capped at 5 in evaluator logic.
        But model save doesn't cap - that's done in evaluator.py."""
        ev = AIEvaluation.objects.create(
            submission=self.submission,
            uniqueness_score=5, ease_of_implementation_score=5,
            feasibility_score=5, impactful_score=5, sustainable_score=5,
            conceptual_clarity_score=5, empathy_score=5, creativity_score=5,
            communication_score=5, flexible_thinking_score=5,
            mismatch_penalty=5,  # Max allowed
        )
        self.assertEqual(ev.final_score, 45)  # 50 - 5


class RankingSystemTest(TestCase):
    """Test ranking and top 400 logic."""

    def setUp(self):
        self.students = []
        for i in range(5):
            self.students.append(make_student(f'rank_user_{i}'))

    def test_rankings_ordered_by_score(self):
        """Higher score = lower rank number (rank 1 = best)."""
        scores = [80, 60, 90, 70, 50]
        for i, score in enumerate(scores):
            sub = make_submission(self.students[i], title=f'Idea {i}')
            sub.status = 'evaluated'
            sub.save()
            per_param = score // 10
            AIEvaluation.objects.create(
                submission=sub,
                uniqueness_score=per_param, ease_of_implementation_score=per_param,
                feasibility_score=per_param, impactful_score=per_param,
                sustainable_score=per_param, conceptual_clarity_score=per_param,
                empathy_score=per_param, creativity_score=per_param,
                communication_score=per_param, flexible_thinking_score=per_param,
            )
        update_rankings()

        evals = AIEvaluation.objects.order_by('rank')
        self.assertEqual(evals[0].final_score, 90)
        self.assertEqual(evals[0].rank, 1)
        self.assertEqual(evals[1].final_score, 80)
        self.assertEqual(evals[1].rank, 2)

    def test_tied_scores_same_rank(self):
        """Submissions with same score get same rank."""
        for i in range(3):
            sub = make_submission(self.students[i], title=f'Idea {i}')
            sub.status = 'evaluated'
            sub.save()
            AIEvaluation.objects.create(
                submission=sub,
                uniqueness_score=7, ease_of_implementation_score=7,
                feasibility_score=7, impactful_score=7, sustainable_score=7,
                conceptual_clarity_score=7, empathy_score=7, creativity_score=7,
                communication_score=7, flexible_thinking_score=7,
            )
        update_rankings()

        ranks = list(AIEvaluation.objects.values_list('rank', flat=True))
        self.assertEqual(ranks.count(1), 3)  # All rank 1

    def test_top_400_no_minimum_threshold(self):
        """Top 400 has no minimum score — any score qualifies if rank <= 400."""
        # Low score (20) - should STILL be top 400 if rank <= 400
        sub1 = make_submission(self.students[0], title='Low score idea')
        sub1.status = 'evaluated'
        sub1.save()
        AIEvaluation.objects.create(
            submission=sub1,
            uniqueness_score=2, ease_of_implementation_score=2,
            feasibility_score=2, impactful_score=2, sustainable_score=2,
            conceptual_clarity_score=2, empathy_score=2, creativity_score=2,
            communication_score=2, flexible_thinking_score=2,
            # Total = 20
        )

        # High score (80)
        sub2 = make_submission(self.students[1], title='High score idea')
        sub2.status = 'evaluated'
        sub2.save()
        AIEvaluation.objects.create(
            submission=sub2,
            uniqueness_score=8, ease_of_implementation_score=8,
            feasibility_score=8, impactful_score=8, sustainable_score=8,
            conceptual_clarity_score=8, empathy_score=8, creativity_score=8,
            communication_score=8, flexible_thinking_score=8,
            # Total = 80
        )

        update_rankings()

        ev1 = AIEvaluation.objects.get(submission=sub1)
        ev2 = AIEvaluation.objects.get(submission=sub2)
        # Both should be in top 400 (only 2 submissions, both rank <= 400)
        self.assertTrue(ev1.is_top_400)
        self.assertTrue(ev2.is_top_400)
        # High score should have better rank
        self.assertEqual(ev2.rank, 1)
        self.assertEqual(ev1.rank, 2)

    def test_disqualified_excluded_from_ranking(self):
        """Disqualified submissions should have rank=None."""
        sub = make_submission(self.students[0], title='Disqualified idea')
        sub.status = 'evaluated'
        sub.save()
        AIEvaluation.objects.create(
            submission=sub,
            uniqueness_score=0, ease_of_implementation_score=0,
            feasibility_score=0, impactful_score=0, sustainable_score=0,
            conceptual_clarity_score=0, empathy_score=0, creativity_score=0,
            communication_score=0, flexible_thinking_score=0,
            is_disqualified=True,
        )
        update_rankings()

        ev = AIEvaluation.objects.get(submission=sub)
        self.assertIsNone(ev.rank)
        self.assertFalse(ev.is_top_400)


class EvaluateIdeaParallelTest(TestCase):
    """Test full evaluate_idea function with mocked API calls."""

    def setUp(self):
        self.student = make_student('eval_test')
        self.submission = make_submission(self.student)

    @patch('ai_assistant.evaluator.OpenRouterClient')
    def test_evaluate_creates_evaluation(self, MockClient):
        """evaluate_idea should create an AIEvaluation record."""
        mock_instance = MagicMock()
        mock_instance.generate_completion.side_effect = [
            FAKE_EVAL_RESPONSE,       # Main eval
            FAKE_COHERENCE_RESPONSE,   # Coherence (from run_coherence_checks)
        ]
        MockClient.return_value = mock_instance

        evaluation = evaluate_idea(self.submission)

        self.assertIsNotNone(evaluation)
        self.assertEqual(evaluation.uniqueness_score, 7)
        self.assertEqual(evaluation.impactful_score, 8)
        self.assertEqual(evaluation.flexible_thinking_score, 5)
        self.assertFalse(evaluation.is_disqualified)
        self.assertEqual(evaluation.coherence_failures, 0)
        self.assertEqual(self.submission.status, 'evaluated')

    @patch('ai_assistant.evaluator.OpenRouterClient')
    def test_evaluate_skips_if_already_evaluated(self, MockClient):
        """Should return existing evaluation if not force_reevaluate."""
        existing = AIEvaluation.objects.create(
            submission=self.submission,
            uniqueness_score=5, ease_of_implementation_score=5,
            feasibility_score=5, impactful_score=5, sustainable_score=5,
            conceptual_clarity_score=5, empathy_score=5, creativity_score=5,
            communication_score=5, flexible_thinking_score=5,
        )
        result = evaluate_idea(self.submission)
        self.assertEqual(result.id, existing.id)
        # API should NOT have been called
        MockClient.return_value.generate_completion.assert_not_called()

    @patch('ai_assistant.evaluator.OpenRouterClient')
    def test_force_reevaluate_takes_min_score(self, MockClient):
        """Re-evaluation should take min(old, new) for each parameter."""
        # Old eval had uniqueness=9
        AIEvaluation.objects.create(
            submission=self.submission,
            uniqueness_score=9, ease_of_implementation_score=8,
            feasibility_score=8, impactful_score=9, sustainable_score=8,
            conceptual_clarity_score=8, empathy_score=8, creativity_score=9,
            communication_score=8, flexible_thinking_score=8,
        )
        mock_instance = MagicMock()
        mock_instance.generate_completion.side_effect = [
            FAKE_EVAL_RESPONSE,       # New eval has uniqueness=7
            FAKE_COHERENCE_RESPONSE,
        ]
        MockClient.return_value = mock_instance

        evaluation = evaluate_idea(self.submission, force_reevaluate=True)
        # Should take min(old=9, new=7) = 7
        self.assertEqual(evaluation.uniqueness_score, 7)
        # Should take min(old=8, new=6) = 6
        self.assertEqual(evaluation.ease_of_implementation_score, 6)

    @patch('ai_assistant.evaluator.OpenRouterClient')
    def test_api_failure_raises_runtime_error(self, MockClient):
        """If AI API fails, should raise RuntimeError."""
        mock_instance = MagicMock()
        mock_instance.generate_completion.side_effect = Exception('API timeout')
        MockClient.return_value = mock_instance

        with self.assertRaises(RuntimeError):
            evaluate_idea(self.submission)


class AttachmentPenaltyEdgeCaseTest(TestCase):
    """Test attachment penalty edge cases in the evaluation model."""

    def setUp(self):
        self.student = make_student('attach_test')
        self.submission = make_submission(self.student)

    def test_no_files_penalty_3(self):
        """No files = -3 penalty."""
        ev = AIEvaluation.objects.create(
            submission=self.submission,
            uniqueness_score=7, ease_of_implementation_score=7,
            feasibility_score=7, impactful_score=7, sustainable_score=7,
            conceptual_clarity_score=7, empathy_score=7, creativity_score=7,
            communication_score=7, flexible_thinking_score=7,
            mismatch_penalty=3, mismatch_severity='missing',
            attachment_mismatch=True,
        )
        self.assertEqual(ev.final_score, 67)  # 70 - 3

    def test_severe_mismatch_penalty_5(self):
        """All files irrelevant = -5 penalty."""
        ev = AIEvaluation.objects.create(
            submission=self.submission,
            uniqueness_score=7, ease_of_implementation_score=7,
            feasibility_score=7, impactful_score=7, sustainable_score=7,
            conceptual_clarity_score=7, empathy_score=7, creativity_score=7,
            communication_score=7, flexible_thinking_score=7,
            mismatch_penalty=5, mismatch_severity='severe',
            attachment_mismatch=True,
        )
        self.assertEqual(ev.final_score, 65)  # 70 - 5

    def test_no_mismatch_no_penalty(self):
        """All files relevant = 0 penalty."""
        ev = AIEvaluation.objects.create(
            submission=self.submission,
            uniqueness_score=7, ease_of_implementation_score=7,
            feasibility_score=7, impactful_score=7, sustainable_score=7,
            conceptual_clarity_score=7, empathy_score=7, creativity_score=7,
            communication_score=7, flexible_thinking_score=7,
            mismatch_penalty=0, mismatch_severity='none',
        )
        self.assertEqual(ev.final_score, 70)  # 70 - 0
