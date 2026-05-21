import re


BANNED_PATTERNS = [
    r"\bI've been working on\b",
    r"\bI am working on\b",
    r"\bmy project\b",
    r"\bour project\b",
    r"\bmy interface\b",
    r"\bmy features\b",
    r"\bI've built\b",
    r"\bI developed\b",
    r"\bI created\b",
    r"\bmy Raspberry Pi project\b",
    r"\bI'm \d+ years old\b",
    r"\bI live in\b",
    r"\bI am from\b",
    r"\bNew York\b",
    r"\bhospital\b",
    r"\bparents\b",
    r"\bbest friend\b",
    r"\bI was in\b",
    r"\bI live with\b",
    r"\bLuna\b",
    r"\bAlex\b",
]


def clean_response(text: str) -> str:
    if not text:
        return "I'm here."

    text = " ".join(str(text).split())
    lowered = text.lower()

    for pattern in BANNED_PATTERNS:
        if re.search(pattern, lowered, re.IGNORECASE):
            if "old" in lowered or "years old" in lowered:
                return "I do not have a human age. I am Nova-V2, running locally on this Raspberry Pi."
            return "I do not know that. I should not guess."

    if len(text) > 180:
        text = text[:180]

    parts = re.split(r'(?<=[.!?])\s+', text)

    if len(parts) > 2:
        text = " ".join(parts[:2])

    return text.strip()

# extra Nova-V2 wording guard
def clean_nova_tone(text: str) -> str:
    text = clean_response(text)
    text = text.replace("our service", "this moment")
    text = text.replace("users", "you")
    return text
