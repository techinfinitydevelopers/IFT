"""
AI Idea Evaluator - Scores submissions using 10-parameter rubric (0-10 scale each, max 100).
Includes 10 coherence cross-checks with -1 penalty each. >5 failures = disqualified.
"""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from django.conf import settings
from .openrouter_client import OpenRouterClient
from .models import AIEvaluation, AISummary
from students.models import IdeaSubmission


# ============================================================================
# EVALUATION PROMPT — 12 Questions, 0-10 Scale, Primary/Secondary 60/40
# ============================================================================
EVALUATION_PROMPT = """You are a STRICT Idea Evaluation AI for a student innovation competition called "India Future Tycoon".
You must be RIGOROUS - this is a competition, and only truly strong ideas should score high.
Evaluate the submitted idea using exactly these 10 parameters on a 0-10 scale.

IDEA SUBMISSION (12 Questions):
================================
Q1 - Target Group & Struggle: {q1}
Q2 - Exact Problem & Why It Matters: {q2}
Q3 - Solution (Explained Simply): {q3}
Q4 - How Solution Is Different: {q4}
Q5 - Key Steps to Build & Test: {q5}
Q6 - Resources Required & Available: {q6}
Q7 - Positive Change If Successful: {q7}
Q8 - Challenges & How to Deal: {q8}
Q9 - Why Team Is Best Placed: {q9}
Q10 - User Feedback & Learning: {q10}
Q11 - Most Creative Element: {q11}
Q12 - 60-Second Pitch: {q12}

SUBMISSION EFFORT: {effort_note}

*** PRIMARY/SECONDARY QUESTION-PARAMETER MAPPING (60/40 Weightage) ***
=======================================================================
When scoring each parameter, give 60% weight to PRIMARY question(s) and 40% to SECONDARY:

| Parameter              | Primary Questions (60%) | Secondary Questions (40%) |
|------------------------|------------------------|--------------------------|
| 1. Uniqueness          | Q4                     | Q11                      |
| 2. Ease of Impl.       | Q5                     | Q6                       |
| 3. Feasibility         | Q6                     | Q5, Q8                   |
| 4. Impact              | Q1, Q7                 | Q12                      |
| 5. Sustainability      | Q7                     | Q1                       |
| 6. Conceptual Clarity  | Q2, Q3                 | Q4, Q9                   |
| 7. Empathy             | Q1                     | Q2, Q10                  |
| 8. Creativity          | Q11                    | Q4                       |
| 9. Communication       | Q12                    | Q3, Q9                   |
| 10. Flexible Thinking  | Q8, Q10                | Q6                       |

SCORING RUBRIC (Rate each 0-10):
==================================

=== IDEA PARAMETERS ===

1. UNIQUENESS (0-10)
   High (8-10): Completely new/unheard idea — even targeted Google search shows nothing similar. No market competitors with similar approach. Clear differentiator explained.
   Moderate (4-7): Idea has some novelty. A few similar alternatives exist but this has distinguishing features.
   Low (0-3): Idea seems like any existing solution. No visible differentiator from alternatives.
   KEYWORDS to look for: novel, first-of-its-kind, no competitor, patent-worthy, unique angle, disrupts existing, never done before, gap in market

2. EASE OF IMPLEMENTATION (0-10)
   High (8-10): Clear step-by-step plan. Resources available and listed. Team has expertise. Feature-to-benefit translation is clear.
   Moderate (4-7): Some plan exists but gaps in execution details. Resources partially available.
   Low (0-3): No clear plan. Resources unavailable. Team lacks expertise. No idea how to translate features to benefits.
   KEYWORDS: step-by-step, prototype ready, tested, pilot, resources listed, team skills, timeline, actionable

3. FEASIBILITY (0-10)
   High (8-10): Resources realistically available. Plan is practical with clear milestones. Challenges acknowledged with mitigation strategies.
   Moderate (4-7): Plan is partially realistic. Some resources available. Challenges mentioned but solutions vague.
   Low (0-3): Plan seems unrealistic. Resources unavailable. No awareness of real constraints.
   KEYWORDS: budget, cost-effective, available tools, realistic timeline, already have, partnership, phased approach

4. IMPACT (0-10)
   High (8-10): Widespread customer base. Solution is critical for users. Removes pains AND adds new benefits over alternatives. Shows scale of impact.
   Moderate (4-7): Customer base identified but not fully characterized. Some positive impact visible.
   Low (0-3): Sporadic users. No visible positive difference. Impact claim not supported.
   KEYWORDS: millions affected, daily pain, life-changing, saves time/money, health impact, community benefit, scalable impact

5. SUSTAINABILITY (0-10)
   High (8-10): Solves common problem + users would pay + lasts more than a year. Revenue model clear. Long-term viability demonstrated.
   Moderate (4-7): Some sustainability factors present. Revenue model unclear but idea has staying power.
   Low (0-3): Any of: not a common problem, users won't pay, won't last. No long-term plan.
   KEYWORDS: revenue model, subscription, recurring, long-term, sustainable, growth plan, retention, business model

=== TEAM PARAMETERS ===
NOTE: Since this is text-based (not face-to-face), infer team qualities from writing quality.

6. CONCEPTUAL CLARITY (0-10)
   High (8-10): Clear about idea AND execution. Knows non-negotiable vs nice-to-have features. Problem-solution link is crystal clear.
   Moderate (4-7): Clear about idea but execution plan is vague. Has product image but details are sketchy.
   Low (0-3): Still unclear about the idea itself. No execution plan. Getting lost in explanation.
   KEYWORDS: clear vision, roadmap, feature list, MVP, priority, architecture, well-defined, structured

7. EMPATHY (0-10)
   High (8-10): Deep empathy — put themselves in users' shoes, felt challenges. Describes real user stories/observations. Removes pains AND brings extra gains.
   Moderate (4-7): Some empathy. Tried to identify user challenges but description is generic.
   Low (0-3): Focused on thrill of ideation. Ignored users and their actual pains. No user understanding.
   KEYWORDS: user interviews, observed, felt, struggled, pain point, user story, walked in shoes, feedback

8. CREATIVITY (0-10)
   High (8-10): Divergent/out-of-box thinking. Trend-setter. Creative presentation and approach. Unexpected element clearly described.
   Moderate (4-7): Good problem-solving but conventional approach. Plays safe.
   Low (0-3): Average approach. No creative temperament visible. Copy of existing solutions.
   KEYWORDS: innovative, unexpected, creative twist, new approach, reimagined, disrupted, unconventional

9. COMMUNICATION (0-10)
   High (8-10): Ideas communicated clearly. Well-structured writing. Uses examples. Vision effectively conveyed. Pitch is compelling.
   Moderate (4-7): Communication is adequate but has gaps. Reader has to work to understand.
   Low (0-3): Confusing, unclear writing. Fails to convey the idea. No structure.
   KEYWORDS: clear, concise, examples, structured, compelling, persuasive, well-written, engaging

10. FLEXIBLE THINKING (0-10)
    High (8-10): Mentions willingness to learn, adapt, iterate. Shows awareness idea may evolve. Describes actual pivot or change after feedback.
    Moderate (4-7): Some flexibility shown. Willing to adapt if essential.
    Low (0-3): No mention of adaptability. Appears closed to iteration. No evidence of learning from feedback.
    KEYWORDS: pivot, iterate, adapt, feedback, learned, changed approach, flexible, open to change

RESPONSE FORMAT (STRICT JSON):
===============================
Return ONLY valid JSON with this exact structure:
{{
    "parameter_scores": [
        {{"parameter_name": "Uniqueness", "score": <0-10>, "reason": "<one sentence>"}},
        {{"parameter_name": "Ease of Implementation", "score": <0-10>, "reason": "<one sentence>"}},
        {{"parameter_name": "Feasibility", "score": <0-10>, "reason": "<one sentence>"}},
        {{"parameter_name": "Impact", "score": <0-10>, "reason": "<one sentence>"}},
        {{"parameter_name": "Sustainability", "score": <0-10>, "reason": "<one sentence>"}},
        {{"parameter_name": "Conceptual Clarity", "score": <0-10>, "reason": "<one sentence>"}},
        {{"parameter_name": "Empathy", "score": <0-10>, "reason": "<one sentence>"}},
        {{"parameter_name": "Creativity", "score": <0-10>, "reason": "<one sentence>"}},
        {{"parameter_name": "Communication", "score": <0-10>, "reason": "<one sentence>"}},
        {{"parameter_name": "Flexible Thinking", "score": <0-10>, "reason": "<one sentence>"}}
    ],
    "total_score": <sum of all 10 scores, range 0-100>,
    "overall_justification": "<2-3 sentence summary>",
    "confidence": "<high/medium/low>"
}}

IMPORTANT RULES:
- Score MUST be integer 0-10
- Higher score = BETTER (10 is best, 0 is worst)
- Be STRICT and RIGOROUS. This is a national competition.
- High scores (8-10) should be RARE (top 5% quality). 6-7 = strong. 4-5 = average. 2-3 = below average. 0-1 = poor.
- If the student gave vague, short, or generic answers, score LOW.
- Generic ideas ("make an app to solve X") without differentiation should score 0-3 on Uniqueness and Creativity.
- If no explanation of WHY solution is better than alternatives, Uniqueness and Impact should be LOW.
- If no understanding of user pain points with examples, Empathy should be LOW.
- If no mention of adaptability or willingness to learn, Flexible Thinking MUST be 0-3.
- Remember 60/40 weightage: Primary questions matter MORE for each parameter.
- Reason MUST be one short sentence.
- Do NOT include recommendations or rankings.
"""


