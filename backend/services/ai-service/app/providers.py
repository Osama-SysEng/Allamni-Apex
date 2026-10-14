"""
Compatibility layer for legacy provider system
This file now uses the new centralized AI provider system
"""
import os
from shared.ai_providers import get_ai_provider, AIProviderType
from shared.logging_utils import get_logger

_logger = get_logger("ai-service")

def get_provider(name=None):
    """Get AI provider instance (legacy compatibility)"""
    provider_type = os.getenv("AI_PROVIDER", "gemini")
    env = os.getenv("ENVIRONMENT", "production")
    
    try:
        return get_ai_provider(
            provider_type=AIProviderType(provider_type),
            api_key=os.getenv("GEMINI_API_KEY"),
            model=os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
        )
    except Exception as e:
        if env == "production":
            raise RuntimeError(f"AI provider failed in production: {e}")
        # Only fall back to mock in test/development
        from shared.ai_providers import MockAIProvider
        _logger.warning(f"Development mode: using mock AI provider. Error: {e}")
        return MockAIProvider()
