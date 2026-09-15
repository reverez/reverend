import pytest

from reverend.intelligence.citations import audit_citations


@pytest.mark.parametrize('answer,sources,status,unknown', [
    ('Hello.', [], 'not_applicable', []),
    ('An answer.', [{'citation_label': 'K1'}], 'missing', []),
    ('Supported [K1] and [1].', [{'citation_label': 'K1'}], 'present', []),
    ('[web-1]', [{'citation_label': 'web-1'}], 'present', []),
    ('[K2]', [], 'unknown_source', ['K2']),
    ('[K1] [K99]', [{'citation_label': 'K1'}], 'unknown_source', ['K99']),
    ('[K99] [K99]', [], 'unknown_source', ['K99']),
    ('[made-up]', [{'citation_label': 'K1'}], 'unknown_source', ['made-up']),
    ('`[K1]`\n```md\n[K1]\n```\n~~~\n[K1]\n~~~', [{'citation_label': 'K1'}], 'missing', []),
    (r'\[K1] $[K1]$ [K1](https://example.invalid) [K1][link]', [{'citation_label': 'K1'}], 'missing', []),
    ('```\n[K99]', [], 'not_applicable', []),
])
def test_label_integrity(answer, sources, status, unknown):
    result = audit_citations(answer, sources)
    assert result['scope'] == 'source_label_integrity'
    assert result['status'] == status
    assert result['unknown_labels'] == unknown
    codes = [issue['code'] for issue in result['issues']]
    assert ('citation_missing' in codes) == (status == 'missing')
    assert ('citation_unknown_source' in codes) == bool(unknown)


def test_double_bracket_source_label_is_accepted():
    from reverend.intelligence.citations import audit_citations

    result = audit_citations(
        'Xavier is an animated television series [[K1]].',
        [{'citation_label': 'K1', 'source': 'zim://fixture/xavier'}],
    )

    assert result['status'] == 'present'
    assert result['cited_labels'] == ['K1']
    assert result['valid_labels'] == ['K1']
    assert result['unknown_labels'] == []


def test_double_bracket_wiki_link_is_not_misclassified_as_citation():
    from reverend.intelligence.citations import audit_citations

    result = audit_citations(
        'See [[Xavier: Renegade Angel]] for background.',
        [{'citation_label': 'K1', 'source': 'zim://fixture/xavier'}],
    )

    assert result['status'] == 'missing'
    assert result['cited_labels'] == []
