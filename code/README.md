# ClearBuy Architecture & Development Guide

## Architecture Overview

ClearBuy is structured to separate deterministic financial calculations from LLM-driven inference to ensure financial safety constraints are strictly respected. 

### Modules:
1. **Data Loading (`data_loader.py`)**: Responsible for reading inputs from the dataset, validating them using Pydantic, and resolving foreign-key relationships (e.g., pulling images for a financial event).
2. **Models (`models/schemas.py`)**: Pydantic schemas validating expected structures and ensuring type safety at the borders.
3. **Financial Math / Forecasting (`core/financial_math.py`)**: Deterministic functions for forecasting a 90-day cash-flow balance, verifying safety bounds, and prioritizing payment options.
4. **LLM Provider Interface (`core/llm_provider.py`)**: Abstract interface with implementations for Groq (primary) and Gemini (for multimodal fallback/vision), used for information extraction (untangling messages, reading images) and decision summarization.
5. **Decision Engine (`core/engine.py`)**: Orchestrates the pipeline for a single request: gathering data -> extracting missing amounts -> running deterministic forecasts -> building the payment plan -> generating the decision explanation.

## Technology Stack
- **Python 3.x**
- **Pydantic**: For strict data validation.
- **Pytest**: For testing the pipeline.
- **Groq API**: Preferred for fast text inference.
- **Gemini API**: Alternative for multimodal inference if needed.

## Design Principles
- Keep secrets out of the codebase (use `.env` and `config.py`).
- No LLM hallucination in financial planning: the 90-day safety check must be deterministic.
- Minimal dependencies (no LangChain, LangGraph unless strictly necessary).
