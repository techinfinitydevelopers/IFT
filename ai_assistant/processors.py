"""
AI Processing Module for IFT Platform

Uses Claude 3.5 Sonnet with Vision for analyzing:
- Text content (ideas, PDFs, DOCX)
- Images (direct vision)
- Videos (frame extraction → vision)
"""

import json
import logging
import os
import tempfile
from django.conf import settings
from .openrouter_client import OpenRouterClient
from .models import AISummary
from .file_extractors import extract_text_from_file

logger = logging.getLogger(__name__)

# Model Configuration
MODELS = {
    'default': 'anthropic/claude-3.5-sonnet',
    'premium': 'anthropic/claude-3-opus',
}


def extract_video_frames(video_path, num_frames=3):
    """
    Extract key frames from video for Claude Vision analysis.
    Returns list of temporary image paths.
    """
    try:
        import cv2
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning(f"Could not open video: {video_path}")
            return []
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames == 0:
            return []
        
        # Get frames at 25%, 50%, 75% of video
        frame_positions = [int(total_frames * p) for p in [0.25, 0.5, 0.75]]
        
        extracted_frames = []
        temp_dir = tempfile.gettempdir()
        
        for i, pos in enumerate(frame_positions[:num_frames]):
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            ret, frame = cap.read()
            if ret:
                frame_path = os.path.join(temp_dir, f"video_frame_{i}_{os.path.basename(video_path)}.jpg")
                cv2.imwrite(frame_path, frame)
                extracted_frames.append(frame_path)
        
        cap.release()
        return extracted_frames
        
    except ImportError:
        logger.warning("OpenCV not installed - video frame extraction disabled")
        return []
    except Exception as e:
        logger.error(f"Video frame extraction failed: {e}")
        return []


def validate_submission(submission):
    """Validate if submission is complete"""
    missing = []
    if not submission.problem_definition or len(submission.problem_definition.strip()) < 10:
        missing.append("Problem Definition too short")
    if not submission.solution or len(submission.solution.strip()) < 10:
        missing.append("Solution too short")
    return len(missing) == 0, "; ".join(missing) if missing else "Complete"