# ============================================================================
# COHERENCE CHECK PROMPT — 10 Cross-Checks
# ============================================================================
COHERENCE_CHECK_PROMPT = """You are checking LOGICAL CONSISTENCY between answers in a student's innovation idea submission.
For each pair of questions, determine if the answers are CONSISTENT (logically connected) or INCONSISTENT (contradictory/unrelated).

SUBMISSION ANSWERS:
====================
Q1 - Target Group: {q1}
Q2 - Exact Problem: {q2}
Q3 - Solution Simple: {q3}
Q4 - Differentiation: {q4}
Q5 - Build Steps: {q5}
Q6 - Resources: {q6}
Q7 - Positive Change: {q7}
Q8 - Challenges: {q8}
Q9 - Team Fit: {q9}
Q10 - Feedback: {q10}
Q11 - Creative Element: {q11}
Q12 - Pitch: {q12}

PERFORM THESE 10 CHECKS:
=========================
1. USER-PROBLEM FIT (Q1 vs Q2): Does the target group in Q1 match the problem described in Q2? Are these the people who would face this problem?
2. PROBLEM-SOLUTION FIT (Q2 vs Q3): Does the solution in Q3 DIRECTLY address the problem in Q2? Is there a logical connection?
3. DIFFERENCE VALIDITY (Q3 vs Q4): Is the claimed difference in Q4 actually visible in the solution described in Q3?
4. EXECUTION REALITY (Q3 vs Q5): Are the build steps in Q5 actually needed to create the solution in Q3? Do they make sense together?
5. RESOURCES ALIGNMENT (Q5 vs Q6): Do the resources in Q6 support the steps listed in Q5? Are required resources acknowledged?
6. RISK AWARENESS (Q6 vs Q8): Do the challenges in Q8 reflect real constraints from the resources in Q6? Are risks realistic?
7. IMPACT CONTINUITY (Q7 vs Q8): Do the challenges in Q8 contradict the positive impact claimed in Q7?
8. SUSTAINABILITY LOGIC (Q7 vs Q9): Does the team's positioning in Q9 support the long-term impact claimed in Q7?
9. TEAM FIT (Q5+Q6 vs Q9): Does the team in Q9 have the skills/resources needed for the steps (Q5) and resources (Q6)?
10. LEARNING LOOP (Q10 vs Q3+Q5): Has the feedback in Q10 actually influenced the current solution (Q3) or build steps (Q5)?

RULES:
- Be STRICT. Only pass if there is a CLEAR logical connection.
- If an answer is empty or too short (<10 words), that check FAILS.
- If answers contradict each other, that check FAILS.
- If answers seem to be about different topics, that check FAILS.

Return ONLY valid JSON:
{{
    "checks": [
        {{"name": "User-Problem Fit", "passed": true, "reason": "brief reason"}},
        {{"name": "Problem-Solution Fit", "passed": true, "reason": "brief reason"}},
        {{"name": "Difference Validity", "passed": true, "reason": "brief reason"}},
        {{"name": "Execution Reality", "passed": true, "reason": "brief reason"}},
        {{"name": "Resources Alignment", "passed": true, "reason": "brief reason"}},
        {{"name": "Risk Awareness", "passed": true, "reason": "brief reason"}},
        {{"name": "Impact Continuity", "passed": true, "reason": "brief reason"}},
        {{"name": "Sustainability Logic", "passed": true, "reason": "brief reason"}},
        {{"name": "Team Fit", "passed": true, "reason": "brief reason"}},
        {{"name": "Learning Loop", "passed": true, "reason": "brief reason"}}
    ]
}}
"""

