import os
import json
from typing import Optional, Dict, Any
from groq import Groq
import google.generativeai as genai
from PIL import Image
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
            
        try:
            response = self.groq_client.chat.completions.create(
                model="llama3-8b-8192", # fast model for structured output
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": text}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            raw_json = response.choices[0].message.content
            data = json.loads(raw_json)
            return ExtractedEventFacts(**data)
        except Exception as e:
            print(f"Error during Groq extraction: {e}")
            return None

    def extract_from_image(self, image_path: str, context_text: str = "") -> Optional[ExtractedEventFacts]:
        if not self.gemini_model:
            print("Warning: Gemini API key not set. Skipping image extraction.")
            return None
            
        if not os.path.exists(image_path):
            print(f"Error: Image {image_path} not found.")
            return None

        try:
            img = Image.open(image_path)
            prompt = self.system_prompt + "\n\n" + (context_text or "Extract the financial facts from this image.")
            
            response = self.gemini_model.generate_content(
                [prompt, img],
                generation_config={"response_mime_type": "application/json"}
            )
            
            data = json.loads(response.text)
            return ExtractedEventFacts(**data)
        except Exception as e:
            print(f"Error during Gemini extraction: {e}")
            return None

    def mock_extract(self, text_or_image: str) -> ExtractedEventFacts:
        """Fallback for testing without making real API calls."""
        text = str(text_or_image).lower()
        return ExtractedEventFacts(
            is_cancelled="cancel" in text or "void" in text or "batal" in text,
            amended_amount=42750000.0 if "42750000" in text else None,
            amended_date="2025-08-15" if "2025-08-15" in text else None,
            is_confirmed="konfirmasi" in text or "confirmed" in text
        )
