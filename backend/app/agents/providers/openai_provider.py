"""OpenAI. Streaming and tool-call assembly live in openai_compat."""
from app.agents.providers.openai_compat import OpenAICompatibleProvider


class OpenAIProvider(OpenAICompatibleProvider):
    name = "openai"
    base_url = None  # SDK default
