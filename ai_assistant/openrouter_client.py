import requests
import json
import time
import base64
import os
from django.conf import settings


class OpenRouterClient:
    """Client for interacting with OpenRouter API with Vision support"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.default_model = "anthropic/claude-3.5-sonnet"
        
    def generate_completion(self, system_prompt, user_prompt, model=None, max_tokens=800, images=None):
        """
        Generate a completion from OpenRouter API with optional image support
        """
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured.")
        
        model = model or self.default_model
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://ift-platform.local",
            "X-Title": "IFT - India Future Tycoon"
        }
        
        # Build user content
        if not images:
            # For text-only, many providers prefer a simple string
            user_msg_content = user_prompt
        else:
            # Multi-modal format
            user_msg_content = []
            user_msg_content.append({
                "type": "text",
                "text": user_prompt
            })
            
            for img_path in images[:5]:
                try:
                    if os.path.exists(img_path):
                        with open(img_path, 'rb') as f:
                            img_data = base64.b64encode(f.read()).decode('utf-8')
                        
                        ext = img_path.lower().split('.')[-1]
                        media_type = {
                            'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                            'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'
                        }.get(ext, 'image/jpeg')
                        
                        user_msg_content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{img_data}"}
                        })
                except Exception as e:
                    print(f"Failed to load image {img_path}: {e}")
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg_content}
            ],
            "max_tokens": max_tokens,
            "temperature": 0,
            "seed": 42,
            "top_p": 1
        }
        
        start_time = time.time()
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=60
            )
            
            # Try to get error message from body if it failed
            if not response.ok:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', str(error_data))
                except (ValueError, KeyError):
                    response.raise_for_status()
                else:
                    raise Exception(f"OpenRouter API error: {error_msg}")

            data = response.json()
            processing_time = time.time() - start_time

            return {
                'content': data['choices'][0]['message']['content'],
                'model': data.get('model', model),
                'tokens': data.get('usage', {}).get('total_tokens', 0),
                'time': processing_time,
                'raw_response': json.dumps(data)
            }

        except requests.exceptions.RequestException as e:
            raise Exception(f"OpenRouter API request failed: {str(e)}")
        except (KeyError, IndexError) as e:
            raise Exception(f"Unexpected API response format: {str(e)}")
    
    def generate_video_completion(self, system_prompt, user_prompt, video_path, model=None, max_tokens=1200):
        """
        Generate a completion with native video support using Gemini.
        Sends video file directly to Gemini 1.5 Flash for full video analysis.
        """
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured.")
        
        # Default to Gemini for video analysis
        model = model or "google/gemini-2.0-flash-001"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://ift-platform.local",
            "X-Title": "IFT - India Future Tycoon"
        }
        
        # Build user content with video
        user_msg_content = []
        user_msg_content.append({
            "type": "text",
            "text": user_prompt
        })
        
        # Encode video as base64
        if video_path and os.path.exists(video_path):
            try:
                # Get video MIME type
                ext = video_path.lower().split('.')[-1]
                video_mime = {
                    'mp4': 'video/mp4',
                    'webm': 'video/webm',
                    'mov': 'video/quicktime',
                    'mpeg': 'video/mpeg',
                    'mpg': 'video/mpeg',
                }.get(ext)

                if not video_mime:
                    raise ValueError(f"Unsupported video format: {ext}. Supported: mp4, webm, mov, mpeg")

                # Check file size (max 200MB for large competition videos)
                file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
                if file_size_mb > 200:
                    raise ValueError(f"Video too large ({file_size_mb:.1f}MB). Max allowed: 200MB")

                # Read and encode video
                with open(video_path, 'rb') as f:
                    video_data = base64.b64encode(f.read()).decode('utf-8')
                
                # Add video to content using video_url format
                user_msg_content.append({
                    "type": "video_url",
                    "video_url": {"url": f"data:{video_mime};base64,{video_data}"}
                })
                
            except Exception as e:
                print(f"Failed to load video {video_path}: {e}")
                raise
        else:
            raise ValueError(f"Video file not found: {video_path}")
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg_content}
            ],
            "max_tokens": max_tokens,
            "temperature": 0,
        }
        
        start_time = time.time()
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=300  # 5 min timeout for large video processing
            )
            
            if not response.ok:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', str(error_data))
                except (ValueError, KeyError):
                    response.raise_for_status()
                else:
                    raise Exception(f"OpenRouter API error: {error_msg}")

            data = response.json()
            processing_time = time.time() - start_time

            return {
                'content': data['choices'][0]['message']['content'],
                'model': data.get('model', model),
                'tokens': data.get('usage', {}).get('total_tokens', 0),
                'time': processing_time,
                'raw_response': json.dumps(data)
            }

        except requests.exceptions.RequestException as e:
            raise Exception(f"OpenRouter API request failed: {str(e)}")
        except (KeyError, IndexError) as e:
            raise Exception(f"Unexpected API response format: {str(e)}")
