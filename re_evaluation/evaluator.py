"""
Light Evaluator — Scores ideas from short description + attachments only.
Separate from the main evaluator (ai_assistant/evaluator.py).
Uses the same 10-parameter rubric (0-10 scale, max 100) and same OpenRouter client.
"""
import json
import os
import re
from django.conf import settings
from django.utils import timezone
from ai_assistant.openrouter_client import OpenRouterClient


LIGHT_EVALUATION_PROMPT = """You are an Idea Evaluation AI for a SCHOOL STUDENT innovation competition called "India Future Tycoon".
These are school students (ages 13-18), NOT startup founders. Calibrate your expectations accordingly.

You are given a SHORT DESCRIPTION of the idea and possibly some attachments (images/documents/video).
Evaluate the idea using exactly these 10 parameters on a 0-10 scale.

CALIBRATION NOTE: Since you only have a short description, do NOT penalize heavily for missing details.
If the core idea is good, give credit for it. Most student ideas should fall in the 4-7 range.
Only score 0-3 if the idea is genuinely poor or description is meaningless. Score 8-10 for truly outstanding ideas.

PROJECT NAME: {project_name}
IDEA DESCRIPTION: {description}
INDUSTRY: {industry}

{attachment_notes}

SCORING RUBRIC (Rate each 0-10):
==================================

=== IDEA PARAMETERS ===

1. UNIQUENESS (0-10)
   High (8-10): Completely new/unheard idea. No market competitors with similar approach. Clear differentiator.
   Moderate (4-7): Some novelty. A few similar alternatives exist but has distinguishing features.
   Low (0-3): Seems like any existing solution. No visible differentiator.

2. EASE OF IMPLEMENTATION (0-10)
   High (8-10): Clear plan visible. Resources seem available. Practical steps implied.
   Moderate (4-7): Some plan exists but gaps in execution details.
   Low (0-3): No clear plan. Seems unrealistic to execute.

3. FEASIBILITY (0-10)
   High (8-10): Clearly identifies required and available resources with awareness of gaps. Explains how missing resources will be obtained. Phased execution thinking with realistic constraints acknowledged. Solution can begin with simple, low-cost steps. Small-scale testing possible.
   Moderate (4-7): Resources listed but acquisition pathway unclear. Some realism present but optimistic assumptions remain. Logical steps exist but with large jumps in execution. Dependencies underexplored.
   Low (0-3): Assumes resources will automatically appear. Ignores major constraints. Build steps unrealistic for capability. Heavy dependence on unknown external support. No awareness of operational complexity.

4. IMPACT (0-10)
   High (8-10): Widespread benefit with clear evidence of scale. Solution is critical for users AND shows specific data or reasoning for impact.
   Moderate (4-7): Some positive impact visible but limited scope. General claims without specifics.
   Low (0-3): No visible positive difference. Impact claim not supported or exaggerated.
   NOTE: Do not give high scores just because the problem sounds important. The student must show HOW their solution creates impact.

5. SUSTAINABILITY (0-10)
   High (8-10): Solves common problem + lasting value. Long-term viability visible.
   Moderate (4-7): Some sustainability factors present.
   Low (0-3): Won't last. No long-term plan visible.

=== TEAM PARAMETERS ===
NOTE: Infer team qualities from description quality and attachments.
IMPORTANT: Since you only have a short description, give moderate scores (5-6) by default for team parameters unless there is clear evidence of high or low quality. Do NOT score low just because the description is brief.

6. CONCEPTUAL CLARITY (0-10)
   High (8-10): Clear about idea AND execution with specific details. Problem-solution link is crystal clear with no ambiguity.
   Moderate (4-7): Clear about the idea but execution is vague or missing details. Most short descriptions fall here.
   Low (0-3): Unclear about the idea itself. Confusing or contradictory description.
   NOTE: A short but clear description should score 4-5, not higher. Reserve 6+ for descriptions that show both clarity AND depth.

7. EMPATHY (0-10)
   High (8-10): Deep understanding of user pain. Real user needs addressed.
   Moderate (4-7): Some empathy. Generic user understanding.
   Low (0-3): Focused on technology, ignored users and their pains.

8. CREATIVITY (0-10)
   High (8-10): Divergent/out-of-box thinking. Unexpected creative element.
   Moderate (4-7): Good problem-solving but conventional approach.
   Low (0-3): Average approach. Copy of existing solutions.

9. COMMUNICATION (0-10)
   High (8-10): Description is well-structured, persuasive, and engaging. Uses examples. Vision compellingly conveyed.
   Moderate (4-7): Adequate but has gaps. Reader has to work to understand. Grammar issues or unclear flow.
   Low (0-3): Confusing, unclear. Fails to convey the idea.
   NOTE: Simple or short descriptions should score 4-5 max on communication. Only score 6+ if the writing quality is genuinely strong.

10. FLEXIBLE THINKING (0-10)
    High (8-10): Explicitly describes a pivot, iteration, or change based on feedback. Shows concrete evidence of adaptability.
    Moderate (4-7): Mentions willingness to adapt but no specific examples.
    Low (0-3): No mention of adaptability or iteration whatsoever.
    NOTE: This is the hardest parameter to score from a short description. If the description does NOT mention feedback, iteration, or adaptability at all, score 1-2. Do NOT assume flexibility — it must be visible in the text.

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
- These are SCHOOL STUDENTS. Be fair, not harsh. Judge the idea's potential, not just what's written.
- You have LIMITED information (short description only). Give benefit of doubt where the idea concept is sound.
- If the idea is clearly innovative or addresses a real problem, score accordingly even if details are sparse.
- If description is very short, default team parameters to 5-6 (moderate) rather than penalizing.
- If no differentiation mentioned but the idea itself is unique, still give moderate Uniqueness score.
- Reason MUST be one short sentence.
- Do NOT include recommendations or rankings.
"""


