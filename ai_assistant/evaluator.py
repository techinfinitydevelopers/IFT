"""
AI Idea Evaluator - Scores submissions using 10-parameter jury rubric (1-5 scale each).
"""
import json
import re
from .openrouter_client import OpenRouterClient
from .models import AIEvaluation
from students.models import IdeaSubmission


# 10-parameter evaluation prompt based on jury rubric (exact sheet descriptions)
EVALUATION_PROMPT = """You are an Idea Evaluation AI for a student innovation competition called "India Future Tycoon".
Evaluate the submitted idea using exactly these 10 parameters on a 1-5 scale.

IDEA SUBMISSION:
================
Title: {title}
Problem Statement: {problem_statement}
Proposed Solution: {proposed_solution}
Target Users: {target_users}
Idea Stage: {idea_stage}

SCORING RUBRIC (Rate each 1-5, where 1 is WORST and 5 is BEST):
================================================================

=== IDEA PARAMETERS ===

1. UNIQUENESS (1-5)
   5 = (a) Mostly new/unheard of idea - even a targeted Google search doesn't throw up anything similar
       (b) Market competitors/existing alternatives don't have any similarity with this idea
   4 = (a) Idea seems new, a random Google search doesn't throw up anything similar
       (b) Not more than 2 existing alternatives or market competitors are based on similar thoughts
   3 = (a) Idea seems new
       (b) Though some existing alternatives are based on similar ideas but this idea has some distinguishing features which separate it from the existing alternatives
   2 = (a) Idea seems similar to ideas/thoughts behind the existing alternatives
       (b) It is tough to see any differentiator between this and the existing alternatives already in the market
   1 = (a) The idea seems like any other idea currently in use to solve a similar problem
       (b) It is tough to see any differentiator between this and the existing alternatives already in the market

2. EASE OF IMPLEMENTATION (1-5)
   5 = (a) Resources required are available in the market and can be easily procured
       (b) Team has the expertise to give shape to the idea
       (c) The team has complete clarity on how to translate the features into product benefits
   4 = (a) Resources required are available in the market and can be easily procured
       (b) Team has the expertise to give shape to the idea
       (c) The team has a fair idea of how to translate the features into product benefits
   3 = (a) Resources required are available in the market and can be easily procured
       (b) Team lacks the expertise to give shape to the idea - they need to hire experts
       (c) The team has a sketchy idea of how to translate the features into product benefits
   2 = (a) Resources required are not easily available in the market
       (b) Team lacks the expertise to give shape to the idea - they need to hire experts
       (c) The team is not sure how to translate the features into product benefits
   1 = (a) Resources required are not easily available in the market
       (b) Team lacks the expertise to give shape to the idea
       (c) The team does not have any idea how to translate the features into product benefits

3. SCALABLE (1-5)
   5 = Considering the solution benefits, the idea has the potential to take the business from X to 30X in terms of growth in the first two years of operation
   4 = Considering the solution benefits, the idea has the potential to take the business from X to 20X in terms of growth in the first two years of operation
   3 = Considering the solution benefits, the idea has the potential to take the business from X to 10X in terms of growth in the first two years of operation
   2 = Considering the solution benefits, the idea has the potential to grow the business to some extent in the first two years of operation
   1 = Considering the solution benefits, it seems unlikely that the business can grow at all unless some major change is introduced

4. IMPACTFUL (1-5)
   5 = (a) The identified customer base that will get impacted by the solution idea is widespread
       (b) The solution idea is critical for the user and makes a positive difference in their everyday lives
       (c) The solution idea removes the current pains AND gives additional benefits over existing alternatives
   4 = (a) The identified customer base that will get impacted by the solution idea is widespread
       (b) The solution idea brings a positive difference to the users' lives
       (c) The solution idea removes the current pains but no additional benefits over existing alternatives
   3 = (a) The team is yet to fully identify the customer base
       (b) The solution idea brings a positive difference to the users' lives
       (c) The solution idea removes a few of the current pains but no additional benefits over existing alternatives
   2 = (a) The customer base is sporadic and irregular
       (b) The solution idea brings a positive difference to the users' lives
       (c) The solution idea removes a few pains but no additional benefits over existing alternatives
   1 = (a) The customer base is sporadic and irregular
       (b) The solution idea does not bring any visible positive difference
       (c) The solution idea does not impact the customers' lives in any visible way

5. SUSTAINABLE (1-5)
   Score based on answers to these 3 questions:
   Q1: Is the idea solving a common problem that an average person would face?
   Q2: Will the solution create enough difference that users would be ready to pay for it?
   Q3: Is the idea going to last more than a year?
   5 = All three questions answered YES
   4 = Q1 and Q2 are YES, but not sure about Q3
   3 = Q1 is YES, but not sure about Q2 and Q3
   2 = Not sure about any of the three questions
   1 = Any of the three questions is a resounding NO

=== TEAM PARAMETERS ===
NOTE: Since this is a text-based submission (not face-to-face), infer team qualities from:
- How clearly and coherently the student writes (Communication)
- How detailed and structured their execution plan is (Conceptual Clarity)
- How well they understand user pain points (Empathy)
- How unique/divergent their approach to the solution is (Creativity)
- Whether they mention willingness to iterate, learn, or adapt (Flexible Thinking)

6. CONCEPTUAL CLARITY & COMPREHENSIVENESS (1-5)
   5 = The team is clear about the idea and execution. They have thought out details like how the final product looks, what features are non-negotiable vs good-to-have.
   4 = The team is clear about the idea and execution. They have thought out features but are yet to decide which are non-negotiable vs good-to-have.
   3 = The team is clear about the idea and execution. They have an image of the product but plan to proceed further on the go.
   2 = The team is clear about the idea but not decided on execution. They plan to proceed on the go.
   1 = The team is still not very clear about the idea and are getting lost. They are yet to think through the execution plan.

7. EMPATHY (1-5)
   5 = Great empathy demonstrated. Put themselves in users' shoes, felt the challenges users face. Besides removing current pains, also looked at gains they could bring to users' lives.
   4 = Great empathy demonstrated. Put themselves in users' shoes, felt challenges. Ensured their idea removes all pains users currently face with existing alternatives.
   3 = Ample empathy demonstrated. Tried to feel users' challenges. Ensured idea removes most pains users currently face.
   2 = Some empathy. Tried to identify challenges but failed to identify all pains. Idea fails to provide a complete solution.
   1 = Focused more on thrill of ideation. Ignored users and their pains. Idea fails to provide a solution to users' problems.

8. CREATIVITY (1-5)
   5 = Demonstrated divergent/out-of-box thinking. Trend-setter temperament. Shows creativity and innovation in how they present the idea and approach the problem.
   4 = Demonstrated divergent thinking. Trend-setter temperament. However, the presentation and approach is conventional.
   3 = Demonstrated good problem-solving skills. Plays safe, doesn't stray from the trodden path. Conventional approach.
   2 = Good problem-solving but hardly any creative temperament visible in the submission.
   1 = Average problem-solving. No creative temperament visible in the submission.

9. COMMUNICATION (1-5)
   5 = Ideas communicated clearly and coherently. Writing is well-structured, uses examples, and effectively conveys the vision to the reader. All aspects covered comprehensively.
   4 = Ideas communicated clearly. Writing is structured and conveys the vision. Minor gaps in external communication clarity.
   3 = Communication is somewhat unclear. Some confusion in conveying ideas. Reader has to work to understand the vision.
   2 = Communication needs improvement. Ideas are not conveyed clearly. Writing lacks structure and coherence.
   1 = Communication is ineffective. Writing is confusing, unclear, and fails to convey the idea properly.

10. FLEXIBLE THINKING (1-5)
    5 = Demonstrates flexible approach. Mentions willingness to learn, adapt, iterate. Shows awareness that the idea may need to evolve.
    4 = Demonstrates flexibility. Willing to adapt and iterate when essential.
    3 = Shows some resistance to change. Only willing to adapt if absolutely essential.
    2 = Does not demonstrate flexibility. No mention of willingness to adapt or iterate.
    1 = Appears completely closed to any iteration or change whatsoever.

RESPONSE FORMAT (STRICT JSON):
==============================
Return ONLY valid JSON with this exact structure:
{{
    "parameter_scores": [
        {{"parameter_name": "Uniqueness", "score": <1-5>, "reason": "<one sentence>"}},
        {{"parameter_name": "Ease of Implementation", "score": <1-5>, "reason": "<one sentence>"}},
        {{"parameter_name": "Scalable", "score": <1-5>, "reason": "<one sentence>"}},
        {{"parameter_name": "Impactful", "score": <1-5>, "reason": "<one sentence>"}},
        {{"parameter_name": "Sustainable", "score": <1-5>, "reason": "<one sentence>"}},
        {{"parameter_name": "Conceptual Clarity", "score": <1-5>, "reason": "<one sentence>"}},
        {{"parameter_name": "Empathy", "score": <1-5>, "reason": "<one sentence>"}},
        {{"parameter_name": "Creativity", "score": <1-5>, "reason": "<one sentence>"}},
        {{"parameter_name": "Communication", "score": <1-5>, "reason": "<one sentence>"}},
        {{"parameter_name": "Flexible Thinking", "score": <1-5>, "reason": "<one sentence>"}}
    ],
    "total_score": <sum of all 10 scores, range 10-50>,
    "overall_justification": "<2-3 sentence summary>",
    "confidence": "<high/medium/low>"
}}

IMPORTANT RULES:
- Score MUST be integer 1-5 only (no 0, no decimals)
- Higher score = BETTER (5 is best, 1 is worst)
- Do NOT default to score 3. If the idea genuinely meets the criteria for 4 or 5, give that score. Be fair, not conservative.
- Evaluate based on what IS written, not what is missing. If a student clearly articulates a strong idea, reward them.
- Reason MUST be one short sentence
- Do NOT include recommendations or rankings
"""


