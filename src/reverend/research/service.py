"""Parent-owned provenance persistence; worker receives only a URL."""
from __future__ import annotations
import base64
import hashlib
import json
import shutil
import sqlite3
import subprocess
import uuid
from pathlib import Path
from .worker import validate_url

MAX_DISCOVERY_SEARCH_CALLS=3
MAX_DISCOVERY_FETCH_ATTEMPTS=3


def sandbox_worker_argv(script_name: str):
    if script_name not in {'worker.py','search_worker.py','image_worker.py'}:
        raise ValueError('Unknown public research worker')
    binary=shutil.which('bwrap')
    if not binary:raise ValueError('Public research requires bubblewrap; no unsafe fallback is available')
    script=Path(__file__).with_name(script_name)
    if not script.is_file():raise ValueError('Public research worker is unavailable')
    target='/'+script_name
    argv=[binary,'--unshare-all','--share-net','--die-with-parent','--new-session','--clearenv',
          '--ro-bind','/usr','/usr','--ro-bind','/lib','/lib']
    if Path('/lib64').exists():argv+=['--ro-bind','/lib64','/lib64']
    argv+=['--dir','/etc','--dir','/etc/ssl']
    for source in ('/etc/ssl/certs','/etc/resolv.conf','/etc/hosts','/etc/nsswitch.conf'):
        if Path(source).exists():argv+=['--ro-bind',source,source]
    argv+=['--tmpfs','/tmp','--dev','/dev','--ro-bind',str(script),target,
           '--chdir','/tmp','/usr/bin/python3','-I','-B',target]
    return argv


def worker_argv():
    return sandbox_worker_argv('worker.py')


def search_worker_argv():
    return sandbox_worker_argv('search_worker.py')


def image_worker_argv():
    return sandbox_worker_argv('image_worker.py')


