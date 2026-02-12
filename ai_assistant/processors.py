"""
AI Processing Module for IFT Platform

Hybrid AI Approach:
- Claude 3.5 Sonnet: Text content, PDFs, DOCX, Images
- Gemini 1.5 Flash: Native video analysis (full video understanding)
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

# Model Configuration - Hybrid approach
MODELS = {
    'default': 'anthropic/claude-3.5-sonnet',    # Text + Images
    'video': 'google/gemini-2.0-flash-001',       # Native video analysis
    'premium': 'anthropic/claude-3-opus',
}

# Supported video formats for Gemini
GEMINI_VIDEO_FORMATS = ('mp4', 'webm', 'mov', 'mpeg', 'mpg')


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
    problem = submission.q2_exact_problem or submission.problem_definition or ''
    if len(problem.strip()) < 10:
        missing.append("Problem description too short")
    solution = submission.q3_solution_simple or submission.solution or ''
    if len(solution.strip()) < 10:
        missing.append("Solution too short")
    return len(missing) == 0, "; ".join(missing) if missing else "Complete"


def analyze_video_with_gemini(video_path, filename, idea_context, client):
    """
    Analyze video using Gemini 1.5 Flash for native video understanding.
    Returns video analysis dict or None if failed.
    """
    video_system_prompt = """You are analyzing a video from a student's innovation idea submission.
Watch the entire video carefully and provide detailed analysis.
Describe what you see, any demonstrations, prototypes, or presentations shown."""

    video_prompt = f"""IDEA CONTEXT:
Problem: {idea_context.get('problem', 'Not provided')}
Solution: {idea_context.get('solution', 'Not provided')}

TASK - Analyze this video:
1. Describe what the video shows (scenes, demonstrations, content)
2. Does the video support/relate to the student's idea?
3. If it shows a prototype or demo, describe what it demonstrates
4. Note any important text, diagrams, or visuals in the video
5. Describe any audio/speech content if present

Return JSON:
{{
    "video_description": "Detailed description of what the video shows",
    "supports_idea": true or false,
    "key_observations": ["observation1", "observation2", "observation3"],
    "audio_content": "Description of any speech or audio if present",
    "inconsistency_reason": "If video doesn't support idea, explain why"
}}"""

    try:
        response = client.generate_video_completion(
            video_system_prompt,
            video_prompt,
            video_path,
            model=MODELS['video'],
            max_tokens=1000
        )
        
        content = response['content'].strip()
        
        # Parse JSON response
        if '{' in content:
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            video_data = json.loads(content[json_start:json_end])
            
            return {
                'filename': filename,
                'description': video_data.get('video_description', 'Video analyzed'),
                'supports_idea': video_data.get('supports_idea', True),
                'key_observations': video_data.get('key_observations', []),
                'audio_content': video_data.get('audio_content', ''),
                'inconsistency_reason': video_data.get('inconsistency_reason', ''),
                'model_used': response.get('model', MODELS['video']),
                'tokens': response.get('tokens', 0),
            }
        else:
            return {
                'filename': filename,
                'description': content[:500],
                'supports_idea': True,
                'key_observations': [],
                'model_used': response.get('model', MODELS['video']),
            }
            
    except Exception as e:
        logger.error(f"Gemini video analysis failed for {filename}: {e}")
        return None


def generate_summary(submission, use_premium_model=False):
    """
    Generate AI summary using hybrid approach:
    - Claude 3.5 Sonnet: Text content, images, documents
    - Gemini 1.5 Flash: Native video analysis (full video understanding)
    """
    model = MODELS['premium'] if use_premium_model else MODELS['default']
    client = OpenRouterClient()
    
    system_prompt = """You are analyzing a student's idea submission.