def parse_evaluation_response(response_text):
    """Parse AI response JSON into structured data"""
    try:
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            data = json.loads(json_match.group())
            if 'parameter_scores' in data:
                return data
    except json.JSONDecodeError:
        pass
    
    raise ValueError(f"Could not parse AI response as JSON: {response_text[:200]}")


def evaluate_idea(submission: IdeaSubmission, force_reevaluate=False) -> AIEvaluation:
    """
    Evaluate a single idea submission using 10-parameter jury rubric.
    """
    if hasattr(submission, 'ai_evaluation') and not force_reevaluate:
        return submission.ai_evaluation

    if force_reevaluate:
        try:
            old_eval = submission.ai_evaluation
            old_eval.delete()
        except AIEvaluation.DoesNotExist:
            pass

    client = OpenRouterClient()

    # Build prompt with submission data
    problem_statement = submission.problem_definition or ''
    problem_description = submission.problem_description or ''
    proposed_solution = submission.solution or ''
    target_users = submission.target_user_group or ''
    idea_stage = submission.get_idea_stage_display() if submission.idea_stage else 'Idea'

    full_problem = f"{problem_statement}\n\n{problem_description}"
    full_solution = f"{proposed_solution}"

    prompt = EVALUATION_PROMPT.format(
        title=submission.title or problem_statement[:100],
        problem_statement=full_problem,
        proposed_solution=full_solution,
        target_users=target_users,
        idea_stage=idea_stage
    )

    try:
        response = client.generate_completion(
            system_prompt="You are an expert idea evaluator. Return ONLY valid JSON, no other text.",
            user_prompt=prompt,
            model="anthropic/claude-3.5-sonnet",
            max_tokens=1500
        )
    except Exception as e:
        raise RuntimeError(f"AI API call failed: {str(e)}")

    if not response or 'content' not in response:
        raise RuntimeError("AI returned empty or invalid response")

    try:
        eval_data = parse_evaluation_response(response['content'])
    except ValueError as e:
        raise RuntimeError(f"Failed to parse AI response: {str(e)}")
    
    # Extract scores from parameter_scores array
    scores = {p['parameter_name']: p for p in eval_data.get('parameter_scores', [])}
    
    def get_score(name, default=3):
        param = scores.get(name, {})
        score = param.get('score', default)
        return max(1, min(5, int(score)))  # Clamp to 1-5
    
    def get_reason(name, default=''):
        return scores.get(name, {}).get('reason', default)
    
    evaluation = AIEvaluation.objects.create(
        submission=submission,
        
        # Idea parameters
        uniqueness_score=get_score('Uniqueness'),
        ease_of_implementation_score=get_score('Ease of Implementation'),
        scalable_score=get_score('Scalable'),
        impactful_score=get_score('Impactful'),
        sustainable_score=get_score('Sustainable'),
        
        # Team parameters
        conceptual_clarity_score=get_score('Conceptual Clarity'),
        empathy_score=get_score('Empathy'),
        creativity_score=get_score('Creativity'),
        communication_score=get_score('Communication'),
        flexible_thinking_score=get_score('Flexible Thinking'),
        
        # Justifications
        uniqueness_justification=get_reason('Uniqueness'),
        ease_of_implementation_justification=get_reason('Ease of Implementation'),
        scalable_justification=get_reason('Scalable'),
        impactful_justification=get_reason('Impactful'),
        sustainable_justification=get_reason('Sustainable'),
        conceptual_clarity_justification=get_reason('Conceptual Clarity'),
        empathy_justification=get_reason('Empathy'),
        creativity_justification=get_reason('Creativity'),
        communication_justification=get_reason('Communication'),
        flexible_thinking_justification=get_reason('Flexible Thinking'),
        overall_justification=eval_data.get('overall_justification', ''),
        
        # Metadata
        confidence_level=eval_data.get('confidence', 'medium'),
        model_used=response.get('model', 'anthropic/claude-3.5-sonnet'),
        tokens_used=response.get('tokens', 0),
        processing_time=response.get('time', 0),
        raw_response=response.get('raw_response', '')
    )
    
    submission.status = 'evaluated'
    submission.save(update_fields=['status'])
    
    return evaluation


