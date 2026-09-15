"""Sandboxed JSON search client for Brave Search and SearXNG."""
from __future__ import annotations

import ctypes
import errno
import http.client
import ipaddress
import json
import re
import socket
import ssl
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit, urlunsplit

MAX_RESPONSE_BYTES=2_000_000
BRAVE_ENDPOINT="https://api.search.brave.com/res/v1/web/search"
FRESHNESS_BRAVE={"day":"pd","week":"pw","month":"pm","year":"py"}
# The public SearXNG API documents day/month/year while current SearXNG
# internals also accept week. Reverend probes native week first, then uses
# a tighter day subset, and finally a dated month fallback.
FRESHNESS_SEARX={"day":"day","week":"month","month":"month","year":"year"}


class SearchProviderError(RuntimeError):
    def __init__(self,message: str,*,code: str="web_search_failed"):
        super().__init__(message)
        self.code=code


def classify_provider_error(status: int,payload: dict | None=None) -> tuple[str,str]:
    data=payload if isinstance(payload,dict) else {}
    provider_error=data.get("error")
    provider_code=""
    if isinstance(provider_error,dict):
        provider_code=str(provider_error.get("code","")).strip().upper()

    if status in {401,403} or provider_code=="SUBSCRIPTION_TOKEN_INVALID":
        return "network_search_auth_failed","Search provider rejected authentication"
    if status==429 or provider_code in {"RATE_LIMITED","QUOTA_LIMITED"}:
        return "web_search_rate_limited","Search provider rate limit or quota reached"
    if provider_code=="OPTION_NOT_IN_PLAN":
        return "web_search_plan_unavailable","Search provider plan does not permit this endpoint"
    if status==422:
        return "web_search_request_rejected","Search provider rejected the request"
    return "web_search_failed","Search provider returned HTTP "+str(status)


def deny_process_execution():
    library=ctypes.CDLL("libseccomp.so.2")
    library.seccomp_init.argtypes=[ctypes.c_uint32]
    library.seccomp_init.restype=ctypes.c_void_p
    library.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p]
    library.seccomp_syscall_resolve_name.restype=ctypes.c_int
    library.seccomp_rule_add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint]
    library.seccomp_load.argtypes=[ctypes.c_void_p]
    library.seccomp_release.argtypes=[ctypes.c_void_p]
    ctx=library.seccomp_init(0x7fff0000)
    if not ctx:
        raise RuntimeError("Cannot initialize search syscall boundary")
    try:
        for name in (
            "execve","execveat","fork","vfork","clone","clone3","ptrace",
            "process_vm_readv","process_vm_writev","mount","umount2",
            "unshare","setns","bpf","io_uring_setup",
        ):
            number=library.seccomp_syscall_resolve_name(name.encode())
            if number>=0 and library.seccomp_rule_add(
                ctx,0x00050000|errno.EPERM,number,0
            )!=0:
                raise RuntimeError("Cannot restrict search worker")
        if library.seccomp_load(ctx)!=0:
            raise RuntimeError("Cannot enforce search worker boundary")
    finally:
        library.seccomp_release(ctx)


def _loopback_host(host: str) -> bool:
    if host.casefold()=="localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _public_addresses(host: str, port: int) -> list[str]:
    addresses=list(
        dict.fromkeys(
            row[4][0]
            for row in socket.getaddrinfo(
                host,
                port,
                type=socket.SOCK_STREAM,
            )
        )
    )
    if not addresses or len(addresses)>16:
        raise ValueError("Invalid search-provider DNS answer")
    for address in addresses:
        ip=ipaddress.ip_address(address)
        if not ip.is_global or getattr(ip,"ipv4_mapped",None) is not None:
            raise ValueError("Private or local search-provider address refused")
    return addresses


def validate_search_endpoint(provider: str, endpoint: str):
    if provider not in {"brave","searxng"}:
        raise ValueError("Unsupported search provider")
    parsed=urlsplit(endpoint)
    if (
        parsed.username
        or parsed.password
        or parsed.fragment
        or parsed.query
        or not parsed.hostname
    ):
        raise ValueError("Invalid search-provider endpoint")

    if provider=="brave":
        if endpoint.rstrip("/")!=BRAVE_ENDPOINT:
            raise ValueError("Invalid Brave Search endpoint")
        if parsed.scheme!="https" or parsed.port not in (None,443):
            raise ValueError("Brave Search must use public HTTPS")
        return parsed

    if parsed.scheme=="http":
        if not _loopback_host(parsed.hostname):
            raise ValueError("Plain HTTP SearXNG is allowed only on loopback")
    elif parsed.scheme=="https":
        if not _loopback_host(parsed.hostname) and parsed.port not in (None,443):
            raise ValueError("Public SearXNG HTTPS must use port 443")
    else:
        raise ValueError("SearXNG endpoint must use HTTP or HTTPS")
    return parsed