def generate_summary(submission, use_premium_model=False):
    """
    Generate AI summary using Claude Vision.
    - Images: Sent directly to Claude
    - Videos: Frames extracted and sent to Claude
    - Documents: Text extracted and sent
    """
    model = MODELS['premium'] if use_premium_model else MODELS['default']
    client = OpenRouterClient()
    
    system_prompt = """You are analyzing a student's idea submission.
Be factual and neutral. Analyze all content including images and video frames.
Describe what you see in each image/video frame.
Check if uploaded files match the idea description.
If they don't match, explain exactly what the image/video shows vs what the idea is about."""
    
    # Compile idea text using the 8 new questions
    idea_text = f"""STUDENT IDEA SUBMISSION:
1. Problem: {submission.problem_definition}
2. Details: {submission.problem_description}
3. Target: {submission.target_user_group}
4. Urgency: {submission.problem_urgency}
5. Solution: {submission.solution}
6. Benefits: {submission.solution_benefits}
7. Team/Why: {submission.why_best_equipped}
8. Stage: {submission.get_idea_stage_display()}"""
    
    # Collect files for analysis
    image_paths = []
    file_descriptions = []
    temp_frames = []  # Track temp files for cleanup
    
    for f in submission.uploaded_files.all():
        file_path = os.path.join(settings.MEDIA_ROOT, str(f.file))
        ext = f.original_filename.lower().split('.')[-1]
        
        if not os.path.exists(file_path):
            continue
        
        # Images - send directly to Claude
        if ext in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
            image_paths.append(file_path)
            file_descriptions.append(f"[IMAGE: {f.original_filename}] - Attached for visual analysis")
        
        # Videos - extract frames
        elif ext in ('mp4', 'mov', 'avi', 'webm', 'mkv'):
            frames = extract_video_frames(file_path, num_frames=3)
            if frames:
                image_paths.extend(frames)
                temp_frames.extend(frames)
                file_descriptions.append(f"[VIDEO: {f.original_filename}] - 3 frames extracted for analysis")
            else:
                file_descriptions.append(f"[VIDEO: {f.original_filename}] - Could not extract frames")
        
        # Documents - extract text
        elif ext in ('pdf', 'docx', 'pptx', 'txt'):
            try:
                text = extract_text_from_file(file_path, 'document', f.original_filename)
                if text:
                    f.extracted_text = text
                    f.save(update_fields=['extracted_text'])
                    file_descriptions.append(f"[DOC: {f.original_filename}]\n{text[:1200]}")
            except Exception as e:
                file_descriptions.append(f"[DOC: {f.original_filename}] - Extraction failed")
    
    # Count images for prompt
    num_images = len(image_paths)
    
    user_prompt = f"""{idea_text}

UPLOADED FILES:
{chr(10).join(file_descriptions) if file_descriptions else "No files uploaded"}

{f"[{num_images} images/frames attached for visual analysis]" if num_images > 0 else ""}

YOUR TASK:
1. Generate a SHORT TITLE for this idea (5-8 words, catchy and descriptive)
2. Summarize the idea in 2-3 sentences
3. For EACH image/video frame: Describe what you see in detail
4. CONSISTENCY CHECK: Do the images/videos relate to the idea?
   - If YES: Note they support the idea
   - If NO: Explain exactly what the image shows vs what the idea is about
   Example: "Image shows a beach/ocean scene, but the idea is about education technology - this appears unrelated"
5. Suggest category tags

Return JSON:
{{
    "title": "Short catchy title for the idea (5-8 words)",
    "summary": "2-3 sentence idea summary",
    "tags": ["tag1", "tag2"],
    "file_summaries": {{
        "filename.jpg": "Detailed description of what this image shows",
        "video.mp4": "Description of what the video frames show"
    }},
    "is_consistent": true or false,
    "inconsistency_reasons": ["Specific reason why each file doesn't match, describing what it shows"]
}}"""

    
    try:
        response = client.generate_completion(
            system_prompt, 
            user_prompt, 
            model=model, 
            max_tokens=1200,
            images=image_paths if image_paths else None
        )
        
        content = response['content'].strip()
        
        # Parse JSON
        try:
            if '{' in content:
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                ai_data = json.loads(content[json_start:json_end])
            else:
                raise ValueError("No JSON found in AI response")
        except (json.JSONDecodeError, ValueError) as parse_err:
            logger.warning(f"AI response JSON parse failed: {parse_err}")
            ai_data = {
                "summary": f"[Parse error - raw response] {content[:400]}",
                "tags": ["Other"],
                "file_summaries": {},
                "is_consistent": False,
                "inconsistency_reasons": ["AI response could not be parsed - needs manual review"]
            }
        
        is_complete, notes = validate_submission(submission)
        
        # Save AI summary
        ai_summary, _ = AISummary.objects.update_or_create(
            submission=submission,
            defaults={
                'summary': ai_data.get('summary', 'Summary unavailable'),
                'suggested_tags': ai_data.get('tags', []),
                'file_summaries': ai_data.get('file_summaries', {}),
                'is_consistent': ai_data.get('is_consistent', True),
                'inconsistency_reasons': ai_data.get('inconsistency_reasons', []),
                'is_complete': is_complete,
                'completeness_notes': notes,
                'model_used': response['model'],
                'tokens_used': response['tokens'],
                'processing_time': response['time'],
                'raw_response': response['raw_response']
            }
        )
        
        # Update category
        if ai_data.get('tags'):
            cat_map = {
                'EdTech': 'edtech', 'Sustainability': 'sustainability',
                'Health': 'health', 'FinTech': 'fintech', 
                'Social Impact': 'social_impact', 'Agriculture': 'agriculture',
                'Technology': 'technology', 'Entertainment': 'entertainment'
            }
            submission.ai_suggested_category = cat_map.get(ai_data['tags'][0], 'other')
            if not submission.final_category:
                submission.final_category = submission.ai_suggested_category
        
        # Auto-generate title from AI if not already set
        if ai_data.get('title') and not submission.title:
            submission.title = ai_data['title'][:300]  # Limit to field max length
        
        submission.ai_processed = True
        submission.ai_processing_error = ""
        submission.save()

        
        return ai_summary
        
    except Exception as e:
        logger.error(f"AI failed: {e}")
        submission.ai_processing_error = str(e)
        submission.save()
        
        ai_summary, _ = AISummary.objects.update_or_create(
            submission=submission,
            defaults={
                'summary': f'AI processing failed: {str(e)[:100]}',
                'model_used': model,
            }
        )
        return ai_summary
        
    finally:
        # Cleanup temp video frames
        for frame_path in temp_frames:
            try:
                if os.path.exists(frame_path):
                    os.remove(frame_path)
            except:
                pass


def regenerate_summary_premium(submission):
    """Use premium model (Claude Opus)"""
    return generate_summary(submission, use_premium_model=True)