def batch_evaluate(submissions=None, limit=None):
    """Evaluate multiple submissions."""
    if submissions is None:
        submissions = IdeaSubmission.objects.filter(
            status='submitted'
        ).exclude(
            ai_evaluation__isnull=False
        )
    
    if limit:
        submissions = submissions[:limit]
    
    results = []
    for submission in submissions:
        try:
            evaluation = evaluate_idea(submission)
            results.append((submission, evaluation, None))
        except Exception as e:
            results.append((submission, None, str(e)))
    
    return results


def update_rankings():
    """
    Update rank fields for all evaluated submissions.
    Rankings are ordered by final_score descending (higher score = better, since 5=BEST, 1=WORST).
    Top 400 requires score >= 34 (average of 3.4+ per parameter).
    """
    evaluations = AIEvaluation.objects.all().order_by(
        '-final_score',
        '-uniqueness_score',
        '-impactful_score'
    )

    prev_score = None
    prev_rank = None
    for i, evaluation in enumerate(evaluations, start=1):
        # Tied scores get the same rank
        if evaluation.final_score == prev_score:
            evaluation.rank = prev_rank
        else:
            evaluation.rank = i
            prev_rank = i
        prev_score = evaluation.final_score
        # Top 400: rank within 400 AND score >= 34 (68% of max 50)
        evaluation.is_top_400 = (evaluation.rank <= 400) and (evaluation.final_score >= 34)
        evaluation.save(update_fields=['rank', 'is_top_400'])
    
    return evaluations.count()


def get_top_n(n=400):
    """Get top N ranked submissions"""
    update_rankings()
    return AIEvaluation.objects.filter(is_top_400=True).select_related('submission', 'submission__student__user')
