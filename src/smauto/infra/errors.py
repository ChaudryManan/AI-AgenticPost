"""
Typed exceptions — one per failure class.

Why: publishers, media clients and LLM adapters can all fail, but a rate
limit is not the same as an auth failure is not the same as a bad format.
The publish node catches by type so it can route each to the right recovery
(retry, re-auth, dead-letter).
"""
from __future__ import annotations


class SMError(Exception):
    """Base class for every error raised by smauto."""


class ValidationError(SMError):
    """Input failed schema / policy / platform validation."""


class PolicyViolation(SMError):
    """Content contains banned terms or claims the policy disallows."""


class ResearchError(SMError):
    """Web search / trends lookup failed or returned nothing useful."""


class MediaError(SMError):
    """Image, video, TTS, ffmpeg or canvas generation failed."""


class PublishError(SMError):
    """A publisher rejected the payload for a non-retryable reason."""


class RateLimited(PublishError):
    """HTTP 429 / provider-specific throttle.  Retry with backoff."""


class AuthFailed(PublishError):
    """HTTP 401/403 or missing credentials.  Do not retry — re-auth."""


class FormatRejected(PublishError):
    """Payload violates the platform's format rules.  Send back to formatter."""


class BudgetExceeded(SMError):
    """Token or USD budget for the run is exhausted.  Abort the run."""