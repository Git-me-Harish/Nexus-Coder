"""
Groq is OpenAI-API-compatible (same request/response shape, different
base_url) -- reuses the openai SDK and the shared streaming/tool-call
implementation rather than carrying a second copy of it.
"""
from app.agents.providers.openai_compat import OpenAICompatibleProvider

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider(OpenAICompatibleProvider):
    name = "groq"
    base_url = GROQ_BASE_URL
