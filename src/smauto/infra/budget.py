"""
Per-run token / USD meter.

Every LLM call goes through `BudgetMeter.charge(model, in_tok, out_tok, node)`.
If the run crosses either the token or USD budget, `BudgetExceeded` is raised
and the run aborts cleanly.

Prices are approximate — update the table when you switch providers.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config.settings import get_settings
from .errors import BudgetExceeded

# (USD per 1K input tokens, USD per 1K output tokens)
PRICE_TABLE: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o":            (0.0050, 0.0150),
    "gpt-4o-mini":       (0.00015, 0.00060),
    "gpt-4-turbo":       (0.0100, 0.0300),
    # Anthropic
    "claude-3-5-sonnet": (0.0030, 0.0150),
    "claude-3-5-haiku":  (0.0008, 0.0040),
    # Gemini
    "gemini-1.5-pro":    (0.0035, 0.0105),
    "gemini-1.5-flash":  (0.00035, 0.00105),
}


def _price(model: str) -> tuple[float, float]:
    if model in PRICE_TABLE:
        return PRICE_TABLE[model]
    # unknown model → assume mid-tier, conservative estimate
    return (0.001, 0.002)


@dataclass
class BudgetMeter:
    tokens: int = 0
    usd: float = 0.0
    by_node: dict[str, float] = field(default_factory=dict)
    by_model: dict[str, int] = field(default_factory=dict)
    hard: bool = True   # set False in tests to disable enforcement

    def charge(self, model: str, in_tok: int, out_tok: int,
               node: str = "unknown") -> float:
        """Record usage and return the incremental USD cost."""
        pin, pout = _price(model)
        cost = (in_tok / 1000.0) * pin + (out_tok / 1000.0) * pout

        self.tokens += in_tok + out_tok
        self.usd += cost
        self.by_node[node] = self.by_node.get(node, 0.0) + cost
        self.by_model[model] = self.by_model.get(model, 0) + in_tok + out_tok

        if self.hard:
            s = get_settings()
            if self.tokens > s.token_budget or self.usd > s.usd_budget:
                raise BudgetExceeded(
                    f"Budget exceeded at node '{node}': "
                    f"{self.tokens} tokens / ${self.usd:.4f} "
                    f"(limits: {s.token_budget} / ${s.usd_budget})"
                )
        return cost

    def snapshot(self) -> dict:
        return {
            "tokens": self.tokens,
            "usd": round(self.usd, 4),
            "by_node": {k: round(v, 4) for k, v in self.by_node.items()},
            "by_model": dict(self.by_model),
        }