# Coherence check definitions: which parameters get -1 penalty for each failed check
COHERENCE_PENALTY_MAP = {
    'User-Problem Fit': ['empathy', 'conceptual_clarity'],
    'Problem-Solution Fit': ['conceptual_clarity', 'impactful'],
    'Difference Validity': ['uniqueness'],
    'Execution Reality': ['ease_of_implementation', 'feasibility'],
    'Resources Alignment': ['feasibility'],
    'Risk Awareness': ['flexible_thinking'],
    'Impact Continuity': ['impactful'],
    'Sustainability Logic': ['sustainable'],
    'Team Fit': ['communication'],
    'Learning Loop': ['flexible_thinking'],
}


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


def get_submission_questions(submission):
    """Get 12 question answers from submission, with fallback to old fields."""
    return {
        'q1': submission.q1_target_group or submission.target_user_group or '',
        'q2': submission.q2_exact_problem or submission.problem_definition or '',
        'q3': submission.q3_solution_simple or submission.solution or '',
        'q4': submission.q4_differentiation or submission.innovation_uniqueness or '',
        'q5': submission.q5_build_steps or submission.feasibility_execution or '',
        'q6': submission.q6_resources or '',
        'q7': submission.q7_positive_change or submission.solution_benefits or '',
        'q8': submission.q8_challenges or '',
        'q9': submission.q9_team_fit or submission.why_best_equipped or '',
        'q10': submission.q10_feedback or '',
        'q11': submission.q11_creative_element or '',
        'q12': submission.q12_pitch or '',
    }


