import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.llm_provider import ExtractorProvider

def main():
    provider = ExtractorProvider()
    print("Testing Groq...")
    facts = provider.extract_from_text("Rincian penggajian Anda di Cobalt Systems telah berubah. Gaji bulanan Anda naik menjadi IDR 42750000. Perubahan ini berlaku mulai 2025-08-15.")
    print(facts.model_dump() if facts else "Failed")

if __name__ == "__main__":
    main()
