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


LIGHT_EVALUATION_PROMPT = """You are a STRICT Idea Evaluation AI for a student innovation competition called "India Future Tycoon".
You must be RIGOROUS - this is a competition, and only truly strong ideas should score high.

You are given a SHORT DESCRIPTION of the idea and possibly some attachments (images/documents/video).
Evaluate the idea using exactly these 10 parameters on a 0-10 scale.

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
   High (8-10): Resources realistically available. Plan is practical.
   Moderate (4-7): Partially realistic. Some constraints visible.
   Low (0-3): Unrealistic. No awareness of real constraints.

4. IMPACT (0-10)
   High (8-10): Widespread benefit. Solution is critical for users. Shows scale of impact.
   Moderate (4-7): Some positive impact visible but limited scope.
   Low (0-3): No visible positive difference. Impact claim not supported.

5. SUSTAINABILITY (0-10)
   High (8-10): Solves common problem + lasting value. Long-term viability visible.
   Moderate (4-7): Some sustainability factors present.
   Low (0-3): Won't last. No long-term plan visible.

=== TEAM PARAMETERS ===
NOTE: Infer team qualities from description quality and attachments.

6. CONCEPTUAL CLARITY (0-10)
   High (8-10): Clear about idea AND how it works. Problem-solution link is crystal clear.
   Moderate (4-7): Clear about idea but execution is vague.
   Low (0-3): Unclear about the idea itself. Confusing description.

7. EMPATHY (0-10)
   High (8-10): Deep understanding of user pain. Real user needs addressed.
   Moderate (4-7): Some empathy. Generic user understanding.
   Low (0-3): Focused on technology, ignored users and their pains.

8. CREATIVITY (0-10)
   High (8-10): Divergent/out-of-box thinking. Unexpected creative element.
   Moderate (4-7): Good problem-solving but conventional approach.
   Low (0-3): Average approach. Copy of existing solutions.

9. COMMUNICATION (0-10)
   High (8-10): Description is clear, concise. Vision effectively conveyed.
   Moderate (4-7): Adequate but has gaps. Reader has to work to understand.
   Low (0-3): Confusing, unclear. Fails to convey the idea.

10. FLEXIBLE THINKING (0-10)
    High (8-10): Shows awareness that idea may evolve. Mentions adaptability.
    Moderate (4-7): Some flexibility visible.
    Low (0-3): No mention of adaptability. Appears closed to iteration.

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
- High scores (8-10) should be RARE (top 5% quality).
- You have LIMITED information (short description only). Score based on what is available.
- If description is vague or generic, score LOW on Conceptual Clarity and Communication.
- If no differentiation mentioned, Uniqueness should be LOW.
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
        model="anthropic/claude-3.5-sonnet",
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
    submission.ai_model_used = response.get('model', 'anthropic/claude-3.5-sonnet')
    submission.ai_raw_response = response.get('raw_response', '')
    submission.is_evaluated = True
    submission.evaluated_at = timezone.now()

    submission.save()
    return submission