def run_coherence_checks(questions, client):
    """
    Run 10 coherence cross-checks via AI.
    Returns list of check results: [{'name': str, 'passed': bool, 'reason': str}, ...]
    """
    prompt = COHERENCE_CHECK_PROMPT.format(**questions)

    try:
        response = client.generate_completion(
            system_prompt="You are a strict logical consistency checker. Return ONLY valid JSON.",
            user_prompt=prompt,
            model="anthropic/claude-3.5-sonnet",
            max_tokens=1200
        )

        if response and 'content' in response:
            json_match = re.search(r'\{[\s\S]*\}', response['content'])
            if json_match:
                data = json.loads(json_match.group())
                checks = data.get('checks', [])
                if len(checks) == 10:
                    return checks
    except Exception as e:
        print(f"[COHERENCE] AI check failed: {e}")

    # Fallback: all checks pass (cannot verify)
    return [
        {'name': name, 'passed': True, 'reason': 'Could not verify - check passed by default'}
        for name in COHERENCE_PENALTY_MAP.keys()
    ]


def apply_coherence_penalties(score_dict, check_results):
    """
    Apply -1 penalty to affected parameters for each failed coherence check.
    If >5 failures: all scores = 0 (disqualified).
    Returns: (modified_scores, failures_count, is_disqualified)
    """
    failures = 0
    for check in check_results:
        if not check.get('passed', True):
            failures += 1
            check_name = check.get('name', '')
            penalty_params = COHERENCE_PENALTY_MAP.get(check_name, [])
            for param in penalty_params:
                if param in score_dict:
                    score_dict[param] = max(0, score_dict[param] - 1)

    is_disqualified = failures > 5
    if is_disqualified:
        for key in score_dict:
            score_dict[key] = 0

    return score_dict, failures, is_disqualified


# ============================================================================
# ATTACHMENT ANALYSIS (unchanged logic, updated field references)
# ============================================================================
ATTACHMENT_ANALYSIS_PROMPT = """You are a STRICT file relevance checker for a student business idea competition called "India Future Tycoon".
Your job is to check whether uploaded files ACTUALLY relate to the idea or not.

IDEA CONTEXT:
================
Title: {title}
Problem: {problem}
Solution: {solution}

UPLOADED FILES:
================
{file_details}

*** CRITICAL INSTRUCTIONS ***
==============================
For EACH file, you MUST follow this exact process:

STEP 1: DESCRIBE what you LITERALLY see/read in the file. Do NOT assume or infer anything from the idea context.
- For images: Describe EXACTLY what objects, text, diagrams, scenes you see. If it's a stock photo, say so.
- For documents: Summarize ONLY what the extracted text actually says.
- For videos: Just note the filename.

STEP 2: JUDGE RELEVANCE - Be STRICT. A file is RELEVANT only if it DIRECTLY and SPECIFICALLY relates to THIS idea's topic/problem/solution.

A file is IRRELEVANT if:
- It shows generic content (stock photos, random landscapes, animals, memes, generic charts)
- It shows content about a DIFFERENT topic than the idea
- It's a random screenshot unrelated to the idea
- It's a generic template with no specific content about this idea
- The connection between the file and the idea is vague or requires stretching logic

DO NOT be lenient. If there's no CLEAR, DIRECT connection to the specific idea, mark it as IRRELEVANT.

RESPONSE FORMAT (STRICT JSON):
{{
    "file_analyses": [
        {{
            "filename": "example.pptx",
            "file_type": "document",
            "summary": "Describe EXACTLY what you see/read in the file content.",
            "is_relevant": true,
            "relevance_note": "If irrelevant: explain what the file actually shows and why it does not match the idea."
        }}
    ],
    "missing_types": ["video"],
    "has_content_mismatch": false
}}

RULES:
- summary: Describe the ACTUAL content you see - NOT what you think it should be
- is_relevant: true ONLY if the file DIRECTLY relates to this specific idea. When in doubt, mark IRRELEVANT.
- relevance_note: If irrelevant, state: "File shows [what it actually shows] which does not relate to [idea topic]"
- missing_types: List file types NOT uploaded (from: "video", "document", "image")
- has_content_mismatch: true if ANY file is irrelevant
"""


