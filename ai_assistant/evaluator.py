"""
AI Idea Evaluator - Scores submissions using 10-parameter jury rubric (1-5 scale each).
"""
import json
import os
import re
from django.conf import settings
from .openrouter_client import OpenRouterClient
from .models import AIEvaluation, AISummary
from students.models import IdeaSubmission


# 10-parameter evaluation prompt based on jury rubric (exact sheet descriptions)
EVALUATION_PROMPT = """You are a STRICT Idea Evaluation AI for a student innovation competition called "India Future Tycoon".
You must be RIGOROUS - this is a competition, and only truly strong ideas should score high.
Evaluate the submitted idea using exactly these 10 parameters on a 1-5 scale.

IDEA SUBMISSION (8 Questions):
===============================
Title: {title}
Q1 - Problem Definition: {problem_statement}
Q2 - Detailed Description: {problem_description}
Q3 - Target User Group: {target_users}
Q4 - Problem Urgency: {problem_urgency}
Q5 - Proposed Solution: {proposed_solution}
Q6 - Solution Benefits: {solution_benefits}
Q7 - Why Best Equipped: {why_best_equipped}
Q8 - Idea Stage: {idea_stage}

SUBMISSION EFFORT: {effort_note}

*** CRITICAL: COHERENCE CHECK (DO THIS FIRST) ***
==================================================
Before scoring, check if ALL fields are talking about the SAME idea:
1. Does the Problem Statement describe ONE clear problem?
2. Does the Proposed Solution DIRECTLY address that specific problem?
3. Are the Target Users the people who would face that specific problem?
4. Do all fields logically connect and make sense together?

If the submission is INCOHERENT (fields seem to be from different ideas, unrelated, or contradictory):
- Set "is_coherent": false in your response
- Give score of 0 to ALL parameters (incoherent submissions get zero marks)
- In overall_justification, clearly state: "INCOHERENT SUBMISSION: The fields do not relate to each other and appear to be from different ideas."

Only if the submission IS coherent, proceed with normal evaluation.

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
    "is_coherent": <true/false>,
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
- Score MUST be integer 0-5 (0 ONLY for incoherent submissions, otherwise 1-5)
- Higher score = BETTER (5 is best, 1 is worst)
- Be STRICT and RIGOROUS. This is a national competition - only truly exceptional ideas deserve 5, and only well-articulated ideas deserve 4.
- Score 5 should be RARE (top 5% quality). Score 4 = strong. Score 3 = average. Score 2 = below average. Score 1 = poor.
- If the student gave vague, short, or generic answers, score LOW. Effort and depth matter.
- Generic ideas (e.g. "make an app to solve X") without clear differentiation should score 1-2 on Uniqueness and Creativity.
- If the student does NOT explain WHY their solution is better than alternatives, Uniqueness and Impact should be LOW.
- If the student does NOT show understanding of user pain points with specific examples, Empathy should be LOW.
- If there is no mention of adaptability, iteration, or willingness to learn, Flexible Thinking MUST be 1-2.
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
- For images: Describe EXACTLY what objects, text, diagrams, scenes you see. If it's a stock photo, say so. If it's a screenshot of something unrelated, say so.
- For documents: Summarize ONLY what the extracted text actually says.
- For videos: Just note the filename.

STEP 2: JUDGE RELEVANCE - Be STRICT. A file is RELEVANT only if it DIRECTLY and SPECIFICALLY relates to THIS idea's topic/problem/solution.

A file is IRRELEVANT if:
- It shows generic content (stock photos, random landscapes, animals, memes, generic charts)
- It shows content about a DIFFERENT topic than the idea
- It's a random screenshot unrelated to the idea
- It's a generic template with no specific content about this idea
- The connection between the file and the idea is vague or requires stretching logic
- It contains content about a completely different domain/subject

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
- For video files: If video frames are provided below, analyze the VISUAL CONTENT of those frames to determine relevance. Describe what you see in the frames. If frames show content related to the idea, mark RELEVANT. If frames show unrelated content, mark IRRELEVANT.
- If video frames could NOT be extracted (stated in file details), mark as RELEVANT by default since content is unverifiable.
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

    # Build idea context
    title = submission.title or (submission.problem_definition or '')[:100] or 'Untitled'
    problem = submission.problem_definition or submission.problem_statement or ''
    solution_text = submission.solution or submission.proposed_solution or ''

    # Categorize files and build details
    file_details_parts = []
    image_paths = []
    present_types = set()
    videos_with_frames = set()  # filenames of videos that were analyzed
    gemini_video_analyses = {}  # Store Gemini analysis results {filename: analysis}
    
    # Gemini-supported video formats
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
                detail += "\n  ⚠️ Image file missing from disk - cannot analyze"
        elif f.file_type == 'video':
            full_path = os.path.join(settings.MEDIA_ROOT, str(f.file))
            ext = f.original_filename.lower().split('.')[-1]
            
            if ext in GEMINI_VIDEO_FORMATS and os.path.exists(full_path):
                # Use Gemini for native video analysis
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
                        system_prompt="You are a strict video relevance checker. Be skeptical - only mark videos as relevant if they DIRECTLY and SPECIFICALLY relate to the student's idea. Random or generic videos should be marked IRRELEVANT.",
                        user_prompt=video_prompt,
                        video_path=full_path,
                        model="google/gemini-2.0-flash-001",
                        max_tokens=800
                    )
                    
                    if video_response and 'content' in video_response:
                        print(f"[GEMINI] Raw response: {video_response['content'][:500]}")
                        json_match = re.search(r'\{[\s\S]*\}', video_response['content'])
                        if json_match:
                            video_data = json.loads(json_match.group())
                            print(f"[GEMINI] Parsed: is_relevant={video_data.get('is_relevant')}, summary={video_data.get('summary', '')[:100]}")
                            gemini_video_analyses[f.original_filename] = video_data
                            videos_with_frames.add(f.original_filename)
                            detail += f"\n  [Gemini Analysis]: {video_data.get('summary', 'Video analyzed')[:300]}"
                            # If video is irrelevant, add to detail
                            if not video_data.get('is_relevant', True):
                                detail += f"\n  ⚠️ IRRELEVANT: {video_data.get('relevance_note', 'Does not match idea')}"
                        else:
                            print(f"[GEMINI] Could not parse JSON from response")
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
                        'relevance_note': f'Gemini analysis failed ({str(e)[:100]}). Video could not be verified - manual review needed.'
                    }
                    detail += f"\n  ⚠️ UNVERIFIED: Gemini analysis failed - {str(e)[:100]}"
            else:
                # Unsupported format or file not found - mark as unverified
                videos_with_frames.add(f.original_filename)
                if not os.path.exists(full_path):
                    gemini_video_analyses[f.original_filename] = {
                        'summary': 'Video file missing from disk',
                        'is_relevant': False,
                        'relevance_note': 'Video file not found on disk - cannot verify relevance.'
                    }
                    detail += "\n  ⚠️ Video file missing from disk"
                else:
                    gemini_video_analyses[f.original_filename] = {
                        'summary': f'Unsupported video format (.{ext}) - cannot analyze',
                        'is_relevant': False,
                        'relevance_note': f'Video format .{ext} is not supported for analysis. Manual review needed.'
                    }
                    detail += f"\n  ⚠️ UNVERIFIED: Unsupported format (.{ext}) - manual review needed"

        file_details_parts.append(detail)

    # Determine missing types
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
            system_prompt="You are a strict file relevance checker. Describe EXACTLY what you see in each file. For video files, analyze the extracted frames carefully. Do NOT assume files are relevant just because they were uploaded with the idea. Be skeptical - if you cannot see a DIRECT, SPECIFIC connection to the idea, mark it IRRELEVANT. Return ONLY valid JSON.",
            user_prompt=prompt,
            model="anthropic/claude-3.5-sonnet",
            max_tokens=1000,
            images=image_paths if image_paths else None
        )

        if response and 'content' in response:
            json_match = re.search(r'\{[\s\S]*\}', response['content'])
            if json_match:
                result = json.loads(json_match.group())
                # Ensure missing_types is accurate
                result['missing_types'] = missing
                # Post-process video files - use Gemini analysis results
                video_filenames = {f.original_filename for f in uploaded_files if f.file_type == 'video'}
                for analysis in result.get('file_analyses', []):
                    fname = analysis.get('filename')
                    if fname in video_filenames:
                        # All videos are now verified (analyzed by Gemini or accepted)
                        analysis['video_verified'] = True
                        # Use Gemini analysis results if available
                        if fname in gemini_video_analyses:
                            gemini_result = gemini_video_analyses[fname]
                            analysis['summary'] = gemini_result.get('summary', 'Video analyzed')
                            analysis['is_relevant'] = gemini_result.get('is_relevant', True)
                            analysis['relevance_note'] = gemini_result.get('relevance_note', '')
                        else:
                            # Fallback - mark as relevant
                            analysis['is_relevant'] = True
                            analysis['summary'] = analysis.get('summary', 'Video file accepted')
                            analysis['relevance_note'] = ''
                # Recalculate has_content_mismatch
                result['has_content_mismatch'] = any(
                    not fa.get('is_relevant', True)
                    for fa in result.get('file_analyses', [])
                )
                return result
    except Exception as e:
        print(f"Attachment analysis failed: {e}")

    # Fallback - return basic info (all videos marked as verified)
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


def evaluate_idea(submission: IdeaSubmission, force_reevaluate=False) -> AIEvaluation:
    """
    Evaluate a single idea submission using 10-parameter jury rubric.
    On re-evaluation: reuses attachment analysis (files don't change) and
    takes the LOWER of old vs new parameter scores to prevent score inflation.
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
                'scalable': old_eval.scalable_score,
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

    # Build prompt with ALL 8 submission fields
    problem_definition = submission.problem_definition or ''
    problem_description = submission.problem_description or ''
    target_users = submission.target_user_group or ''
    problem_urgency = submission.problem_urgency or ''
    proposed_solution = submission.solution or ''
    solution_benefits = submission.solution_benefits or ''
    why_best_equipped = submission.why_best_equipped or ''
    idea_stage = submission.get_idea_stage_display() if submission.idea_stage else 'Idea'

    # Calculate effort level based on total content length
    all_text = f"{problem_definition} {problem_description} {target_users} {problem_urgency} {proposed_solution} {solution_benefits} {why_best_equipped}"
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
        title=submission.title or problem_definition[:100],
        problem_statement=problem_definition,
        problem_description=problem_description,
        proposed_solution=proposed_solution,
        target_users=target_users,
        problem_urgency=problem_urgency,
        solution_benefits=solution_benefits,
        why_best_equipped=why_best_equipped,
        idea_stage=idea_stage,
        effort_note=effort_note
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
    
    # Check coherence status from AI response
    is_coherent = eval_data.get('is_coherent', True)

    def get_score(name, old_key=None, default=3):
        if not is_coherent:
            return 0  # Incoherent submissions get 0 marks
        param = scores.get(name, {})
        new_score = param.get('score', default)
        new_score = max(1, min(5, int(new_score)))  # Clamp to 1-5
        # On re-evaluation: take the LOWER of old vs new to prevent score inflation
        if old_scores and old_key and old_scores.get('is_coherent', True):
            old_score = old_scores.get(old_key, new_score)
            return min(old_score, new_score)
        return new_score

    def get_reason(name, default=''):
        return scores.get(name, {}).get('reason', default)

    evaluation = AIEvaluation.objects.create(
        submission=submission,
        is_coherent=is_coherent,

        # Idea parameters
        uniqueness_score=get_score('Uniqueness', 'uniqueness'),
        ease_of_implementation_score=get_score('Ease of Implementation', 'ease_of_implementation'),
        scalable_score=get_score('Scalable', 'scalable'),
        impactful_score=get_score('Impactful', 'impactful'),
        sustainable_score=get_score('Sustainable', 'sustainable'),

        # Team parameters
        conceptual_clarity_score=get_score('Conceptual Clarity', 'conceptual_clarity'),
        empathy_score=get_score('Empathy', 'empathy'),
        creativity_score=get_score('Creativity', 'creativity'),
        communication_score=get_score('Communication', 'communication'),
        flexible_thinking_score=get_score('Flexible Thinking', 'flexible_thinking'),
        
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

    # === Attachment Analysis & Content Mismatch Penalty ===
    # ALWAYS run fresh attachment analysis (Gemini now handles videos natively)
    mismatch_penalty = 0
    mismatch_severity = 'none'
    attachment_mismatch_flag = False
    mismatch_reasons = []
    attachment_summaries = {}

    has_files = submission.uploaded_files.exists()

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
        attachment_summaries = analyze_attachments(submission, client)

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

    # === Missing Attachment Types Penalty ===
    # -1 per missing type (max -2, since no-files case is already -3)
    if has_files:
        missing_types = attachment_summaries.get('missing_types', [])
        missing_count = len(missing_types)
        if missing_count > 0:
            missing_penalty = min(missing_count, 2)  # -1 per missing type, max -2
            mismatch_penalty += missing_penalty
            attachment_mismatch_flag = True
            if mismatch_severity == 'none':
                mismatch_severity = 'minor'
            for mt in missing_types:
                mismatch_reasons.append(f'Missing attachment type: {mt}')

    # Cap total penalty at -5
    mismatch_penalty = min(mismatch_penalty, 5)

    evaluation.attachment_mismatch = attachment_mismatch_flag
    evaluation.mismatch_severity = mismatch_severity
    evaluation.mismatch_penalty = mismatch_penalty
    evaluation.mismatch_reasons = mismatch_reasons
    evaluation.attachment_summaries = attachment_summaries
    evaluation.save()

    submission.status = 'evaluated'
    if not is_coherent:
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
