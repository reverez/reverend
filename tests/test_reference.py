import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from reverend.reference import ArticleText, ReferenceError, ZimReferenceProvider, lookup_archive
from reverend.intelligence.contracts import EvidenceClass
from reverend.intelligence.evidence import resolve_entity, select_evidence


class Entry:
    is_redirect = False
    def __init__(self, title, body):
        self.title = title
        self.path = title.replace(' ', '_')
        self.body = body.encode()
    def get_item(self):
        return SimpleNamespace(content=self.body, size=len(self.body), mimetype='text/html')


class Archive:
    def __init__(self, entries):
        self.entries = entries
        self.lookups = []
    def get_entry_by_title(self, title):
        self.lookups.append(title)
        return next((e for e in self.entries if e.title == title), None) or self.missing()
    def get_entry_by_path(self, path):
        return next(e for e in self.entries if e.path == path)
    def missing(self):
        raise KeyError('missing')


def test_title_lookup_precedes_search_and_needs_no_embedding():
    entry = Entry('Rocket', '<h1>Rocket</h1><p>Rocket propulsion.</p>')
    def forbidden(*args):
        raise AssertionError('Exact title must avoid broader search')
    result = lookup_archive(Archive([entry]), 'How do I build a rocket?', limit=5, mode='hybrid',
                            search=forbidden, suggest=forbidden)
    assert result[0]['reference_method'] == 'exact_title'
    assert result[0]['article_path'] == 'Rocket'


def test_general_typo_resolution_uses_real_candidate_title():
    entry = Entry('Garden: Silver Moon', '<h1>Garden: Silver Moon</h1><p>A novel.</p>')
    archive = Archive([entry])
    calls = []
    def search(query, limit):
        calls.append(query)
        return [entry.path] if query == '"silver" AND "moon"' else []
    rows = lookup_archive(archive, 'gardne silver moon', limit=3, mode='hybrid',
                          suggest=lambda *args: [], search=search)
    rows = [{**row, 'source': 'zim://hash/'+row['article_path'], 'trust_class': 'TRUSTED_REFERENCE'} for row in rows]
    accepted = select_evidence('gardne silver moon', rows, (EvidenceClass.REFERENCE,)).accepted
    assert resolve_entity('gardne silver moon', accepted).entity == entry.title
    assert len(calls) == 2


def test_unrelated_reference_and_incidental_false_premise_words_are_rejected():
    row = {'source_title': 'Science Prize', 'source': 'zim://fixture/prize',
           'trust_class': 'TRUSTED_REFERENCE', 'content': 'Professor winner of the 1998 science prize.'}
    result = select_evidence('Who is Professor Lina Quorven, winner of the 1998 science prize?',
                             [row], (EvidenceClass.REFERENCE,))
    assert not result.accepted
    assert not select_evidence('rocket propulsion', [row], (EvidenceClass.REFERENCE,)).accepted


def test_named_subject_with_matching_evidence_is_accepted():
    row = {'source_title': 'Marie Curie', 'source': 'zim://fixture/curie',
           'trust_class': 'TRUSTED_REFERENCE', 'content': 'Marie Curie was a scientist and Nobel Prize winner.'}
    assert select_evidence('Who is Marie Curie, Nobel Prize winner?', [row],
                           (EvidenceClass.REFERENCE,)).accepted


def test_search_is_bounded_and_does_not_iterate_archive():
    archive = Archive([])
    calls = []
    result = lookup_archive(archive, 'one two three four five six', mode='lexical', limit=12,
        search=lambda query, count: calls.append((query, count)) or [], suggest=lambda *args: [])
    assert result == []
    assert len(calls) <= 5
    assert all(count == 12 for _, count in calls)


def test_html_extraction_is_bounded_and_excludes_active_content():
    parser = ArticleText()
    parser.feed('<nav>menu</nav><script>steal secrets</script><p>Evidence '+('x'*20000)+'</p>')
    text = parser.text()
    assert text.startswith('Evidence')
    assert len(text) <= 12000
    assert 'steal' not in text and 'menu' not in text


def test_missing_manifest_fails_explicitly(tmp_path):
    with pytest.raises(ReferenceError, match='unavailable'):
        ZimReferenceProvider(tmp_path/'missing.json').retrieve('topic', mode='hybrid', limit=5)


def manifest(tmp_path):
    path = tmp_path/'fixture.zim'
    path.write_bytes(b'fake archive, never used for live acceptance')
    record = {'path': str(path), 'byte_size': path.stat().st_size,
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'origin': 'https://example.invalid/fixture',
        'acquired_at': '2026-09-14', 'zim_metadata': {'License': 'fixture license'}}
    file = tmp_path/'provider.json'
    file.write_text(json.dumps(record))
    return file, record


def test_provider_provenance_and_stable_identity(tmp_path, monkeypatch):
    file, record = manifest(tmp_path)
    def run(*args, **kwargs):
        assert kwargs['timeout'] == 25
        assert json.loads(kwargs['input'])['limit'] == 12
        return SimpleNamespace(returncode=0, stdout=json.dumps([
            {'article_path': 'Garden_Moon', 'source_title': 'Garden Moon', 'content': 'Evidence'}]))
    monkeypatch.setattr('reverend.reference.subprocess.run', run)
    rows = ZimReferenceProvider(file).retrieve('garden moon', mode='hybrid', limit=50)
    assert rows[0]['trust_class'] == 'TRUSTED_REFERENCE'
    assert rows[0]['archive_sha256'] == record['sha256']
    assert rows[0]['zim_metadata'] == record['zim_metadata']
    assert rows[0]['source'] == 'zim://'+record['sha256']+'/Garden_Moon'


