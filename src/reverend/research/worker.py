"""Standalone stdlib worker launched in a minimal bubblewrap filesystem."""
from __future__ import annotations
import ctypes
import errno
import hashlib
import http.client
import ipaddress
import json
import re
import socket
import ssl
import sys
from html.parser import HTMLParser
from urllib.parse import urlsplit

MAX_BYTES=2_000_000


def validate_url(url):
    if not isinstance(url,str) or not 1<=len(url)<=2000 or any(ord(c)<33 for c in url):raise ValueError('Invalid public URL')
    parsed=urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.port not in (None,443):
        raise ValueError('Only public HTTPS URLs on port 443 without credentials or fragments are supported')
    return parsed


def public_addresses(host):
    addresses=list(dict.fromkeys(row[4][0] for row in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)))
    if not addresses or len(addresses)>16:raise ValueError('Invalid public DNS answer')
    for address in addresses:
        ip=ipaddress.ip_address(address)
        if not ip.is_global or getattr(ip,'ipv4_mapped',None) is not None:raise ValueError('Private, local and mapped network addresses are refused')
    return addresses


def deny_process_execution():
    """No shell/subprocess capability after startup. Fail closed without seccomp."""
    library=ctypes.CDLL('libseccomp.so.2')
    library.seccomp_init.argtypes=[ctypes.c_uint32];library.seccomp_init.restype=ctypes.c_void_p
    library.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p];library.seccomp_syscall_resolve_name.restype=ctypes.c_int
    library.seccomp_rule_add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint]
    library.seccomp_load.argtypes=[ctypes.c_void_p]
    library.seccomp_release.argtypes=[ctypes.c_void_p]
    ctx=library.seccomp_init(0x7fff0000)  # SCMP_ACT_ALLOW
    if not ctx:raise RuntimeError('Cannot initialize research syscall boundary')
    try:
        for name in ('execve','execveat','fork','vfork','clone','clone3','ptrace','process_vm_readv','process_vm_writev','mount','umount2','unshare','setns','bpf','io_uring_setup'):
            number=library.seccomp_syscall_resolve_name(name.encode())
            if number>=0 and library.seccomp_rule_add(ctx,0x00050000|errno.EPERM,number,0)!=0:
                raise RuntimeError('Cannot restrict research worker')
        if library.seccomp_load(ctx)!=0:raise RuntimeError('Cannot enforce research worker boundary')
    finally:library.seccomp_release(ctx)


def _normalize_text(value: str) -> str:
    value=value.replace("\r\n","\n").replace("\r","\n")
    value=re.sub(r"[ \t\f\v]+"," ",value)
    value=re.sub(r" *\n *","\n",value)
    return re.sub(r"\n{3,}","\n\n",value).strip()


