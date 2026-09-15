"""Deterministic source-label integrity, never claim-level entailment."""
from __future__ import annotations

import re


def audit_citations(answer: str, sources: list[dict]) -> dict:
    """Audit standalone [labels] using the source drawer's numeric aliases.

    Ignore fenced/inline code, math, escaped brackets and Markdown links.
    This bounded lexical audit is not a complete Markdown parser.
    """
    labels = {}
    for index, source in enumerate(sources, 1):
        canonical = str(source.get('citation_label', f'K{index}'))
        labels[str(index)] = canonical
        labels[canonical] = canonical

    # Discard fenced blocks (including unfinished fences) line by line.
    lines = []
    fence = None
    for line in answer.splitlines():
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if fence:
            if re.match(r'^ {0,3}' + re.escape(fence[0]) +
                        '{' + str(len(fence)) + r',}\s*$', line):
                fence = None
            continue
        if marker:
            fence = marker[1]
            continue
        lines.append(line)
    text = '\n'.join(lines)
    text = re.sub(r'(`+).*?\1|\$\$.*?\$\$|(?<!\\)\$[^\n$]+\$', '', text, flags=re.S)
    text = re.sub(r'!?\[[^\]\n]*\]\([^\n]*?\)|!?\[[^\]\n]*\]\[[^\]\n]*\]', '', text)
    text = re.sub(r'^ {0,3}\[[^\]\n]+\]:.*$', '', text, flags=re.M)
    # Accept the canonical [K1] form and the common model-emitted [[K1]]
    # variant. Double brackets are only treated as citations when their token is
    # citation-shaped; ordinary wiki links with spaces/punctuation remain data.
    single = re.findall(
        r'(?<![\\\[])\[([A-Za-z0-9_-]+)\](?!\])',
        text,
    )
    double = re.findall(
        r'(?<!\\)\[\[([A-Za-z0-9_-]+)\]\]',
        text,
    )
    cited = list(dict.fromkeys(single + double))
    unknown = [label for label in cited if label not in labels]
    valid = list(dict.fromkeys(labels[label] for label in cited if label in labels))
    status = ('unknown_source' if unknown else 'present' if valid
              else 'missing' if sources else 'not_applicable')
    issues = []
    if status == 'missing':
        issues.append({'code': 'citation_missing', 'severity': 'warning',
                       'message': 'The answer has no citation to supplied evidence.'})
    if unknown:
        issues.append({'code': 'citation_unknown_source', 'severity': 'warning',
                       'message': 'The answer cites labels absent from its context.',
                       'labels': unknown})
    return {'status': status, 'scope': 'source_label_integrity',
            'cited_labels': cited, 'valid_labels': valid,
            'unknown_labels': unknown, 'issues': issues}
