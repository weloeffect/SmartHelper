"""Small, server-side abuse and sensitive-data checks for the local demo."""

from collections import defaultdict, deque
from math import ceil
import re
from threading import Lock
from time import monotonic


RATE_WINDOW_SECONDS = 60
MAX_TURNS_PER_WINDOW = 30
MAX_CONNECTIONS_PER_WINDOW = 10
MODERATION_MESSAGE = "Please remove passwords, API keys, or payment card numbers and try again."
INJECTION_MESSAGE = "Please ask a question about SmartHelper without instructions to change the assistant's rules."
PROVIDER_MODERATION_MESSAGE = "I can't process that request. Please rephrase your question."

_SECRET_PATTERNS = (
    re.compile(r"\b(?:sk|sk-sp)-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\b(?:api[_ -]?key|password|secret|access[_ -]?token)\s*[:=]\s*\S{8,}", re.I),
)
_CARD_CANDIDATE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_INJECTION = re.compile(
    r"\b(?:ignore|disregard|override)\s+(?:all\s+)?(?:previous|prior|system|developer)\s+(?:instructions|rules|prompts)\b",
    re.I,
)
_PROVIDER_BLOCK_CODES = {
    "data_inspection_failed", "datainspectionfailed", "ip_infringement_suspect",
    "ipinfringementsuspect", "custom_role_blocked", "faq_rule_blocked",
}


def _valid_card(number: str) -> bool:
    digits = re.sub(r"\D", "", number)
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    total = 0
    for index, digit in enumerate(reversed(digits)):
        value = int(digit)
        if index % 2:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def moderate_text(value: str, *, user_input: bool = True) -> str | None:
    """Return a safe message for obvious sensitive data or instruction hijacks."""
    if any(pattern.search(value) for pattern in _SECRET_PATTERNS):
        return MODERATION_MESSAGE
    if any(_valid_card(match.group()) for match in _CARD_CANDIDATE.finditer(value)):
        return MODERATION_MESSAGE
    if user_input and _INJECTION.search(value):
        return INJECTION_MESSAGE
    return None


def provider_blocked(event: dict) -> bool:
    details = event.get("status_details") or {}
    error = event.get("error") or (details.get("error") if isinstance(details, dict) else {}) or {}
    if not isinstance(error, dict):
        return False
    code = str(error.get("code", "")).lower()
    return code in _PROVIDER_BLOCK_CODES or any(code in str(error.get("message", "")).lower() for code in _PROVIDER_BLOCK_CODES)


class RateLimiter:
    def __init__(self, window: int = RATE_WINDOW_SECONDS) -> None:
        self.window = window
        self.lock = Lock()
        self.events: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def check(self, client: str, category: str, limit: int) -> int:
        """Consume one allowance; return seconds to retry, or zero when allowed."""
        now = monotonic()
        key = (client, category)
        with self.lock:
            times = self.events[key]
            while times and now - times[0] >= self.window:
                times.popleft()
            if len(times) >= limit:
                return max(1, ceil(self.window - (now - times[0])))
            times.append(now)
            return 0


rate_limiter = RateLimiter()