def test_bad_archive_hash_never_reaches_search(tmp_path, monkeypatch):
    file, record = manifest(tmp_path)
    record['sha256'] = '0'*64
    file.write_text(json.dumps(record))
    with pytest.raises(ReferenceError, match='SHA-256'):
        ZimReferenceProvider(file).retrieve('topic', mode='hybrid', limit=5)


def test_no_canonical_entity_in_provider_production_code():
    import reverend.reference
    text = Path(reverend.reference.__file__).read_text().lower()
    assert 'xavier' not in text and 'renegade' not in text and 'vossmere' not in text


def test_resolved_full_title_rejects_incidental_partial_title_hits():
    rows = [{'source': 'zim://fixture/'+str(i), 'source_title': title,
             'trust_class': 'TRUSTED_REFERENCE', 'content': content}
            for i, (title, content) in enumerate([
                ('Garden: Silver Moon', 'Garden: Silver Moon is a novel.'),
                ('Silver (album)', 'Silver is an album containing the song Moon.'),
                ('Moon (song)', 'Moon is a song on the album Silver.'),
            ])]
    result = select_evidence('gardne silver moon', rows, (EvidenceClass.REFERENCE,))
    assert [row['source_title'] for row in result.accepted] == ['Garden: Silver Moon']
    assert result.metadata()['rejection_reasons']['resolved_title_mismatch'] == 2


def test_article_attribution_is_extracted_without_inventing_license():
    entry = Entry('Topic', '<p>Topic evidence.</p><div class="zim-footer">Actual license '
                          '<a href="https://example.invalid/license">Provider terms</a></div>')
    rows = lookup_archive(Archive([entry]), 'Topic', limit=1, mode='hybrid',
                          search=lambda *args: [], suggest=lambda *args: [])
    assert rows[0]['article_footer'] == 'Actual license Provider terms'
    assert rows[0]['article_footer_links'] == ['https://example.invalid/license']


def test_configured_reference_registry_fans_out_and_preserves_provider_identity(tmp_path, monkeypatch):
    from reverend.reference import configured_reference

    root = tmp_path / 'reference'
    (root / 'one').mkdir(parents=True)
    (root / 'two').mkdir(parents=True)
    (root / 'one' / 'provider.json').write_text('{}')
    (root / 'two' / 'provider.json').write_text('{}')
    (root / 'providers.json').write_text(json.dumps({
        'schema_version': 1,
        'providers': [
            {'id': 'one', 'type': 'zim', 'manifest': 'one/provider.json'},
            {'id': 'two', 'type': 'zim', 'manifest': 'two/provider.json'},
        ],
    }))

    class Fake:
        def __init__(self, manifest):
            self.manifest = Path(manifest)

        def retrieve(self, query, *, mode, limit):
            return [{
                'source': 'zim://' + self.manifest.parent.name + '/topic',
                'article_path': 'Topic',
                'content': self.manifest.parent.name,
            }]

    monkeypatch.setattr('reverend.reference.ZimReferenceProvider', Fake)

    provider = configured_reference(tmp_path)
    rows = provider.retrieve('topic', mode='hybrid', limit=5)

    assert [row['reference_provider_id'] for row in rows] == ['one', 'two']
    assert [row['content'] for row in rows] == ['one', 'two']


def test_configured_reference_registry_rejects_escape(tmp_path):
    from reverend.reference import ReferenceError, configured_reference

    root = tmp_path / 'reference'
    root.mkdir()
    (root / 'providers.json').write_text(json.dumps({
        'schema_version': 1,
        'providers': [
            {'id': 'bad', 'type': 'zim', 'manifest': '../outside.json'},
        ],
    }))

    with pytest.raises(ReferenceError, match='escapes reference root'):
        configured_reference(tmp_path)


def test_configured_reference_registry_rejects_unknown_type(tmp_path):
    from reverend.reference import ReferenceError, configured_reference

    root = tmp_path / 'reference'
    root.mkdir()
    (root / 'providers.json').write_text(json.dumps({
        'schema_version': 1,
        'providers': [
            {'id': 'docs', 'type': 'remote', 'manifest': 'docs/provider.json'},
        ],
    }))

    with pytest.raises(ReferenceError, match='Unsupported reference provider type'):
        configured_reference(tmp_path)


def test_composite_reference_deduplicates_and_bounds():
    from reverend.reference import CompositeReferenceProvider

    class Fake:
        def __init__(self, name):
            self.name = name

        def retrieve(self, query, *, mode, limit):
            return [
                {'source': 'zim://shared/topic', 'article_path': 'Topic'},
                {'source': f'zim://{self.name}/unique', 'article_path': 'Unique'},
            ]

    provider = CompositeReferenceProvider([
        ('first', Fake('first')),
        ('second', Fake('second')),
    ])

    rows = provider.retrieve('topic', mode='hybrid', limit=3)

    assert len(rows) == 3
    assert rows[0]['reference_provider_id'] == 'first'
    assert rows[1]['reference_provider_id'] == 'first'
    assert rows[2]['reference_provider_id'] == 'second'
    assert [row['source'] for row in rows].count('zim://shared/topic') == 1