class PublicResearch:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS public_sources(id TEXT PRIMARY KEY,url TEXT NOT NULL,content TEXT NOT NULL,content_hash TEXT NOT NULL,trust TEXT NOT NULL,clipped INTEGER NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
            columns={row[1] for row in db.execute('PRAGMA table_info(public_sources)')}
            for name,declaration in (
                ('source_title','TEXT'),
                ('search_provider','TEXT'),
                ('search_rank','INTEGER'),
                ('published_at','TEXT'),
                ('updated_at','TEXT'),
                ('search_result_date','TEXT'),
                ('search_age','TEXT'),
                ('search_freshness','TEXT'),
                ('image_id','TEXT'),
            ):
                if name not in columns:
                    db.execute(f'ALTER TABLE public_sources ADD COLUMN {name} {declaration}')
            db.execute(
                'CREATE TABLE IF NOT EXISTS public_images('
                'id TEXT PRIMARY KEY,'
                'source_id TEXT NOT NULL,'
                'url TEXT NOT NULL,'
                'media_type TEXT NOT NULL,'
                'content_hash TEXT NOT NULL,'
                'byte_count INTEGER NOT NULL,'
                'content BLOB NOT NULL,'
                'search_provider TEXT,'
                'search_rank INTEGER,'
                'created_at TEXT DEFAULT CURRENT_TIMESTAMP)'
            )

    def fetch(self,url: str,*,allow_network=False,metadata=None):
        if allow_network is not True:raise ValueError('Explicit network opt-in is required for public research')
        validate_url(url)
        metadata=dict(metadata or {})
        allowed={'source_title','search_provider','search_rank','published_at','updated_at','search_result_date','search_age','search_freshness'}
        if set(metadata)-allowed:raise ValueError('Invalid public-source metadata')
        source_title=str(metadata.get('source_title',''))[:500]
        search_provider=str(metadata.get('search_provider',''))[:32]
        published_at=str(metadata.get('published_at',''))[:100]
        updated_at=str(metadata.get('updated_at',''))[:100]
        search_result_date=str(metadata.get('search_result_date',''))[:100]
        search_age=str(metadata.get('search_age',''))[:100]
        search_freshness=str(metadata.get('search_freshness','')).strip().lower()
        if search_freshness not in {'','stable','day','week','month','year'}:
            raise ValueError('Invalid public-source freshness provenance')
        search_rank=metadata.get('search_rank')
        if search_rank is not None and (
            not isinstance(search_rank,int)
            or isinstance(search_rank,bool)
            or not 1<=search_rank<=50
        ):raise ValueError('Invalid public-source search rank')
        try:
            result=subprocess.run(worker_argv(),input=json.dumps({'url':url}),text=True,capture_output=True,
                timeout=25,env={},cwd='/tmp',close_fds=True)
        except subprocess.TimeoutExpired as exc:raise ValueError('Public research exceeded its time limit') from exc
        if result.returncode:
            # bubblewrap errors may contain host paths; provide a bounded capability explanation.
            try:message=json.loads(result.stdout)['error']
            except (ValueError,KeyError):message='Restricted research sandbox could not start; check bubblewrap and user namespaces'
            raise ValueError(message)
        if len(result.stdout)>160000:raise ValueError('Research output exceeded limit')
        data=json.loads(result.stdout)
        if data.get('url')!=url or data.get('trust')!='UNTRUSTED_EXTERNAL' or len(data.get('content',''))>24000:
            raise ValueError('Invalid research worker output')
        source_title=source_title or str(data.get('source_title',''))[:500]
        published_at=published_at or str(data.get('published_at',''))[:100]
        updated_at=updated_at or str(data.get('updated_at',''))[:100]
        identity=uuid.uuid4().hex
        with sqlite3.connect(self.path) as db:
            db.execute(
                'INSERT INTO public_sources(id,url,content,content_hash,trust,clipped,source_title,search_provider,search_rank,published_at,updated_at,search_result_date,search_age,search_freshness) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (
                    identity,url,data['content'],data['content_hash'],
                    'UNTRUSTED_EXTERNAL',bool(data['clipped']),
                    source_title or None,search_provider or None,search_rank,
                    published_at or None,updated_at or None,search_result_date or None,
                    search_age or None,search_freshness or None,
                ),
            )
        return self.get(identity)

    def search(self,query: str,*,allow_network=False,freshness='stable',limit=6,config=None):
        if allow_network is not True:raise ValueError('Explicit network opt-in is required for public research')
        if (
            not isinstance(query,str)
            or not query.strip()
            or len(query)>600
            or len(query.split())>75
            or freshness not in {'stable','day','week','month','year'}
            or not isinstance(limit,int)
            or isinstance(limit,bool)
            or not 1<=limit<=10
        ):raise ValueError('Invalid bounded web-search request')
        from .search import (
            WebSearchAuthenticationError,
            WebSearchError,
            WebSearchPlanError,
            WebSearchRateLimitError,
            WebSearchRequestRejected,
            WebSearchUnavailable,
            configured_web_search,
        )
        settings=config
        if settings is None:
            settings=configured_web_search()
        if settings is None:
            raise WebSearchUnavailable('No web-search provider is configured')
        payload={
            'provider':settings.provider,
            'endpoint':settings.endpoint,
            'api_key':settings.api_key or '',
            'country':settings.country,
            'language':settings.language,
            'query':query.strip(),
            'freshness':freshness,
            'limit':limit,
        }
        try:
            result=subprocess.run(
                search_worker_argv(),
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                timeout=20,
                env={},
                cwd='/tmp',
                close_fds=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise WebSearchError('Web search exceeded its time limit') from exc
        if len(result.stdout)>2_500_000:
            raise WebSearchError('Web-search output exceeded limit')
        if result.returncode:
            try:
                failure=json.loads(result.stdout)
                message=failure['error']
                error_code=str(failure.get('error_code','web_search_failed'))
            except (ValueError,KeyError,TypeError):
                message='Restricted web-search sandbox could not start'
                error_code='web_search_failed'
            error_type={
                'network_search_auth_failed':WebSearchAuthenticationError,
                'web_search_rate_limited':WebSearchRateLimitError,
                'web_search_plan_unavailable':WebSearchPlanError,
                'web_search_request_rejected':WebSearchRequestRejected,
            }.get(error_code,WebSearchError)
            raise error_type(str(message)[:1000])
        try:data=json.loads(result.stdout)
        except ValueError as exc:raise WebSearchError('Invalid web-search worker output') from exc
        if (
            data.get('provider')!=settings.provider
            or data.get('freshness')!=freshness
            or not isinstance(data.get('results'),list)
            or len(data['results'])>limit
        ):
            raise WebSearchError('Invalid web-search worker output')
        response={
            'provider':settings.provider,
            'freshness':freshness,
            'results':[dict(row) for row in data['results']],
            'configuration':settings.safe_metadata(),
        }
        for key in ('strategy','provider_time_range'):
            if data.get(key) is not None:
                response[key]=data.get(key)
        return response

    def discover(self,query: str,*,allow_network=False,freshness='stable',limit=3,config=None):
        if not isinstance(limit,int) or isinstance(limit,bool) or not 1<=limit<=3:
            raise ValueError('Public discovery limit must be 1–3')

        from .search import (
            preferred_primary_domains,
            primary_source_search_query,
            source_authority,
        )
        from .quality import facet_search_query,missing_search_facets

        search_limit=min(10,max(limit*2,limit))
        authority_query=primary_source_search_query(query)
        authority_found=None
        authority_error=None
        search_call_count=0

        if authority_query:
            try:
                search_call_count+=1
                authority_found=self.search(
                    authority_query,
                    allow_network=allow_network,
                    freshness=freshness,
                    limit=search_limit,
                    config=config,
                )
            except Exception as exc:
                authority_error={
                    'error_code':getattr(exc,'code','authority_search_failed'),
                }

        search_call_count+=1
        found=self.search(
            query,
            allow_network=allow_network,
            freshness=freshness,
            limit=search_limit,
            config=config,
        )

        merged_results=[]
        seen_urls=set()
        for batch in (authority_found,found):
            if not batch:
                continue
            for original in batch.get('results',[]):
                url=str(original.get('url','')).strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                row=dict(original)
                row['rank']=len(merged_results)+1
                row.update(source_authority(url,query,title=row.get('title','')))
                merged_results.append(row)

        followup_query=None
        followup_found=None
        missing_facets=missing_search_facets(query,merged_results)
        if missing_facets and search_call_count<MAX_DISCOVERY_SEARCH_CALLS:
            followup_query=facet_search_query(query,missing_facets[0])
            search_call_count+=1
            try:
                followup_found=self.search(
                    followup_query,
                    allow_network=allow_network,
                    freshness=freshness,
                    limit=search_limit,
                    config=config,
                )
            except Exception:
                followup_found=None
            if followup_found:
                for original in followup_found.get('results',[]):
                    url=str(original.get('url','')).strip()
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    row=dict(original)
                    row['rank']=len(merged_results)+1
                    row.update(source_authority(url,query,title=row.get('title','')))
                    merged_results.append(row)

        fetched=[]
        sources=[]
        failures=[]
        snippet_fallback_count=0
        fetch_attempt_count=0
        for row in merged_results:
            if len(sources)>=limit or fetch_attempt_count>=MAX_DISCOVERY_FETCH_ATTEMPTS:break
            fetch_attempt_count+=1
            try:
                source=self.fetch(
                    row['url'],
                    allow_network=True,
                    metadata={
                        'source_title':row.get('title',''),
                        'search_provider':found['provider'],
                        'search_rank':row.get('rank'),
                        'search_result_date':row.get('published_at',''),
                        'search_age':row.get('published_at',''),
                        'search_freshness':found['freshness'],
                    },
                )
            except Exception as exc:
                failure={
                    'rank':row.get('rank'),
                    'source':row.get('url'),
                    'source_authority':row.get('source_authority'),
                    'error_code':getattr(exc,'code','public_fetch_failed'),
                    'error':str(exc)[:300],
                }
                failures.append(failure)

                title=str(row.get('title','')).strip()
                snippet=str(row.get('snippet','')).strip()
                if (
                    row.get('source_authority')=='primary'
                    and title
                    and len(snippet)>=80
                ):
                    url=str(row.get('url','')).strip()
                    content=(
                        title
                        + '\n\nSearch result snippet:\n'
                        + snippet
                    )
                    snippet_source={
                        'id':'search-'+hashlib.sha256(
                            (url+'\n'+content).encode('utf-8')
                        ).hexdigest()[:32],
                        'url':url,
                        'source_title':title,
                        'content':content,
                        'content_hash':hashlib.sha256(
                            content.encode('utf-8')
                        ).hexdigest(),
                        'trust':'UNTRUSTED_EXTERNAL',
                        'clipped':0,
                        'search_provider':found['provider'],
                        'search_rank':row.get('rank'),
                        'search_result_date':row.get('published_at',''),
                        'search_age':row.get('published_at',''),
                        'search_freshness':found['freshness'],
                        'source_authority':'primary',
                        'source_authority_score':1.0,
                        'source_authority_kind':row.get('source_authority_kind'),
                        'research_authority_score':row.get('research_authority_score'),
                        'claim_authority_fit':row.get('claim_authority_fit'),
                        'source_independence_key':row.get('source_independence_key'),
                        'transport_confidence':0.75,
                        'authority_domain':row.get('authority_domain'),
                        'source_transport':'search_snippet',
                        'fetch_status':'blocked',
                        'fetch_error':failure['error'],
                    }
                    sources.append(snippet_source)
                    snippet_fallback_count+=1
                continue

            source=dict(source)
            source.update(source_authority(
                source.get('url',''),
                query,
                title=source.get('source_title',''),
            ))
            source['source_transport']='fetched_page'
            source['transport_confidence']=1.0
            source['fetch_status']='fetched'
            image_url=row.get('image_url')
            if image_url:
                source['_image_candidate_url']=image_url
            fetched.append(source)
            sources.append(source)

        strategy=found.get('strategy')
        if authority_query:
            strategy=(
                'authority_first'
                + (f'+{strategy}' if strategy else '')
            )

        result={
            'provider':found['provider'],
            'freshness':freshness,
            'configuration':found['configuration'],
            'search_strategy':strategy,
            'provider_time_range':found.get('provider_time_range'),
            'search_result_count':len(merged_results),
            'search_call_count':search_call_count,
            'search_call_budget':MAX_DISCOVERY_SEARCH_CALLS,
            'followup_query':followup_query,
            'followup_facet':missing_facets[0].event.value if missing_facets else None,
            'page_fetch_attempt_count':fetch_attempt_count,
            'page_fetch_attempt_budget':MAX_DISCOVERY_FETCH_ATTEMPTS,
            'fetched_count':len(fetched),
            'snippet_fallback_count':snippet_fallback_count,
            'fetch_failure_count':len(failures),
            'failures':failures,
            'authority_search_attempted':bool(authority_query),
            'authority_domains':list(preferred_primary_domains(query)),
            'authority_search_result_count':(
                len(authority_found.get('results',[]))
                if authority_found
                else 0
            ),
            'sources':sources,
        }
        if authority_error is not None:
            result['authority_search_error']=authority_error
        return result

    def fetch_image(self,url: str,*,allow_network=False,source_id=None):
        if allow_network is not True:
            raise ValueError('Explicit network opt-in is required for public images')
        if not isinstance(source_id,str) or not source_id:
            raise ValueError('Public images require searched source provenance')
        source=self.get(source_id)
        if (
            not source.get('search_provider')
            or source.get('search_freshness') not in {'day','week','month','year'}
        ):
            raise ValueError('Public images require fresh searched source provenance')
        if source.get('image_id'):
            return self.image_metadata(source['image_id'])

        from .image_worker import ALLOWED_MEDIA_TYPES,MAX_IMAGE_BYTES,validate_image_url
        validate_image_url(url)
        try:
            result=subprocess.run(
                image_worker_argv(),
                input=json.dumps({'url':url}),
                text=True,
                capture_output=True,
                timeout=20,
                env={},
                cwd='/tmp',
                close_fds=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError('Public image exceeded its time limit') from exc
        if len(result.stdout)>3_000_000:
            raise ValueError('Public image worker output exceeded limit')
        if result.returncode:
            try:message=json.loads(result.stdout)['error']
            except (ValueError,KeyError):message='Restricted public-image sandbox could not start'
            raise ValueError(str(message)[:1000])
        try:data=json.loads(result.stdout)
        except ValueError as exc:raise ValueError('Invalid public-image worker output') from exc
        if data.get('url')!=url or data.get('media_type') not in ALLOWED_MEDIA_TYPES:
            raise ValueError('Invalid public-image worker output')
        try:content=base64.b64decode(data.get('data',''),validate=True)
        except Exception as exc:raise ValueError('Invalid public-image encoding') from exc
        byte_count=data.get('bytes')
        if (
            not isinstance(byte_count,int)
            or isinstance(byte_count,bool)
            or byte_count!=len(content)
            or byte_count>MAX_IMAGE_BYTES
            or hashlib.sha256(content).hexdigest()!=data.get('content_hash')
        ):
            raise ValueError('Invalid public-image integrity metadata')

        identity=uuid.uuid4().hex
        with sqlite3.connect(self.path) as db:
            db.execute(
                'INSERT INTO public_images(id,source_id,url,media_type,content_hash,byte_count,content,search_provider,search_rank) VALUES(?,?,?,?,?,?,?,?,?)',
                (
                    identity,source_id,url,data['media_type'],data['content_hash'],
                    byte_count,content,source.get('search_provider'),source.get('search_rank'),
                ),
            )
            db.execute('UPDATE public_sources SET image_id=? WHERE id=?',(identity,source_id))
        return self.image_metadata(identity)

    def image_metadata(self,identity):
        with sqlite3.connect(self.path) as db:
            db.row_factory=sqlite3.Row
            row=db.execute(
                'SELECT id,source_id,media_type,content_hash,byte_count,search_provider,search_rank,created_at FROM public_images WHERE id=?',
                (identity,),
            ).fetchone()
        if row is None:raise KeyError('Unknown public image')
        return dict(row)

    def image(self,identity):
        with sqlite3.connect(self.path) as db:
            db.row_factory=sqlite3.Row
            row=db.execute('SELECT id,media_type,content FROM public_images WHERE id=?',(identity,)).fetchone()
        if row is None:raise KeyError('Unknown public image')
        return {'id':row['id'],'media_type':row['media_type'],'content':bytes(row['content'])}

    def search_status(self):
        from .search import WebSearchError,configured_web_search
        try:
            settings=configured_web_search()
        except WebSearchError as exc:
            return {
                'configured':False,
                'error_code':getattr(exc,'code','network_search_unavailable'),
                'error':str(exc),
            }
        if settings is None:return {'configured':False}
        return {'configured':True,**settings.safe_metadata()}

    def get(self,identity):
        with sqlite3.connect(self.path) as db:
            db.row_factory=sqlite3.Row
            row=db.execute('SELECT * FROM public_sources WHERE id=?',(identity,)).fetchone()
        if row is None:raise KeyError('Unknown public source')
        return dict(row)