GEMINI_VIDEO_FORMATS = ('mp4', 'webm', 'mov', 'mpeg', 'mpg')


def _analyze_video_with_gemini(video_path, filename, project_name, description):
    """Analyze a video file using Gemini 2.0 Flash (same as main system)."""
    client = OpenRouterClient()
    video_prompt = f"""Analyze this video for a student innovation idea competition.

PROJECT: {project_name}
IDEA: {description[:500]}

TASK:
1. Describe what the video shows (scenes, demonstrations, content).
2. How does the video content relate to the idea described above?
3. What additional information does the video provide about the idea?

Return JSON:
{{
    "summary": "Detailed description of video content",
    "relevance": "How the video relates to the idea",
    "key_points": "Key information visible in the video"
}}"""

    try:
        response = client.generate_video_completion(
            system_prompt="You are a video content analyzer. Describe what you see in detail.",
            user_prompt=video_prompt,
            video_path=video_path,
            model="google/gemini-2.0-flash-001",
            max_tokens=800,
        )
        if response and 'content' in response:
            json_match = re.search(r'\{[\s\S]*\}', response['content'])
            if json_match:
                data = json.loads(json_match.group())
                return data.get('summary', '') + ' ' + data.get('relevance', '') + ' ' + data.get('key_points', '')
            return response['content'][:500]
    except Exception as e:
        print(f"[RE-EVAL GEMINI] Video analysis failed for {filename}: {e}")
    return f"Video file uploaded ({filename}) but could not be analyzed."


