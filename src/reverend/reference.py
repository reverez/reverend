"""Optional, bounded offline reference provider. No bulk ingestion or embedding."""
from __future__ import annotations

import hashlib
from html import unescape
import json
import re
import subprocess
import sys
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from typing import Protocol
from urllib.parse import quote


class ReferenceError(RuntimeError):
    code = 'reference_provider_failed'


class ReferenceProvider(Protocol):
    def retrieve(self, query: str, *, mode: str, limit: int) -> list[dict]: ...


@lru_cache(maxsize=4)
def _verify(path: str, size: int, mtime: int, ctime: int, inode: int, expected_hash: str) -> None:
    # Once per file fingerprint, outside indexed query execution. Never build an index.
    with open(path, 'rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != expected_hash:
        raise ReferenceError('Reference archive SHA-256 does not match recorded provenance')


class CompositeReferenceProvider:
    """Bounded fan-out across explicitly configured trusted reference providers."""

    def __init__(self, providers: list[tuple[str, ReferenceProvider]]):
        if not providers:
            raise ValueError('At least one reference provider is required')
        if len(providers) > 8:
            raise ValueError('Too many reference providers configured')
        identities = [identity for identity, _ in providers]
        if any(not identity or len(identity) > 80 for identity in identities):
            raise ValueError('Invalid reference provider identity')
        if len(set(identities)) != len(identities):
            raise ValueError('Duplicate reference provider identity')
        self.providers = tuple(providers)

    def retrieve(self, query: str, *, mode: str, limit: int) -> list[dict]:
        if not 0 <= limit <= 50:
            raise ValueError('Invalid reference retrieval limit')
        if limit == 0:
            return []

        # Query every explicitly enabled provider with the same bounded budget,
        # then interleave ranks. Provider order remains deterministic without
        # allowing the first provider to consume the entire candidate window.
        per_provider = min(12, max(1, limit))
        batches = []
        for provider_id, provider in self.providers:
            batch = [
                dict(row)
                for row in provider.retrieve(
                    query,
                    mode=mode,
                    limit=per_provider,
                )
            ]
            batches.append((provider_id, batch))

        rows = []
        seen = set()
        for rank in range(per_provider):
            for provider_id, batch in batches:
                if rank >= len(batch):
                    continue
                row = batch[rank]
                row['reference_provider_id'] = provider_id
                identity = (
                    row.get('source'),
                    row.get('article_path'),
                    row.get('chunk_id'),
                )
                if identity in seen:
                    continue
                seen.add(identity)
                rows.append(row)
                if len(rows) >= limit:
                    return rows

        return rows


class ZimReferenceProvider:
    def __init__(self, manifest: Path):
        self.manifest = Path(manifest)

    def retrieve(self, query: str, *, mode: str, limit: int) -> list[dict]:
        if mode not in {'hybrid', 'lexical', 'dense'} or not 0 <= limit <= 50 or len(query) > 2000:
            raise ValueError('Invalid reference retrieval request')
        if limit == 0:
            return []
        try:
            record = json.loads(self.manifest.read_text())
            path = Path(record['path'])
            stat = path.stat()
            digest = record['sha256']
            if (stat.st_size != record['byte_size'] or not re.fullmatch('[0-9a-f]{64}', digest)
                    or not record.get('origin') or not record.get('acquired_at') or not record.get('zim_metadata')):
                raise ReferenceError('Incomplete or inconsistent reference provenance')
            _verify(str(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino, digest)
            result = subprocess.run([sys.executable, '-m', 'reverend.reference'],
                input=json.dumps({'path': str(path), 'query': query, 'limit': min(limit, 12), 'mode': mode}),
                text=True, capture_output=True, timeout=25, check=False)
            if result.returncode:
                raise ReferenceError('ZIM reader/query failed: ' + result.stderr[-500:])
            if len(result.stdout) > 500_000:
                raise ReferenceError('Reference worker exceeded output budget')
            current = path.stat()
            if (current.st_size, current.st_mtime_ns, current.st_ctime_ns, current.st_ino) != (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino):
                raise ReferenceError('Reference archive changed during retrieval')
            rows = json.loads(result.stdout)
            for row in rows:
                row.update(corpus='reference', trust_class='TRUSTED_REFERENCE',
                    archive_path=str(path), archive_sha256=digest, archive_filename=path.name,
                    origin=record['origin'], acquired_at=record['acquired_at'],
                    zim_metadata=record['zim_metadata'])
                row['source'] = 'zim://' + digest + '/' + quote(row['article_path'], safe='/')
                row['chunk_id'] = row['source']
            return rows
        except ReferenceError:
            raise
        except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
            raise ReferenceError('Reference provider unavailable: ' + str(exc)) from exc


def _safe_provider_manifest(reference_root: Path, value: str) -> Path:
    candidate = (reference_root / value).resolve()
    root = reference_root.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ReferenceError('Reference provider manifest escapes reference root') from exc
    return candidate


def configured_reference(data_root: Path) -> ReferenceProvider | None:
    """Load explicit provider registry, falling back to the accepted M9 layout."""

    reference_root = Path(data_root) / 'reference'
    registry = reference_root / 'providers.json'

    if registry.exists():
        try:
            payload = json.loads(registry.read_text())
            if payload.get('schema_version') != 1:
                raise ReferenceError('Unsupported reference provider registry schema')
            entries = payload.get('providers')
            if not isinstance(entries, list) or len(entries) > 8:
                raise ReferenceError('Invalid reference provider registry')

            providers = []
            for entry in entries:
                if not isinstance(entry, dict):
                    raise ReferenceError('Invalid reference provider entry')
                if entry.get('enabled', True) is False:
                    continue
                if entry.get('type') != 'zim':
                    raise ReferenceError('Unsupported reference provider type')
                identity = str(entry.get('id', '')).strip()
                manifest_value = str(entry.get('manifest', '')).strip()
                if not identity or not manifest_value:
                    raise ReferenceError('Incomplete reference provider entry')
                manifest = _safe_provider_manifest(reference_root, manifest_value)
                if not manifest.exists():
                    raise ReferenceError(
                        'Configured reference provider manifest is unavailable: '
                        + identity
                    )
                providers.append((identity, ZimReferenceProvider(manifest)))

            if not providers:
                return None
            if len(providers) == 1:
                identity, provider = providers[0]
                return CompositeReferenceProvider([(identity, provider)])
            return CompositeReferenceProvider(providers)
        except ReferenceError:
            raise
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ReferenceError('Reference provider registry unavailable: ' + str(exc)) from exc

    manifest = reference_root / 'kiwix' / 'provider.json'
    return ZimReferenceProvider(manifest) if manifest.exists() else None


class ArticleText(HTMLParser):
    """Bound text extraction; scripts/styles/navigation are not article evidence."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0
        self.length = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'nav'}:
            self.skip += 1
        if tag in {'p', 'div', 'h1', 'h2', 'li', 'br'} and not self.skip:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'nav'} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and self.length < 12000:
            data = data[:12000-self.length]
            self.parts.append(data)
            self.length += len(data)

    def text(self):
        return re.sub(r'\s+', ' ', ' '.join(self.parts)).strip()


def lookup_archive(archive, query: str, *, limit: int, mode: str, search, suggest) -> list[dict]:
    """Indexed title → lexical lookup, at most 6 index queries and 12 articles."""
    from reverend.intelligence.evidence import reference_subject, reference_terms
    focus = reference_subject(query) or query
    terms = reference_terms(focus)[:8]
    normalized = ' '.join(terms)
    entries = []
    seen = set()
    operations = []

    def add(entry, method):
        for _ in range(4):
            if not entry.is_redirect:
                break
            entry = entry.get_redirect_entry()
        if entry.is_redirect or entry.path in seen or len(entries) >= min(limit, 12):
            return
        seen.add(entry.path)
        entries.append((entry, method))

    titles = dict.fromkeys([focus.strip(' ?.'), normalized, normalized.capitalize()]) if mode != 'lexical' else ()
    for title in titles:
        try:
            add(archive.get_entry_by_title(title), 'exact_title')
        except KeyError:
            pass
    if not entries and normalized and mode != 'lexical':
        operations.append('title_index')
        for path in suggest(normalized, min(limit, 12)):
            add(archive.get_entry_by_path(path), 'title_index')
    queries = [terms]
    # A bounded single-token omission recovers spelling errors without guessed aliases.
    if 2 <= len(terms) <= 6:
        queries += [terms[:i] + terms[i+1:] for i in range(min(len(terms), 4))]
    if mode == 'lexical' and len(queries) > 1:
        queries = queries[1:] + queries[:1]
    for words in queries:
        if entries or not words:
            break
        operations.append('lexical')
        for path in search(' AND '.join('"' + word + '"' for word in words), min(limit, 12)):
            add(archive.get_entry_by_path(path), 'lexical')
    rows = []
    for entry, method in entries:
        item = entry.get_item()
        if item.mimetype not in {'text/html', 'text/plain'} or item.size > 1_000_000:
            continue
        raw_bytes = bytes(item.content)
        raw = raw_bytes.decode('utf-8', errors='replace')
        parser = ArticleText()
        parser.feed(raw)
        text = parser.text()
        if not text:
            continue
        footer = re.search(r'<div class="zim-footer">(.*?)</div>', raw, re.S)
        rights = ArticleText()
        if footer:
            rights.feed(footer[1])
        rows.append({'article_footer': rights.text(),
                     'article_footer_links': [unescape(link) for link in re.findall(r'href="([^"]+)"', footer[1])] if footer else [],
                     'source_title': entry.title, 'article_path': entry.path,
                     'content': text, 'content_hash': hashlib.sha256(raw_bytes).hexdigest(),
                     'reference_method': method, 'reference_index_operations': operations,
                     'relevance': 1.0 / (len(rows) + 1)})
    return rows


def _main():
    from libzim.reader import Archive
    from libzim.search import Searcher, Query
    from libzim.suggestion import SuggestionSearcher
    request = json.loads(sys.stdin.read(10000))
    archive = Archive(Path(request['path']))
    if not archive.has_fulltext_index or not archive.has_title_index:
        raise ReferenceError('Reference archive lacks required title/fulltext indexes')
    searcher = Searcher(archive)
    suggestion = SuggestionSearcher(archive)
    rows = lookup_archive(archive, request['query'], limit=request['limit'], mode=request['mode'],
        search=lambda text, count: searcher.search(Query().set_query(text)).getResults(0, count),
        suggest=lambda text, count: suggestion.suggest(text).getResults(0, count))
    print(json.dumps(rows))


if __name__ == '__main__':
    _main()
