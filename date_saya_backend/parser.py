from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass
class RPBlock:
    narration: str
    dialogue: str


def parse_rp_output(text: str) -> RPBlock:
    """Parse 'narration + quoted dialogue' format."""
    text = (text or "").strip()
    if not text:
        return RPBlock(narration="", dialogue="")

    match = re.search(r'"([^"]+)"', text, flags=re.DOTALL)
    if match:
        dialogue = match.group(1).strip()
        narration = (text[: match.start()] + text[match.end() :]).strip()
        narration = narration.replace("\n", " ").strip()
        return RPBlock(narration=narration, dialogue=dialogue)
    # fallback: whole text as dialogue
    return RPBlock(narration="", dialogue=text.replace("\n", " ").strip())


def emotion_to_image_key(emotion: str) -> str:
    table = {
        "happy": "smile_saya",
        "sad": "crying_saya",
        "angry": "annoyed_saya",
        "neutral": "neutral_saya",
    }
    return table.get(emotion, "neutral_saya")

