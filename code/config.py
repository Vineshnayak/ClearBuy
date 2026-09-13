import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DATASET_DIR = os.getenv("DATASET_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hackerrank-orchestrate-september26", "dataset"))
    OUTPUT_FILE = os.getenv("OUTPUT_FILE", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hackerrank-orchestrate-september26", "output.csv"))
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq") # groq or gemini
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

config = Config()
