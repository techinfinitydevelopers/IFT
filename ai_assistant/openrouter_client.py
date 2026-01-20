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
        
        Args:
            system_prompt: System role instruction
            user_prompt: User message
            model: Model to use
            max_tokens: Maximum tokens in response
            images: List of image paths to include (for vision models)
            
        Returns:
            dict: Response containing 'content', 'model', 'tokens', 'time'
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
        
        # Build user content with text and images
        user_content = []
        
        # Add text
        user_content.append({
            "type": "text",
            "text": user_prompt
        })
        
        # Add images if provided
        if images:
            for img_path in images[:5]:  # Max 5 images
                try:
                    if os.path.exists(img_path):
                        with open(img_path, 'rb') as f:
                            img_data = base64.b64encode(f.read()).decode('utf-8')
                        
                        # Determine media type
                        ext = img_path.lower().split('.')[-1]
                        media_type = {
                            'jpg': 'image/jpeg',
                            'jpeg': 'image/jpeg',
                            'png': 'image/png',
                            'gif': 'image/gif',
                            'webp': 'image/webp'
                        }.get(ext, 'image/jpeg')
                        
                        user_content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{img_data}"
                            }
                        })
                except Exception as e:
                    print(f"Failed to load image {img_path}: {e}")
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        
        start_time = time.time()
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=60  # Longer timeout for vision
            )
            response.raise_for_status()
            
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
