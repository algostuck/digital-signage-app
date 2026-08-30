"""AI provider adapter (P3-M01, slice 3B-1) — the LocalStorage pattern.

`LocalDeterministicProvider` is the default in every environment: pure
rule/template transforms with zero external calls, so the platform (and its
test suite) never depends on a model being reachable (NFR3-06). Real
providers (OpenAI/Anthropic/Azure/on-prem) become config swaps behind the
same interface (`AI_PROVIDER` + credentials from env/secret store) —
never stored in the database.
"""

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AIResult:
    content: dict
    confidence: float
    model_ref: str
    provider: str
    template_version: str
    notes: list[str] = field(default_factory=list)


class AIProviderError(Exception):
    """Provider unavailable/failed — callers degrade deterministically."""


TOKEN_RE = re.compile(r"({{\s*[\w.]+\s*}}|%[sd])")

# Tiny packaged glossaries: signage-domain vocabulary only. Deliberately
# small — localization QUALITY comes from real providers later; these keep
# the flow deterministic and placeholder-safe.
GLOSSARIES: dict[str, dict[str, str]] = {
    "hi": {"welcome": "स्वागत है", "sale": "बिक्री", "open": "खुला", "closed": "बंद",
           "today": "आज", "new": "नया", "free": "मुफ़्त", "offer": "ऑफ़र",
           "now": "अभी", "thank you": "धन्यवाद"},
    "bn": {"welcome": "স্বাগতম", "sale": "বিক্রয়", "open": "খোলা", "closed": "বন্ধ",
           "today": "আজ", "new": "নতুন", "free": "বিনামূল্যে", "offer": "অফার",
           "now": "এখন", "thank you": "ধন্যবাদ"},
    "es": {"welcome": "bienvenido", "sale": "rebajas", "open": "abierto",
           "closed": "cerrado", "today": "hoy", "new": "nuevo", "free": "gratis",
           "offer": "oferta", "now": "ahora", "thank you": "gracias"},
    "fr": {"welcome": "bienvenue", "sale": "soldes", "open": "ouvert",
           "closed": "fermé", "today": "aujourd'hui", "new": "nouveau",
           "free": "gratuit", "offer": "offre", "now": "maintenant",
           "thank you": "merci"},
    "de": {"welcome": "willkommen", "sale": "angebot", "open": "geöffnet",
           "closed": "geschlossen", "today": "heute", "new": "neu",
           "free": "gratis", "offer": "angebot", "now": "jetzt",
           "thank you": "danke"},
}

TEXT_TEMPLATES = ("headline", "shorten", "cta", "tone_formal", "tone_casual")

_CASUAL_TO_FORMAL = {"hey": "hello", "hi": "hello", "grab": "get", "awesome": "excellent",
                     "stuff": "items", "guys": "everyone", "cool": "impressive"}
_FORMAL_TO_CASUAL = {"purchase": "grab", "excellent": "awesome", "hello": "hey",
                     "items": "stuff", "assistance": "help"}


def _truncate_words(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    cut = text[:max_chars].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "…", True


def _swap_words(text: str, mapping: dict[str, str]) -> str:
    def repl(match: re.Match) -> str:
        word = match.group(0)
        out = mapping.get(word.lower(), word)
        return out.capitalize() if word[0].isupper() else out

    if not mapping:
        return text
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(k) for k in sorted(mapping, key=len, reverse=True)) + r")\b",
        re.IGNORECASE,
    )
    return pattern.sub(repl, text)


class LocalDeterministicProvider:
    name = "local"
    model_ref = "deterministic-rules"

    def generate_text(self, *, template: str, text: str, max_chars: int | None = None) -> AIResult:
        notes: list[str] = []
        confidence = 0.9
        if template == "headline":
            result = " ".join(w if w.isupper() else w.capitalize() for w in text.split())
            if max_chars:
                result, truncated = _truncate_words(result, max_chars)
                if truncated:
                    confidence = 0.7
                    notes.append("truncated to fit")
        elif template == "shorten":
            result, truncated = _truncate_words(text, max_chars or 80)
            if truncated:
                notes.append("shortened at word boundary")
            else:
                confidence = 1.0
        elif template == "cta":
            base = text.rstrip(".!… ")
            result = f"{base} — Shop now!" if base else "Shop now!"
            if max_chars:
                result, _ = _truncate_words(result, max_chars)
        elif template == "tone_formal":
            result = _swap_words(text, _CASUAL_TO_FORMAL)
        elif template == "tone_casual":
            result = _swap_words(text, _FORMAL_TO_CASUAL)
        else:
            raise AIProviderError(f"Unknown text template '{template}'")
        return AIResult(
            content={"text": result},
            confidence=confidence,
            model_ref=self.model_ref,
            provider=self.name,
            template_version=f"{template}@1",
            notes=notes,
        )

    def generate_creative(
        self, *, headline: str, body: str | None, width: int, height: int
    ) -> AIResult:
        ratio = width / height if height else 1
        if ratio >= 3:
            layout_hint, headline_max = "banner", 60
        elif ratio >= 1.2:
            layout_hint, headline_max = "landscape", 80
        elif ratio <= 0.8:
            layout_hint, headline_max = "portrait", 50
        else:
            layout_hint, headline_max = "square", 40
        fitted_headline, truncated = _truncate_words(
            " ".join(w if w.isupper() else w.capitalize() for w in headline.split()),
            headline_max,
        )
        content = {
            "dimensions": {"width": width, "height": height},
            "layout_hint": layout_hint,
            "headline": fitted_headline,
            "body": _truncate_words(body, 200)[0] if body else None,
            "cta": "Learn more",
            "font_scale": round(min(width, height) / 1080, 2),
        }
        return AIResult(
            content=content,
            confidence=0.7 if truncated else 0.85,
            model_ref=self.model_ref,
            provider=self.name,
            template_version="creative@1",
            notes=["headline truncated to zone"] if truncated else [],
        )

    def localize(self, *, text: str, target_locale: str) -> AIResult:
        glossary = GLOSSARIES.get(target_locale.lower().split("-")[0])
        if glossary is None:
            raise AIProviderError(f"No local glossary for locale '{target_locale}'")
        # Freeze placeholders so substitutions can never damage them.
        tokens: list[str] = []

        def freeze(match: re.Match) -> str:
            tokens.append(match.group(0))
            return f"\x00{len(tokens) - 1}\x00"

        frozen = TOKEN_RE.sub(freeze, text)
        translated = _swap_words(frozen, glossary)
        for index, token in enumerate(tokens):
            translated = translated.replace(f"\x00{index}\x00", token)

        words = [w for w in re.findall(r"[a-zA-Z']+", frozen)]
        covered = sum(1 for w in words if w.lower() in glossary)
        coverage = covered / len(words) if words else 0
        return AIResult(
            content={"text": translated, "locale": target_locale},
            confidence=round(0.4 + 0.6 * coverage, 3),
            model_ref=self.model_ref,
            provider=self.name,
            template_version="glossary@1",
            notes=[f"glossary coverage {covered}/{len(words)} words"],
        )


def get_ai_provider() -> LocalDeterministicProvider:
    """Factory: AI_PROVIDER config selects the adapter; anything other than
    a configured real provider resolves to the deterministic local one."""
    from app.core.config import get_settings

    provider = getattr(get_settings(), "ai_provider", "local")
    # Real providers land here as config swaps; local is the safe default.
    _ = provider
    return LocalDeterministicProvider()