def analyze_attachments(submission, client=None):
    """Analyze uploaded attachments - generate per-file summaries and check relevance."""
    if client is None:
        client = OpenRouterClient()

    uploaded_files = list(submission.uploaded_files.all())
    if not uploaded_files:
        return {
            'file_analyses': [],
            'missing_types': ['video', 'document', 'image'],
            'has_content_mismatch': False
        }

    # Build idea context (use new fields with fallback to old)
    title = submission.title or (submission.q2_exact_problem or submission.problem_definition or '')[:100] or 'Untitled'
    problem = submission.q2_exact_problem or submission.problem_definition or submission.problem_statement or ''
    solution_text = submission.q3_solution_simple or submission.solution or submission.proposed_solution or ''

    # Categorize files and build details
    file_details_parts = []
    image_paths = []
    present_types = set()
    videos_with_frames = set()
    gemini_video_analyses = {}

    GEMINI_VIDEO_FORMATS = ('mp4', 'webm', 'mov', 'mpeg', 'mpg')

    for f in uploaded_files:
        present_types.add(f.file_type)
        detail = f"- File: {f.original_filename} (Type: {f.get_file_type_display()})"

        if f.file_type == 'document' and f.extracted_text:
            detail += f"\n  Extracted Text: {f.extracted_text[:500]}"
        elif f.file_type == 'image':
            full_path = os.path.join(settings.MEDIA_ROOT, str(f.file))
            if os.path.exists(full_path):
                image_paths.append(full_path)
                detail += "\n  (Image attached below - describe EXACTLY what you see, do not assume relevance)"
            else:
                detail += "\n  Image file missing from disk - cannot analyze"
        elif f.file_type == 'video':
            full_path = os.path.join(settings.MEDIA_ROOT, str(f.file))
            ext = f.original_filename.lower().split('.')[-1]

            if ext in GEMINI_VIDEO_FORMATS and os.path.exists(full_path):
                try:
                    video_prompt = f"""Analyze this video for relevance to a student's innovation idea.

IDEA CONTEXT:
Title: {title}
Problem: {problem[:500]}
Solution: {solution_text[:500]}

TASK - BE VERY STRICT:
1. Describe what the video shows (scenes, demonstrations, content)
2. Is the video content DIRECTLY and SPECIFICALLY relevant to this exact idea?
3. If the video shows anything unrelated (random footage, stock video, unrelated demo), mark as IRRELEVANT
4. Only mark as relevant if the video CLEARLY demonstrates or explains THIS specific idea

Return JSON:
{{
    "summary": "Detailed description of video content",
    "is_relevant": true or false,
    "relevance_note": "Specific reason why relevant or not"
}}"""

                    print(f"[GEMINI] Analyzing video: {f.original_filename}")
                    video_response = client.generate_video_completion(
                        system_prompt="You are a strict video relevance checker. Be skeptical - only mark videos as relevant if they DIRECTLY and SPECIFICALLY relate to the student's idea.",
                        user_prompt=video_prompt,
                        video_path=full_path,
                        model="google/gemini-2.0-flash-001",
                        max_tokens=800
                    )

                    if video_response and 'content' in video_response:
                        json_match = re.search(r'\{[\s\S]*\}', video_response['content'])
                        if json_match:
                            video_data = json.loads(json_match.group())
                            gemini_video_analyses[f.original_filename] = video_data
                            videos_with_frames.add(f.original_filename)
                            detail += f"\n  [Gemini Analysis]: {video_data.get('summary', 'Video analyzed')[:300]}"
                            if not video_data.get('is_relevant', True):
                                detail += f"\n  IRRELEVANT: {video_data.get('relevance_note', 'Does not match idea')}"
                        else:
                            videos_with_frames.add(f.original_filename)
                            gemini_video_analyses[f.original_filename] = {
                                'summary': video_response['content'][:500],
                                'is_relevant': True,
                                'relevance_note': ''
                            }
                            detail += f"\n  [Gemini Analysis]: {video_response['content'][:300]}"
                except Exception as e:
                    print(f"[GEMINI] Video analysis FAILED for {f.original_filename}: {e}")
                    videos_with_frames.add(f.original_filename)
                    gemini_video_analyses[f.original_filename] = {
                        'summary': f'Video analysis failed: {str(e)[:200]}',
                        'is_relevant': False,
                        'relevance_note': f'Gemini analysis failed ({str(e)[:100]}). Manual review needed.'
                    }
                    detail += f"\n  UNVERIFIED: Gemini analysis failed - {str(e)[:100]}"
            else:
                videos_with_frames.add(f.original_filename)
                if not os.path.exists(full_path):
                    gemini_video_analyses[f.original_filename] = {
                        'summary': 'Video file missing from disk',
                        'is_relevant': False,
                        'relevance_note': 'Video file not found on disk - cannot verify relevance.'
                    }
                    detail += "\n  Video file missing from disk"
                else:
                    gemini_video_analyses[f.original_filename] = {
                        'summary': f'Unsupported video format (.{ext}) - cannot analyze',
                        'is_relevant': False,
                        'relevance_note': f'Video format .{ext} is not supported. Manual review needed.'
                    }
                    detail += f"\n  UNVERIFIED: Unsupported format (.{ext}) - manual review needed"

        file_details_parts.append(detail)

    all_types = {'video', 'document', 'image'}
    missing = list(all_types - present_types)

    file_details = "\n".join(file_details_parts)

    prompt = ATTACHMENT_ANALYSIS_PROMPT.format(
        title=title,
        problem=problem,
        solution=solution_text,
        file_details=file_details
    )

    try:
        response = client.generate_completion(
            system_prompt="You are a strict file relevance checker. Describe EXACTLY what you see. Be skeptical. Return ONLY valid JSON.",
            user_prompt=prompt,
            model="anthropic/claude-3.5-sonnet",
            max_tokens=1000,
            images=image_paths if image_paths else None
        )

        if response and 'content' in response:
            json_match = re.search(r'\{[\s\S]*\}', response['content'])
            if json_match:
                result = json.loads(json_match.group())
                result['missing_types'] = missing
                video_filenames = {f.original_filename for f in uploaded_files if f.file_type == 'video'}
                for analysis in result.get('file_analyses', []):
                    fname = analysis.get('filename')
                    if fname in video_filenames:
                        analysis['video_verified'] = True
                        if fname in gemini_video_analyses:
                            gemini_result = gemini_video_analyses[fname]
                            analysis['summary'] = gemini_result.get('summary', 'Video analyzed')
                            analysis['is_relevant'] = gemini_result.get('is_relevant', True)
                            analysis['relevance_note'] = gemini_result.get('relevance_note', '')
                        else:
                            analysis['is_relevant'] = True
                            analysis['summary'] = analysis.get('summary', 'Video file accepted')
                            analysis['relevance_note'] = ''
                result['has_content_mismatch'] = any(
                    not fa.get('is_relevant', True)
                    for fa in result.get('file_analyses', [])
                )
                return result
    except Exception as e:
        print(f"Attachment analysis failed: {e}")

    return {
        'file_analyses': [
            {
                'filename': f.original_filename,
                'file_type': f.file_type,
                'summary': 'Video file accepted' if f.file_type == 'video' else 'Analysis not available',
                'is_relevant': True,
                'relevance_note': '',
                'video_verified': True if f.file_type == 'video' else None
            } for f in uploaded_files
        ],
        'missing_types': missing,
        'has_content_mismatch': False
    }