def evaluate_light_submission(submission):
    """
    Evaluate a LightSubmission using only description + attachments.
    Analyzes images (Claude vision), videos (Gemini), documents (extracted text).
    Returns the updated submission with AI scores filled in.
    """
    client = OpenRouterClient()

    # Collect attachments
    image_paths = []
    attachment_notes_parts = []

    for f in submission.files.all():
        full_path = os.path.join(settings.MEDIA_ROOT, str(f.file))

        if f.file_type == 'image':
            if os.path.exists(full_path):
                image_paths.append(full_path)
                attachment_notes_parts.append(f"- Image: {f.original_filename} (attached below - LOOK at it carefully)")

        elif f.file_type == 'video':
            ext = f.original_filename.lower().split('.')[-1]
            if ext in GEMINI_VIDEO_FORMATS and os.path.exists(full_path):
                # Analyze video with Gemini
                video_analysis = _analyze_video_with_gemini(
                    full_path, f.original_filename,
                    submission.project_name, submission.idea_description,
                )
                attachment_notes_parts.append(
                    f"- Video: {f.original_filename}\n  [Video Analysis by Gemini]: {video_analysis}"
                )
            else:
                attachment_notes_parts.append(f"- Video: {f.original_filename} (format not supported for analysis)")

        elif f.file_type == 'document':
            # Check if extracted text exists (from UploadedFile model pattern)
            text_preview = ''
            if hasattr(f, 'extracted_text') and f.extracted_text:
                text_preview = f.extracted_text[:500]
            if text_preview:
                attachment_notes_parts.append(
                    f"- Document: {f.original_filename}\n  Extracted Text: {text_preview}"
                )
            else:
                attachment_notes_parts.append(f"- Document: {f.original_filename}")

    if attachment_notes_parts:
        attachment_notes = "UPLOADED ATTACHMENTS:\n" + "\n".join(attachment_notes_parts)
    else:
        attachment_notes = "NO ATTACHMENTS UPLOADED."

    prompt = LIGHT_EVALUATION_PROMPT.format(
        project_name=submission.project_name,
        description=submission.idea_description,
        industry=submission.industry or 'Not specified',
        attachment_notes=attachment_notes,
    )

    response = client.generate_completion(
        system_prompt="You are an expert idea evaluator. Return ONLY valid JSON, no other text.",
        user_prompt=prompt,
        model="anthropic/claude-sonnet-4",
        max_tokens=2000,
        images=image_paths if image_paths else None,
    )

    if not response or 'content' not in response:
        raise RuntimeError("AI returned empty or invalid response")

    # Parse JSON
    json_match = re.search(r'\{[\s\S]*\}', response['content'])
    if not json_match:
        raise RuntimeError(f"Could not parse AI response as JSON: {response['content'][:200]}")

    eval_data = json.loads(json_match.group())
    if 'parameter_scores' not in eval_data:
        raise RuntimeError("AI response missing parameter_scores")

    # Map scores
    scores_map = {p['parameter_name']: p for p in eval_data.get('parameter_scores', [])}

    def get_score(name):
        return max(0, min(10, int(scores_map.get(name, {}).get('score', 0))))

    def get_reason(name):
        return scores_map.get(name, {}).get('reason', '')

    # Fill scores
    submission.uniqueness_score = get_score('Uniqueness')
    submission.ease_of_implementation_score = get_score('Ease of Implementation')
    submission.feasibility_score = get_score('Feasibility')
    submission.impactful_score = get_score('Impact')
    submission.sustainable_score = get_score('Sustainability')
    submission.conceptual_clarity_score = get_score('Conceptual Clarity')
    submission.empathy_score = get_score('Empathy')
    submission.creativity_score = get_score('Creativity')
    submission.communication_score = get_score('Communication')
    submission.flexible_thinking_score = get_score('Flexible Thinking')

    # Fill justifications
    submission.uniqueness_justification = get_reason('Uniqueness')
    submission.ease_of_implementation_justification = get_reason('Ease of Implementation')
    submission.feasibility_justification = get_reason('Feasibility')
    submission.impactful_justification = get_reason('Impact')
    submission.sustainable_justification = get_reason('Sustainability')
    submission.conceptual_clarity_justification = get_reason('Conceptual Clarity')
    submission.empathy_justification = get_reason('Empathy')
    submission.creativity_justification = get_reason('Creativity')
    submission.communication_justification = get_reason('Communication')
    submission.flexible_thinking_justification = get_reason('Flexible Thinking')
    submission.overall_justification = eval_data.get('overall_justification', '')

    # Metadata
    submission.ai_confidence = eval_data.get('confidence', 'medium')
    submission.ai_model_used = response.get('model', 'anthropic/claude-sonnet-4')
    submission.ai_raw_response = response.get('raw_response', '')
    submission.is_evaluated = True
    submission.evaluated_at = timezone.now()

    submission.save()
    return submission
