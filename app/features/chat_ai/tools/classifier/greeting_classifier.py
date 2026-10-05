import re

# Full-message patterns only. Anchored so that
# "hey, is microsoft laying off?" does NOT match —
# only genuine greetings take the fast path.
_GREETING_ALTERNATIVES = [
    r"hi(?: there)?",
    r"hey(?: there)?",
    r"hello(?: there)?",
    r"yo",
    r"sup",
    r"hiya",
    r"howdy",
    r"how are you",
    r"how'?s it going",
    r"what'?s up",
    r"good morning",
    r"good afternoon",
    r"good evening",
]

_GREETING_RE = re.compile(
    r"^(?:" + "|".join(_GREETING_ALTERNATIVES) + r")[\s!.,?]*$",
    re.IGNORECASE,
)


def is_greeting(message: str) -> bool:
    """Local fast-path check. Pure function, zero model cost.

    Assumes the message is already normalized (ChatRequest does this).
    """
    return _GREETING_RE.match(message) is not None