def _connection(parsed):
    port=parsed.port or (443 if parsed.scheme=="https" else 80)
    if parsed.scheme=="http":
        return http.client.HTTPConnection(
            parsed.hostname,
            port,
            timeout=10,
        )

    if _loopback_host(parsed.hostname):
        return http.client.HTTPSConnection(
            parsed.hostname,
            port,
            timeout=10,
            context=ssl.create_default_context(),
        )

    addresses=_public_addresses(parsed.hostname,port)
    context=ssl.create_default_context()

    class PinnedHTTPS(http.client.HTTPSConnection):
        def connect(self):
            sock=socket.create_connection(
                (addresses[0],port),
                timeout=10,
            )
            self.sock=context.wrap_socket(
                sock,
                server_hostname=parsed.hostname,
            )

    return PinnedHTTPS(
        parsed.hostname,
        port,
        timeout=10,
        context=context,
    )


def _clean_text(value, limit: int) -> str:
    text=re.sub(r"<[^>]{0,200}>"," ",str(value or ""))
    text=re.sub(r"\s+"," ",text).strip()
    return text[:limit]


def _published_within_days(value,days: int,*,now=None) -> bool:
    text=str(value or "").strip()
    if not text:
        return False
    try:
        parsed=datetime.fromisoformat(text.replace("Z","+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed=parsed.replace(tzinfo=timezone.utc)
    reference=now or datetime.now(timezone.utc)
    age=reference.astimezone(timezone.utc)-parsed.astimezone(timezone.utc)
    return timedelta(0)<=age<=timedelta(days=days)


def _result_url(value) -> str | None:
    try:
        parsed=urlsplit(str(value or ""))
    except ValueError:
        return None
    if (
        parsed.scheme!="https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in (None,443)
    ):
        return None
    return urlunsplit(
        (
            "https",
            parsed.netloc,
            parsed.path or "/",
            parsed.query,
            "",
        )
    )


def normalize_results(provider: str, payload: dict, limit: int) -> list[dict]:
    if provider=="brave":
        rows=((payload.get("web") or {}).get("results") or [])
    else:
        rows=payload.get("results") or []
    if not isinstance(rows,list):
        raise ValueError("Search provider returned invalid results")

    result=[]
    seen=set()
    for row in rows:
        if not isinstance(row,dict):
            continue
        url=_result_url(row.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        published=(
            row.get("page_age")
            or row.get("publishedDate")
            or row.get("published_date")
            or row.get("age")
        )
        normalized={
            "rank":len(result)+1,
            "url":url,
            "title":_clean_text(row.get("title"),500),
            "snippet":_clean_text(
                row.get("description")
                if provider=="brave"
                else row.get("content"),
                1200,
            ),
            "published_at":_clean_text(published,100),
        }
        image_candidate=row.get("thumbnail")
        if isinstance(image_candidate,dict):
            image_candidate=(
                image_candidate.get("src")
                or image_candidate.get("original")
            )
        if not image_candidate and provider!="brave":
            image_candidate=row.get("img_src")
        image_url=_result_url(image_candidate)
        if image_url:
            normalized["image_url"]=image_url
        result.append(normalized)
        if len(result)>=limit:
            break
    return result


def _searx_categories(freshness: str) -> str:
    return "general" if freshness=="stable" else "general,news"


def _searx_week_ranges() -> tuple[str, ...]:
    return ("week","day","month")


def _read_json_response(response) -> dict:
    content_type=response.getheader("Content-Type","").split(";")[0].strip().lower()
    if response.status!=200:
        raw=response.read(65537)
        provider_payload={}
        if len(raw)<=65536 and content_type in {"application/json","text/json"}:
            try:
                decoded=json.loads(raw.decode("utf-8",errors="strict"))
                if isinstance(decoded,dict):
                    provider_payload=decoded
            except (UnicodeDecodeError,json.JSONDecodeError):
                provider_payload={}
        code,message=classify_provider_error(response.status,provider_payload)
        raise SearchProviderError(message,code=code)
    if content_type not in {"application/json","text/json"}:
        raise ValueError("Search provider did not return JSON")
    if response.getheader("Content-Encoding","identity")!="identity":
        raise ValueError("Compressed search responses are refused")
    raw=response.read(MAX_RESPONSE_BYTES+1)
    if len(raw)>MAX_RESPONSE_BYTES:
        raise ValueError("Search response exceeded two megabytes")
    data=json.loads(raw.decode("utf-8",errors="strict"))
    if not isinstance(data,dict):
        raise ValueError("Search provider returned invalid JSON")
    return data


def _searx_week_results(data: dict, provider_range: str, limit: int) -> list[dict]:
    normalize_limit=10 if provider_range=="month" else limit
    results=normalize_results("searxng",data,normalize_limit)
    if provider_range=="month":
        results=[
            row for row in results
            if _published_within_days(row.get("published_at"),7)
        ]
    return results[:limit]


def search(payload: dict) -> dict:
    provider=str(payload.get("provider","")).strip().lower()
    endpoint=str(payload.get("endpoint","")).strip()
    query=str(payload.get("query","")).strip()
    api_key=str(payload.get("api_key","") or "")
    freshness=str(payload.get("freshness","stable")).strip().lower()
    country=str(payload.get("country","GB")).strip().upper()
    language=str(payload.get("language","en")).strip().lower()
    limit=payload.get("limit",6)

    if (
        not query
        or len(query)>600
        or len(query.split())>75
        or not isinstance(limit,int)
        or isinstance(limit,bool)
        or not 1<=limit<=10
        or freshness not in {"stable","day","week","month","year"}
        or not re.fullmatch(r"[A-Z]{2}",country)
        or not re.fullmatch(r"[a-z]{2,8}(?:-[a-z0-9]{2,8})?",language)
    ):
        raise ValueError("Invalid bounded web-search request")

    parsed=validate_search_endpoint(provider,endpoint)
    headers={
        "Accept":"application/json",
        "Accept-Encoding":"identity",
        "User-Agent":"Reverend-Web-Search/1",
    }
    connection=_connection(parsed)
    try:
        if provider=="brave":
            if not api_key or len(api_key)>512:
                raise ValueError("Brave Search credential unavailable")
            headers["X-Subscription-Token"]=api_key
            params={
                "q":query,
                "count":limit,
                "country":country,
                "search_lang":language.split("-")[0],
                "safesearch":"moderate",
                "text_decorations":"false",
            }
            if freshness!="stable":
                params["freshness"]=FRESHNESS_BRAVE[freshness]
            path=parsed.path+"?"+urlencode(params)
            connection.request("GET",path,headers=headers)
            data=_read_json_response(connection.getresponse())
            return {
                "provider":provider,
                "freshness":freshness,
                "strategy":"brave",
                "results":normalize_results(provider,data,limit),
            }

        base=parsed.path.rstrip("/")
        base_path=(base if base.endswith("/search") else base+"/search") or "/search"
        base_params={
            "q":query,
            "format":"json",
            "language":language,
            "safesearch":"1",
            "categories":_searx_categories(freshness),
        }

        if freshness=="week":
            last_strategy="native_week"
            for provider_range,strategy in (
                ("week","native_week"),
                ("day","day_subset"),
                ("month","dated_month"),
            ):
                params=dict(base_params)
                params["time_range"]=provider_range
                path=base_path+"?"+urlencode(params)
                try:
                    connection.request("GET",path,headers=headers)
                    data=_read_json_response(connection.getresponse())
                except SearchProviderError as exc:
                    if (
                        provider_range=="week"
                        and exc.code=="web_search_request_rejected"
                    ):
                        last_strategy="native_week_rejected"
                        continue
                    raise
                results=_searx_week_results(data,provider_range,limit)
                last_strategy=strategy
                if results:
                    return {
                        "provider":provider,
                        "freshness":freshness,
                        "strategy":strategy,
                        "provider_time_range":provider_range,
                        "results":results,
                    }
            return {
                "provider":provider,
                "freshness":freshness,
                "strategy":last_strategy,
                "provider_time_range":"month",
                "results":[],
            }

        params=dict(base_params)
        provider_range=None
        if freshness!="stable":
            provider_range=FRESHNESS_SEARX[freshness]
            params["time_range"]=provider_range
        path=base_path+"?"+urlencode(params)
        connection.request("GET",path,headers=headers)
        data=_read_json_response(connection.getresponse())
        return {
            "provider":provider,
            "freshness":freshness,
            "strategy":"searxng",
            "provider_time_range":provider_range,
            "results":normalize_results(provider,data,limit),
        }
    finally:
        connection.close()

def main():
    try:
        payload=json.loads(sys.stdin.read(16385))
        if not isinstance(payload,dict):
            raise ValueError("Expected one search request object")
        deny_process_execution()
        result=search(payload)
        print(json.dumps(result,ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({
            "error":str(exc)[:1000],
            "error_code":getattr(exc,"code","web_search_failed"),
        }))
        return 1
    return 0


if __name__=="__main__":
    raise SystemExit(main())