# ============================================================================
# MAIN EVALUATION FUNCTION
# ============================================================================
def evaluate_idea(submission: IdeaSubmission, force_reevaluate=False) -> AIEvaluation:
    """
    Evaluate a single idea submission using 10-parameter rubric (0-10 scale).
    Includes 10 coherence cross-checks with -1 penalty per fail. >5 fails = disqualified.
    On re-evaluation: takes the LOWER of old vs new parameter scores.
    """
    if hasattr(submission, 'ai_evaluation') and not force_reevaluate:
        return submission.ai_evaluation

    # Save old scores before deleting (for re-evaluation: take min of old vs new)
    old_scores = None
    if force_reevaluate:
        try:
            old_eval = submission.ai_evaluation
            old_scores = {
                'uniqueness': old_eval.uniqueness_score,
                'ease_of_implementation': old_eval.ease_of_implementation_score,
                'feasibility': old_eval.feasibility_score,
                'impactful': old_eval.impactful_score,
                'sustainable': old_eval.sustainable_score,
                'conceptual_clarity': old_eval.conceptual_clarity_score,
                'empathy': old_eval.empathy_score,
                'creativity': old_eval.creativity_score,
                'communication': old_eval.communication_score,
                'flexible_thinking': old_eval.flexible_thinking_score,
                'is_coherent': old_eval.is_coherent,
            }
            old_eval.delete()
        except AIEvaluation.DoesNotExist:
            pass

    client = OpenRouterClient()

    # Get 12 question answers (with fallback to old fields)
    questions = get_submission_questions(submission)

    # Calculate effort level
    all_text = ' '.join(questions.values())
    total_words = len(all_text.split())
    if total_words < 30:
        effort_note = "VERY LOW EFFORT - Student wrote less than 30 words total. Score VERY strictly."
    elif total_words < 80:
        effort_note = "LOW EFFORT - Student wrote only a few sentences. Answers lack depth. Score strictly."
    elif total_words < 150:
        effort_note = f"MODERATE EFFORT - {total_words} words total. Evaluate based on content quality."
    else:
        effort_note = f"GOOD EFFORT - {total_words} words total. Evaluate based on content quality and depth."

    prompt = EVALUATION_PROMPT.format(
        q1=questions['q1'], q2=questions['q2'], q3=questions['q3'],
        q4=questions['q4'], q5=questions['q5'], q6=questions['q6'],
        q7=questions['q7'], q8=questions['q8'], q9=questions['q9'],
        q10=questions['q10'], q11=questions['q11'], q12=questions['q12'],
        effort_note=effort_note
    )

    # === Run evaluation, coherence checks, and attachment analysis in PARALLEL ===
    has_files = submission.uploaded_files.exists()

    def _run_main_eval():
        return client.generate_completion(
            system_prompt="You are an expert idea evaluator. Return ONLY valid JSON, no other text.",
            user_prompt=prompt,
            model="anthropic/claude-3.5-sonnet",
            max_tokens=2000
        )

    def _run_coherence():
        coherence_client = OpenRouterClient()
        return run_coherence_checks(questions, coherence_client)

    def _run_attachments():
        if not has_files:
            return None
        attachment_client = OpenRouterClient()
        return analyze_attachments(submission, attachment_client)

    with ThreadPoolExecutor(max_workers=3) as executor:
        eval_future = executor.submit(_run_main_eval)
        coherence_future = executor.submit(_run_coherence)
        attachment_future = executor.submit(_run_attachments)

        # Wait for main evaluation
        try:
            response = eval_future.result()
        except Exception as e:
            raise RuntimeError(f"AI API call failed: {str(e)}")

        # Wait for coherence checks
        try:
            check_results = coherence_future.result()
        except Exception:
            check_results = [
                {'name': name, 'passed': True, 'reason': 'Check failed - passed by default'}
                for name in COHERENCE_PENALTY_MAP.keys()
            ]

        # Wait for attachment analysis
        try:
            attachment_result = attachment_future.result()
        except Exception:
            attachment_result = None

    if not response or 'content' not in response:
        raise RuntimeError("AI returned empty or invalid response")

    try:
        eval_data = parse_evaluation_response(response['content'])
    except ValueError as e:
        raise RuntimeError(f"Failed to parse AI response: {str(e)}")

    # Extract scores from parameter_scores array
    scores_map = {p['parameter_name']: p for p in eval_data.get('parameter_scores', [])}

    def get_score(name, old_key=None, default=5):
        param = scores_map.get(name, {})
        new_score = param.get('score', default)
        new_score = max(0, min(10, int(new_score)))  # Clamp to 0-10
        # On re-evaluation: take the LOWER of old vs new
        if old_scores and old_key and old_scores.get('is_coherent', True):
            old_score = old_scores.get(old_key, new_score)
            return min(old_score, new_score)
        return new_score

    def get_reason(name, default=''):
        return scores_map.get(name, {}).get('reason', default)

    # Build score dict for coherence penalty application
    score_dict = {
        'uniqueness': get_score('Uniqueness', 'uniqueness'),
        'ease_of_implementation': get_score('Ease of Implementation', 'ease_of_implementation'),
        'feasibility': get_score('Feasibility', 'feasibility'),
        'impactful': get_score('Impact', 'impactful'),
        'sustainable': get_score('Sustainability', 'sustainable'),
        'conceptual_clarity': get_score('Conceptual Clarity', 'conceptual_clarity'),
        'empathy': get_score('Empathy', 'empathy'),
        'creativity': get_score('Creativity', 'creativity'),
        'communication': get_score('Communication', 'communication'),
        'flexible_thinking': get_score('Flexible Thinking', 'flexible_thinking'),
    }

    # Apply coherence penalties
    score_dict, coherence_failures, is_disqualified = apply_coherence_penalties(score_dict, check_results)
    is_coherent = coherence_failures <= 5

    # === Process attachment results ===
    mismatch_penalty = 0
    mismatch_severity = 'none'
    attachment_mismatch_flag = False
    mismatch_reasons = []
    attachment_summaries = {}

    if not has_files:
        mismatch_penalty = 3
        mismatch_severity = 'missing'
        attachment_mismatch_flag = True
        mismatch_reasons = ['No attachments uploaded with the submission']
        attachment_summaries = {
            'file_analyses': [],
            'missing_types': ['video', 'document', 'image'],
            'has_content_mismatch': False
        }
    else:
        attachment_summaries = attachment_result or {
            'file_analyses': [], 'missing_types': [], 'has_content_mismatch': False
        }
        has_mismatch = attachment_summaries.get('has_content_mismatch', False)

        if has_mismatch:
            irrelevant_files = [
                f for f in attachment_summaries.get('file_analyses', [])
                if not f.get('is_relevant', True)
            ]
            total_files = len(attachment_summaries.get('file_analyses', []))

            mismatch_reasons = [
                f"{f['filename']}: {f.get('relevance_note', 'Content does not match the idea')}"
                for f in irrelevant_files
            ]

            if total_files > 0 and len(irrelevant_files) >= total_files:
                mismatch_severity = 'severe'
                mismatch_penalty = 5
            else:
                mismatch_severity = 'minor'
                mismatch_penalty = 2

            attachment_mismatch_flag = True
        else:
            try:
                ai_summary = submission.ai_summary
                if not ai_summary.is_consistent:
                    reasons = ai_summary.inconsistency_reasons or []
                    mismatch_reasons = reasons
                    file_count = submission.uploaded_files.count()
                    reason_count = len(reasons)
                    if reason_count >= file_count:
                        mismatch_severity = 'severe'
                        mismatch_penalty = 5
                    else:
                        mismatch_severity = 'minor'
                        mismatch_penalty = 2
                    attachment_mismatch_flag = True
            except AISummary.DoesNotExist:
                pass

    # Missing attachment types penalty
    if has_files:
        missing_types = attachment_summaries.get('missing_types', [])
        missing_count = len(missing_types)
        if missing_count > 0:
            missing_penalty = min(missing_count, 2)
            mismatch_penalty += missing_penalty
            attachment_mismatch_flag = True
            if mismatch_severity == 'none':
                mismatch_severity = 'minor'
            for mt in missing_types:
                mismatch_reasons.append(f'Missing attachment type: {mt}')

    # Cap total penalty at -5
    mismatch_penalty = min(mismatch_penalty, 5)

    # === Create evaluation record with all data ===
    evaluation = AIEvaluation.objects.create(
        submission=submission,
        is_coherent=is_coherent,
        coherence_checks={'checks': check_results},
        coherence_failures=coherence_failures,
        is_disqualified=is_disqualified,

        # Idea parameters (after coherence penalties applied)
        uniqueness_score=score_dict['uniqueness'],
        ease_of_implementation_score=score_dict['ease_of_implementation'],
        feasibility_score=score_dict['feasibility'],
        impactful_score=score_dict['impactful'],
        sustainable_score=score_dict['sustainable'],

        # Team parameters (after coherence penalties applied)
        conceptual_clarity_score=score_dict['conceptual_clarity'],
        empathy_score=score_dict['empathy'],
        creativity_score=score_dict['creativity'],
        communication_score=score_dict['communication'],
        flexible_thinking_score=score_dict['flexible_thinking'],

        # Justifications
        uniqueness_justification=get_reason('Uniqueness'),
        ease_of_implementation_justification=get_reason('Ease of Implementation'),
        feasibility_justification=get_reason('Feasibility'),
        impactful_justification=get_reason('Impact'),
        sustainable_justification=get_reason('Sustainability'),
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
        raw_response=response.get('raw_response', ''),

        # Attachment data (set directly instead of separate save)
        attachment_mismatch=attachment_mismatch_flag,
        mismatch_severity=mismatch_severity,
        mismatch_penalty=mismatch_penalty,
        mismatch_reasons=mismatch_reasons,
        attachment_summaries=attachment_summaries,
    )

    # === Step 5: Update submission status ===
    submission.status = 'evaluated'
    if is_disqualified:
        submission.final_category = 'incoherent'
        submission.save(update_fields=['status', 'final_category'])
    else:
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
    Rankings ordered by final_score descending. Disqualified submissions excluded from top 400.
    Top 400 requires score >= 68 (68% of max 100).
    """
    evaluations = AIEvaluation.objects.filter(
        is_disqualified=False
    ).order_by(
        '-final_score',
        '-uniqueness_score',
        '-impactful_score'
    )

    prev_score = None
    prev_rank = None
    for i, evaluation in enumerate(evaluations, start=1):
        if evaluation.final_score == prev_score:
            evaluation.rank = prev_rank
        else:
            evaluation.rank = i
            prev_rank = i
        prev_score = evaluation.final_score
        evaluation.is_top_400 = (evaluation.rank <= 400) and (evaluation.final_score >= 68)
        evaluation.save(update_fields=['rank', 'is_top_400'])

    # Disqualified submissions get no rank
    disqualified = AIEvaluation.objects.filter(is_disqualified=True)
    for evaluation in disqualified:
        evaluation.rank = None
        evaluation.is_top_400 = False
        evaluation.save(update_fields=['rank', 'is_top_400'])

    return evaluations.count()


def get_top_n(n=400):
    """Get top N ranked submissions"""
    update_rankings()
    return AIEvaluation.objects.filter(is_top_400=True).select_related('submission', 'submission__student__user')
