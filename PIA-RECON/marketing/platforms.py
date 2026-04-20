"""
Static platform metadata used to build drafting prompts.

Kept deliberately small — char_limit drives both prompt guidance and the
post-generation shortening retry for Twitter. format_rules is a short
natural-language blob shoved into the system prompt so the LLM knows what
shape a "good" post takes on each platform.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PlatformSpec:
    label: str
    char_limit: Optional[int]   # None = no hard cap (e.g. script formats)
    format_rules: str


PLATFORMS: dict[str, PlatformSpec] = {
    "twitter": PlatformSpec(
        label="Twitter / X",
        char_limit=280,
        format_rules=(
            "Single post, punchy, one idea. No hashtag spam — 0-2 max. "
            "No preamble. Thread support is future work."
        ),
    ),
    "linkedin": PlatformSpec(
        label="LinkedIn",
        char_limit=3000,
        format_rules=(
            "Professional tone. Short paragraphs separated by blank lines. "
            "Open with a hook, close with a question or CTA. "
            "3-5 relevant hashtags at the end."
        ),
    ),
    "instagram": PlatformSpec(
        label="Instagram",
        char_limit=2200,
        format_rules=(
            "Caption under an image. Emoji OK but tasteful. End with a CTA. "
            "Hashtags in a block after a line break — up to 10 relevant ones."
        ),
    ),
    "tiktok": PlatformSpec(
        label="TikTok / Reels (script)",
        char_limit=None,
        format_rules=(
            "Script format with labeled beats: [HOOK 0-3s], [BEAT 1], "
            "[BEAT 2], [PAYOFF], [CTA]. Include brief visual direction in "
            "brackets. Target ~30-60s spoken length."
        ),
    ),
}


def get_spec(platform: str) -> PlatformSpec:
    """Lookup with a helpful error if the platform is unknown."""
    try:
        return PLATFORMS[platform]
    except KeyError:
        raise ValueError(
            f"Unknown platform {platform!r}. "
            f"Supported: {', '.join(PLATFORMS.keys())}"
        )