Be factual and neutral. Analyze all content including images.
Describe what you see in each image.
Check if uploaded files match the idea description.
If they don't match, explain exactly what the image shows vs what the idea is about."""
    
    # Compile idea text using the 12 v3 questions (with fallback to v2)
    idea_text = f"""STUDENT IDEA SUBMISSION:
1. Target Group: {submission.q1_target_group or submission.target_user_group or 'N/A'}
2. Exact Problem: {submission.q2_exact_problem or submission.problem_definition or 'N/A'}
3. Solution (Simple): {submission.q3_solution_simple or submission.solution or 'N/A'}
4. Differentiation: {submission.q4_differentiation or 'N/A'}
5. Build Steps: {submission.q5_build_steps or 'N/A'}
6. Resources: {submission.q6_resources or 'N/A'}
7. Positive Change: {submission.q7_positive_change or submission.solution_benefits or 'N/A'}
8. Challenges: {submission.q8_challenges or 'N/A'}
9. Team Fit: {submission.q9_team_fit or submission.why_best_equipped or 'N/A'}
10. Feedback: {submission.q10_feedback or 'N/A'}
11. Creative Element: {submission.q11_creative_element or 'N/A'}
12. Pitch: {submission.q12_pitch or 'N/A'}"""

    # Context for video analysis
    idea_context = {
        'problem': submission.q2_exact_problem or submission.problem_definition or '',
        'solution': submission.q3_solution_simple or submission.solution or '',
    }
    
    # Collect files for analysis - HYBRID APPROACH
    image_paths = []
    file_descriptions = []
    video_analyses = []  # Store Gemini video analysis results
    temp_frames = []  # Track temp files for cleanup (fallback only)
    
    for f in submission.uploaded_files.all():
        file_path = os.path.join(settings.MEDIA_ROOT, str(f.file))
        ext = f.original_filename.lower().split('.')[-1]
        
        if not os.path.exists(file_path):
            continue
        
        # Images - send directly to Claude
        if ext in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
            image_paths.append(file_path)
            file_descriptions.append(f"[IMAGE: {f.original_filename}] - Attached for visual analysis")
        
        # Videos - Use Gemini for native video analysis
        elif ext in GEMINI_VIDEO_FORMATS:
            logger.info(f"Analyzing video with Gemini: {f.original_filename}")
            video_result = analyze_video_with_gemini(file_path, f.original_filename, idea_context, client)
            
            if video_result:
                video_analyses.append(video_result)
                # Add video analysis to file descriptions for Claude's context
                desc = video_result.get('description', 'Video analyzed')[:500]
                audio = video_result.get('audio_content', '')
                file_descriptions.append(
                    f"[VIDEO: {f.original_filename}] (Analyzed by Gemini)\n"
                    f"Content: {desc}\n"
                    f"{'Audio/Speech: ' + audio if audio else ''}"
                )
            else:
                # Fallback to frame extraction if Gemini fails
                logger.warning(f"Gemini failed, falling back to frame extraction for {f.original_filename}")
                frames = extract_video_frames(file_path, num_frames=3)
                if frames:
                    image_paths.extend(frames)
                    temp_frames.extend(frames)
                    file_descriptions.append(f"[VIDEO: {f.original_filename}] - 3 frames extracted (fallback)")
                else:
                    file_descriptions.append(f"[VIDEO: {f.original_filename}] - Could not analyze")
        
        # Unsupported video formats - use frame extraction
        elif ext in ('avi', 'mkv'):
            logger.info(f"Unsupported format for Gemini, using frame extraction: {f.original_filename}")
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
    num_videos = len(video_analyses)
    
    user_prompt = f"""{idea_text}

UPLOADED FILES:
{chr(10).join(file_descriptions) if file_descriptions else "No files uploaded"}

{f"[{num_images} images attached for visual analysis]" if num_images > 0 else ""}
{f"[{num_videos} videos analyzed by Gemini AI]" if num_videos > 0 else ""}

YOUR TASK:
1. Generate a SHORT TITLE for this idea (5-8 words, catchy and descriptive)
2. Summarize the idea in 2-3 sentences
3. For EACH image: Describe what you see in detail
4. CONSISTENCY CHECK: Do the images relate to the idea?
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
        "filename.jpg": "Detailed description of what this image shows"
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
        
        # Merge Gemini video analyses into file_summaries
        file_summaries = ai_data.get('file_summaries', {})
        inconsistency_reasons = ai_data.get('inconsistency_reasons', [])
        is_consistent = ai_data.get('is_consistent', True)
        
        for video_result in video_analyses:
            filename = video_result.get('filename', 'video')
            description = video_result.get('description', 'Video analyzed')
            audio = video_result.get('audio_content', '')
            observations = video_result.get('key_observations', [])
            
            # Build comprehensive video summary
            video_summary = f"{description}"
            if observations:
                video_summary += f" Key observations: {', '.join(observations[:3])}"
            if audio:
                video_summary += f" Audio content: {audio}"
            
            file_summaries[filename] = f"[Gemini Analysis] {video_summary}"
            
            # Check video consistency
            if not video_result.get('supports_idea', True):
                is_consistent = False
                reason = video_result.get('inconsistency_reason', f"Video {filename} doesn't match the idea")
                if reason and reason not in inconsistency_reasons:
                    inconsistency_reasons.append(reason)
        
        is_complete, notes = validate_submission(submission)
        
        # Calculate total tokens (Claude + Gemini)
        total_tokens = response['tokens']
        for v in video_analyses:
            total_tokens += v.get('tokens', 0)
        
        # Save AI summary with merged results
        ai_summary, _ = AISummary.objects.update_or_create(
            submission=submission,
            defaults={
                'summary': ai_data.get('summary', 'Summary unavailable'),
                'suggested_tags': ai_data.get('tags', []),
                'file_summaries': file_summaries,
                'is_consistent': is_consistent,
                'inconsistency_reasons': inconsistency_reasons,
                'is_complete': is_complete,
                'completeness_notes': notes,
                'model_used': f"{response['model']} + {MODELS['video']}" if video_analyses else response['model'],
                'tokens_used': total_tokens,
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
        
        # Auto-generate title from AI (always overwrite with better AI title)
        if ai_data.get('title'):
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