class Text(HTMLParser):
    HIDDEN={"script","style","noscript","template","svg","canvas"}
    SUPPRESSED={"nav","header","footer","aside","form","button","dialog"}
    BLOCK={"p","div","br","h1","h2","h3","h4","h5","h6","li","pre","tr","section","article","main"}
    PUBLISHED_DATE_KEYS={
        "article:published_time","datepublished","date","pubdate",
        "publishdate","publish_date","dc.date","dc.date.issued",
    }
    UPDATED_DATE_KEYS={
        "article:modified_time","datemodified","dateupdated","modified",
        "last-modified","last_modified","dc.date.modified",
    }

    def __init__(self):
        super().__init__()
        self.hidden=0
        self.suppressed=0
        self.primary=0
        self.in_title=0
        self.parts=[]
        self.primary_parts=[]
        self.title_parts=[]
        self.published=[]
        self.updated=[]
        self.generic_dates=[]

    def _visible(self):
        return not self.hidden and not self.suppressed

    def _append(self,value):
        if not self._visible():
            return
        self.parts.append(value)
        if self.primary:
            self.primary_parts.append(value)

    def handle_starttag(self,tag,attrs):
        tag=tag.lower()
        values={str(k).lower():str(v or "") for k,v in attrs}
        if tag in self.HIDDEN:
            self.hidden+=1
        if tag in self.SUPPRESSED:
            self.suppressed+=1
        if tag in {"main","article"}:
            self.primary+=1
        if tag=="title":
            self.in_title+=1
        if tag=="meta":
            key=(
                values.get("property")
                or values.get("name")
                or values.get("itemprop")
                or ""
            ).strip().lower()
            content=values.get("content","").strip()
            if key in self.PUBLISHED_DATE_KEYS and content:
                self.published.append(content[:100])
            if key in self.UPDATED_DATE_KEYS and content:
                self.updated.append(content[:100])
        if tag=="time":
            value=values.get("datetime","").strip()
            if value:
                self.generic_dates.append(value[:100])
        if tag in self.BLOCK:
            self._append("\n")

    def handle_endtag(self,tag):
        tag=tag.lower()
        if tag in self.BLOCK:
            self._append("\n")
        if tag=="title":
            self.in_title=max(0,self.in_title-1)
        if tag in {"main","article"}:
            self.primary=max(0,self.primary-1)
        if tag in self.SUPPRESSED:
            self.suppressed=max(0,self.suppressed-1)
        if tag in self.HIDDEN:
            self.hidden=max(0,self.hidden-1)

    def handle_data(self,data):
        if not self._visible():
            return
        self.parts.append(data)
        if self.primary:
            self.primary_parts.append(data)
        if self.in_title:
            self.title_parts.append(data)

    def text(self):
        primary=_normalize_text("".join(self.primary_parts))
        fallback=_normalize_text("".join(self.parts))
        return primary if len(primary)>=200 else fallback

    def title(self):
        return _normalize_text("".join(self.title_parts))[:500]

    def published_at(self):
        explicit=next((value for value in self.published if value.strip()),"")
        if explicit:
            return explicit
        return next((value for value in self.generic_dates if value.strip()),"")

    def updated_at(self):
        return next((value for value in self.updated if value.strip()),"")


def fetch(url):
    parsed=validate_url(url)
    addresses=public_addresses(parsed.hostname)
    context=ssl.create_default_context()
    class PinnedHTTPS(http.client.HTTPSConnection):
        def connect(self):
            sock=socket.create_connection((addresses[0],443),timeout=8)
            self.sock=context.wrap_socket(sock,server_hostname=parsed.hostname)
    connection=PinnedHTTPS(parsed.hostname,timeout=8)
    try:
        connection.request(
            'GET',
            (parsed.path or '/')+('?' + parsed.query if parsed.query else ''),
            headers={
                'User-Agent':(
                    'Mozilla/5.0 (X11; Linux x86_64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/131.0.0.0 Safari/537.36'
                ),
                'Accept':(
                    'text/html,application/xhtml+xml,text/plain;'
                    'q=0.9,*/*;q=0.1'
                ),
                'Accept-Language':'en-GB,en;q=0.9',
                'Accept-Encoding':'identity',
            },
        )
        response=connection.getresponse()
        if 300<=response.status<400:raise ValueError('Redirects are refused; supply the final public URL')
        if response.status!=200:raise ValueError('Public source returned HTTP '+str(response.status))
        content_type=response.getheader('Content-Type','').split(';')[0].strip().lower()
        if content_type not in {'text/html','text/plain'}:raise ValueError('Only HTML and plain text documentation is supported')
        if response.getheader('Content-Encoding','identity')!='identity':raise ValueError('Compressed sources are refused')
        raw=response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ValueError('Source exceeds two megabytes')
        content=raw.decode('utf-8',errors='replace')
        published_at=''
        updated_at=''
        source_title=''
        if content_type=='text/html':
            parser=Text()
            parser.feed(content)
            content=parser.text()
            published_at=parser.published_at()
            updated_at=parser.updated_at()
            source_title=parser.title()
        else:
            content=_normalize_text(content)
        return {
            'url':url,
            'content':content[:24000],
            'content_hash':hashlib.sha256(raw).hexdigest(),
            'trust':'UNTRUSTED_EXTERNAL',
            'clipped':len(content)>24000,
            'bytes':len(raw),
            'published_at':published_at,
            'updated_at':updated_at,
            'source_title':source_title,
        }
    finally:connection.close()


def main():
    try:
        payload=json.loads(sys.stdin.read(4097))
        if set(payload)!={'url'}:raise ValueError('Expected one public URL')
        validate_url(payload['url'])
        deny_process_execution()
        result=fetch(payload['url'])
        print(json.dumps(result))
    except Exception as exc:
        print(json.dumps({'error':str(exc)[:1000]}));return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
