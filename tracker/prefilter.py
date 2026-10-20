"""Free keyword gate so Claude only sees results that mention a degree and recruiting."""

import re

_DEGREE = re.compile(
    r"ph\.?\s?d|doctoral|master'?s|\bm\.?sc\b|\bm\.?a\.?sc\b|\bm\.?s\.? (?:student|position|program)"
    r"|graduate (?:student|position|research|assistant)|grad students?|research assistant|\bgra\b|\bras?hip\b",
    re.I,
)
_RECRUIT = re.compile(
    r"position|opening|vacanc|recruit|hiring|looking for|seeking|join (?:my|our)|funded|funding"
    r"|scholarship|fellowship|apply|application|prospective|opportunit|accepting|available|we are growing",
    re.I,
)


def passes(candidate: dict) -> bool:
    text = f"{candidate.get('title', '')} {candidate.get('snippet', '')}"
    return bool(_DEGREE.search(text) and _RECRUIT.search(text))
