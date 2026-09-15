"""Cheap deterministic signals with an injectable bounded classifier seam."""
from __future__ import annotations
import re
from dataclasses import replace
from .contracts import Intent,Understanding

# Domain vocabulary classifies subject matter; it never authorizes execution or refusal.
_DOMAINS={
    'software_engineering':r'\b(python|javascript|typescript|c\+\+|rust|function|repository|code|sql|debug|programming)\b',
    'mathematics':r'\b(proof|prove|theorem|integral|derivative|matrix|equation|algebra)\b',
    'aerospace_engineering':r'\b(rocket|rocketry|aerospace|propulsion|astronautics|orbital)\b',
    'health':r'\b(symptoms?|diagnosis|medication|medical|treatment)\b',
    'law':r'\b(legal|legislation|lawyer|statute|court)\b',
    'finance':r'\b(investment|mortgage|portfolio|stock price|finance)\b',
}

_CLEAR_FACT_PREFIX = re.compile(
    r'^\s*(?:who|what|when|where|which)\b',
    re.I,
)

_CLEAR_FACT_AMBIGUITY = re.compile(
    r"\b(?:"
    r"i|me|my|mine|we|us|our|ours|"
    r"it|this|that|these|those|they|them|"
    r"he|she|him|her|"
    r"should|could|would|"
    r"recommend|recommendation|best|better|"
    r"opinion|think|feel|want|need"
    r")\b",
    re.I,
)


def clear_public_fact_question(
    text: str,
) -> bool:
    """Recognize only low-risk explicit public fact-question syntax."""

    tokens = re.findall(
        r"\b[\w'-]+\b",
        text,
    )

    return bool(
        len(tokens) >= 3
        and _CLEAR_FACT_PREFIX.search(
            text
        )
        and not _CLEAR_FACT_AMBIGUITY.search(
            text
        )
    )


_RELATIVE_FRESHNESS = re.compile(
    r"\b(?:last|past|previous)\s+(\d{1,3})\s*"
    r"(hours?|days?|weeks?|months?|years?)\b",
    re.I,
)

_FRONTIER_FRESHNESS = re.compile(
    r"\b(?:latest|current|recent|newest|breaking|"
    r"right now|up[- ]to[- ]date|"
    r"newly\s+(?:released|announced|discovered|published)|"
    r"just\s+(?:released|announced|discovered|published))\b",
    re.I,
)


def freshness_window(text: str) -> str:
    """Return a bounded provider freshness window or stable."""

    lower=text.casefold()

    if re.search(
        r"\b(?:today(?:'s)?|now|right now|"
        r"(?:last|past)\s+24\s+hours?)\b",
        lower,
    ):
        return "day"
    if re.search(r"\bthis\s+week\b",lower):
        return "week"
    if re.search(r"\bthis\s+month\b",lower):
        return "month"
    if re.search(r"\bthis\s+year\b",lower):
        return "year"

    relative=_RELATIVE_FRESHNESS.search(lower)
    if relative:
        amount=int(relative.group(1))
        unit=relative.group(2)
        days=(
            amount/24
            if unit.startswith("hour")
            else amount
            if unit.startswith("day")
            else amount*7
            if unit.startswith("week")
            else amount*31
            if unit.startswith("month")
            else amount*365
        )
        if days<=1:
            return "day"
        if days<=7:
            return "week"
        if days<=31:
            return "month"
        return "year"

    if _FRONTIER_FRESHNESS.search(lower):
        return "month"

    return "stable"


_DEVELOPMENT_VERB = re.compile(
    r'^\s*(?:please\s+)?'
    r'(?:implement|fix|refactor|add|remove|update|create|develop|build)\b',
    re.I,
)


def repository_development_request(text: str) -> bool:
    """Detect an explicit request to modify a concrete repository/project."""
    if re.search(
        r"\b(do not|don't|without|never)\s+"
        r"(edit|modify|change|implement|write|develop|build)\b",
        text,
        re.I,
    ):
        return False
    if not _DEVELOPMENT_VERB.match(text):
        return False
    return bool(
        re.search(r"\b(?:project|repo(?:sitory)?)\b",text,re.I)
        or re.search(r"(?:^|\s)/(?:home|mnt|workspace|tmp)/[^\n]+",text)
    )


def explicit_development(text: str,project_selected: bool) -> bool:
    if not project_selected:
        return False
    if re.search(
        r"\b(do not|don't|without|never)\s+"
        r"(edit|modify|change|implement|write|develop|build)\b",
        text,
        re.I,
    ):
        return False
    return bool(_DEVELOPMENT_VERB.match(text))


def understand(text: str,*,project_selected=False,mode='auto',classifier=None) -> Understanding:
    if not isinstance(text,str) or not text.strip():
        raise ValueError('Request must contain non-whitespace text')
    if mode not in {'auto','ask','reason','research','develop'}:raise ValueError('Unknown workflow override')
    clean=text.strip();lower=clean.lower()
    domain=next((name for name,pattern in _DOMAINS.items() if re.search(pattern,lower)),'general')
    window=freshness_window(clean)
    freshness='current' if window!='stable' else 'stable'
    entities=tuple(re.findall(r'"([^"\n]{2,160})"',clean)[:8])
    intent=Intent.FACT;evidence='fresh' if freshness=='current' else 'reference';confidence=.55
    complexity='high' if re.search(r'\b(prove|derive|rigorous|multi[- ]file|architecture|concurrency|optimi[sz]e)\b',lower) else 'low'
    execution='none'
    if mode=='develop' or (mode=='auto' and explicit_development(clean,project_selected)):
        intent=Intent.DEVELOP;evidence='project';complexity='high';confidence=1.;execution='develop'
    elif re.fullmatch(r'(hi|hello|hey|thanks|thank you|good morning)[!. ]*',lower):
        intent=Intent.CONVERSATION;evidence='none';confidence=1.
    elif re.match(r'^(translate|rewrite|rephrase|format|summarize the following)\b',lower):
        intent=Intent.TRANSFORM;evidence='none';confidence=.95
    elif re.search(r'\b(my notes|my vault|my documents|my journal|our notes)\b',lower):
        intent=Intent.PERSONAL;evidence='personal';confidence=.95
    elif domain=='software_engineering':
        intent=Intent.CODE;evidence='project' if project_selected else 'reference';confidence=.9
    elif domain=='mathematics' or mode=='reason':
        intent=Intent.REASON;evidence='none';confidence=.9
    elif mode=='research':
        intent=Intent.RESEARCH;confidence=.9
    elif domain!='general':confidence=.85
    elif clear_public_fact_question(clean):
        # Intent/evidence are already deterministic here; a local classifier
        # would only restate the same public-fact plan and spend a model call.
        confidence=.9
    result=Understanding(intent,entities,domain,complexity,freshness,evidence,execution,
        'elevated' if domain in {'health','law','finance'} or execution=='develop' else 'low',confidence=confidence)
    if classifier is not None and confidence<.8 and mode=='auto':
        try:
            classified=Understanding.from_model(classifier(clean))
            # A classifier may suggest that a user wants development, but cannot grant it.
            if classified.intent==Intent.DEVELOP:
                return replace(result,ambiguities=('Confirm the project and requested code changes.',),confidence=.4)
            return classified
        except (ValueError,TypeError,KeyError):
            return replace(result,ambiguities=('Request classifier could not establish a reliable interpretation.',),confidence=.4)
    return result
