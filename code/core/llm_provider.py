import os
import json
import time
from typing import Optional, Dict, Any
from groq import Groq
import google.generativeai as genai
from PIL import Image
from pydantic import ValidationError
from models.schemas import ExtractedEventFacts
from config import config

class ExtractorProvider:
    def __init__(self):
        self.groq_client = Groq(api_key=config.GROQ_API_KEY) if config.GROQ_API_KEY else None
        if config.GEMINI_API_KEY:
            genai.configure(api_key=config.GEMINI_API_KEY)
            self.gemini_model = genai.GenerativeModel("gemini-1.5-pro-latest")
        else:
            self.gemini_model = None

        self._text_cache: Dict[str, ExtractedEventFacts] = {}
        self._image_cache: Dict[str, ExtractedEventFacts] = {}

        self.usage_stats = {
            "groq_requests": 0,
            "groq_prompt_tokens": 0,
            "groq_completion_tokens": 0,
            "gemini_requests": 0,
            "gemini_prompt_tokens": 0,
            "gemini_completion_tokens": 0,
        }

        self.system_prompt = """
        You are a strict financial data extraction assistant. 
        Your job is to read the provided message or image and extract specific facts into a JSON object.
        Do NOT invent facts. If the information is not explicitly present, return null or false.
        
        The JSON must match this schema:
        {
            "is_cancelled": bool, // True if explicitly stated cancelled/voided
            "amended_date": string or null, // "YYYY-MM-DD" if a date is changed
            "amended_amount": float or null, // new numeric amount if changed
            "is_confirmed": bool // True if a pending/estimate event is confirmed settled
        }
        """

    def extract_from_text(self, text: str) -> Optional[ExtractedEventFacts]:
        if not self.groq_client:
            print("Warning: Groq API key not set. Skipping text extraction.")
            return None
            
        if text in self._text_cache:
            return self._text_cache[text]
            
        for attempt in range(3):
            try:
                response = self.groq_client.chat.completions.create(
                    model=config.GROQ_TEXT_MODEL,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": text}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0
                )
                raw_json = response.choices[0].message.content
                if response.usage:
                    self.usage_stats["groq_requests"] += 1
                    self.usage_stats["groq_prompt_tokens"] += response.usage.prompt_tokens
                    self.usage_stats["groq_completion_tokens"] += response.usage.completion_tokens
                data = json.loads(raw_json)
                fact = ExtractedEventFacts(**data)
                self._text_cache[text] = fact
                return fact
            except (json.JSONDecodeError, ValidationError) as e:
                print(f"Validation error on attempt {attempt+1}: {e}")
                if attempt == 2:
                    return None
            except Exception as e:
                print(f"Network error on attempt {attempt+1}: {e}")
                time.sleep(2 ** attempt)
                if attempt == 2:
                    return None
        return None

    def extract_from_image(self, image_path: str, context_text: str = "") -> Optional[ExtractedEventFacts]:
        if not self.gemini_model:
            print("Warning: Gemini API key not set. Skipping image extraction.")
            return None
            
        if not os.path.exists(image_path):
            print(f"Error: Image {image_path} not found.")
            return None

        if image_path in self._image_cache:
            return self._image_cache[image_path]

        for attempt in range(3):
            try:
                img = Image.open(image_path)
                prompt = self.system_prompt + "\n\n" + (context_text or "Extract the financial facts from this image.")
                
                response = self.gemini_model.generate_content(
                    [prompt, img],
                    generation_config={"response_mime_type": "application/json"}
                )
                
                if response.usage_metadata:
                    self.usage_stats["gemini_requests"] += 1
                    self.usage_stats["gemini_prompt_tokens"] += response.usage_metadata.prompt_token_count
                    self.usage_stats["gemini_completion_tokens"] += response.usage_metadata.candidates_token_count
                
                data = json.loads(response.text)
                fact = ExtractedEventFacts(**data)
                self._image_cache[image_path] = fact
                return fact
            except (json.JSONDecodeError, ValidationError) as e:
                print(f"Validation error on attempt {attempt+1}: {e}")
                if attempt == 2:
                    return None
            except Exception as e:
                print(f"Network error on attempt {attempt+1}: {e}")
                time.sleep(2 ** attempt)
                if attempt == 2:
                    return None
        return None

    def mock_extract(self, text_or_image: str) -> ExtractedEventFacts:
        """Fallback for testing without making real API calls."""
        text = str(text_or_image).lower()
        if text in self._text_cache:
            return self._text_cache[text]
            
        fact = ExtractedEventFacts(
            is_cancelled="cancel" in text or "void" in text or "batal" in text,
            amended_amount=42750000.0 if "42750000" in text else None,
            amended_date="2025-08-15" if "2025-08-15" in text else None,
            is_confirmed="konfirmasi" in text or "confirmed" in text
        )
        self._text_cache[text] = fact
        return fact

    def generate_explanation(self, request: Any, math_result: dict) -> str:
        if not self.groq_client:
            return self.mock_explanation(request, math_result)
            
        prompt = f"""
        You are a financial AI. The deterministic engine has decided the following for the user's request to spend {request.requested_amount} on {request.request_type}:
        - Status: {math_result['affordability_status']}
        - Recommended Method: {math_result['recommended_payment_method']}
        - Amount Safe to Pay Today: {math_result['amount_safe_to_pay']}
        
        Write a single concise sentence explaining this decision to the user.
        Do not add fluff, pleasantries, or additional numbers not provided.
        """
        
        for attempt in range(3):
            try:
                response = self.groq_client.chat.completions.create(
                    model=config.GROQ_REASONING_MODEL,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0
                )
                if response.usage:
                    self.usage_stats["groq_requests"] += 1
                    self.usage_stats["groq_prompt_tokens"] += response.usage.prompt_tokens
                    self.usage_stats["groq_completion_tokens"] += response.usage.completion_tokens
                return response.choices[0].message.content.strip()
            except Exception as e:
                print(f"Error during explanation generation on attempt {attempt+1}: {e}")
                time.sleep(2 ** attempt)
                
        return self.mock_explanation(request, math_result)
            
    def mock_explanation(self, request: Any, math_result: dict) -> str:
        if math_result['affordability_status'] == 'affordable_now':
            return f"Pay {request.requested_amount} today. This leaves a safe margin available over the next 90 days."
        elif math_result['affordability_status'] == 'affordable_with_plan':
            return f"You can afford this using {math_result['recommended_payment_method']}."
        elif math_result['affordability_status'] == 'affordable_later':
            return f"Wait until {math_result['earliest_date_for_full_payment']} when you have sufficient funds."
        else:
            return "This request is not affordable within the next 90 days without breaking your minimum balance."
