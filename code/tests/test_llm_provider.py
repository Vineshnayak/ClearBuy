import os
import sys
import json
import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.llm_provider import ExtractorProvider
from models.schemas import ExtractedEventFacts

class MockUsage:
    def __init__(self):
        self.prompt_tokens = 10
        self.completion_tokens = 20

class MockResponse:
    class Message:
        def __init__(self, content):
            self.content = content
    class Choice:
        def __init__(self, message):
            self.message = message
    def __init__(self, content):
        self.choices = [self.Choice(self.Message(content))]
        self.usage = MockUsage()

class MockGroqClient:
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0
        self.chat = self.Chat(self)
        
    class Chat:
        class Completions:
            def __init__(self, outer):
                self.outer = outer
            def create(self, **kwargs):
                if self.outer.call_count >= len(self.outer.responses):
                    raise Exception("Network error")
                resp = self.outer.responses[self.outer.call_count]
                self.outer.call_count += 1
                if isinstance(resp, Exception):
                    raise resp
                return MockResponse(resp)
        def __init__(self, outer):
            self.completions = self.Completions(outer)

def test_cache_hits():
    provider = ExtractorProvider()
    provider.groq_client = MockGroqClient([
        json.dumps({"is_cancelled": True, "amended_date": None, "amended_amount": None, "is_confirmed": False})
    ])
    
    # First call should hit the mock API
    fact1 = provider.extract_from_text("Cancel my flight")
    assert fact1 is not None
    assert fact1.is_cancelled == True
    assert provider.groq_client.call_count == 1
    
    # Second call should hit cache, not the API
    fact2 = provider.extract_from_text("Cancel my flight")
    assert fact2 is not None
    assert fact2.is_cancelled == True
    assert provider.groq_client.call_count == 1

def test_retry_on_validation_error():
    provider = ExtractorProvider()
    provider.groq_client = MockGroqClient([
        '{"invalid_json": true', # Attempt 1: JSONDecodeError
        '{"is_cancelled": "not_a_bool"}', # Attempt 2: ValidationError
        json.dumps({"is_cancelled": True, "amended_date": None, "amended_amount": None, "is_confirmed": False}) # Attempt 3: Success
    ])
    
    fact = provider.extract_from_text("Try three times")
    assert fact is not None
    assert fact.is_cancelled == True
    assert provider.groq_client.call_count == 3

def test_failure_after_max_retries():
    provider = ExtractorProvider()
    provider.groq_client = MockGroqClient([
        '{"invalid_json": true', 
        '{"invalid_json": true', 
        '{"invalid_json": true'
    ])
    
    fact = provider.extract_from_text("Fail forever")
    assert fact is None
    assert provider.groq_client.call_count == 3
