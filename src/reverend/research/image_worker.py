"""Standalone restricted public-image worker for accepted searched evidence."""
from __future__ import annotations

import base64
import ctypes
import errno
import hashlib
import http.client
import ipaddress
import json
import socket
import ssl
import sys
from urllib.parse import urlsplit

MAX_IMAGE_BYTES=2_000_000
ALLOWED_MEDIA_TYPES={"image/png","image/jpeg","image/webp"}


def validate_image_url(url):
    if (
        not isinstance(url,str)
        or not 1<=len(url)<=2000
        or any(ord(char)<33 for char in url)
    ):
        raise ValueError("Invalid public image URL")
    parsed=urlsplit(url)
    if (
        parsed.scheme!="https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
        or parsed.port not in (None,443)
    ):
        raise ValueError(
            "Only public HTTPS image URLs on port 443 without credentials or fragments are supported"
        )
    return parsed


def public_addresses(host):
    addresses=list(dict.fromkeys(
        row[4][0]
        for row in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
    ))
    if not addresses or len(addresses)>16:
        raise ValueError("Invalid public image DNS answer")
    for address in addresses:
        ip=ipaddress.ip_address(address)
        if not ip.is_global or getattr(ip,"ipv4_mapped",None) is not None:
            raise ValueError("Private, local and mapped image addresses are refused")
    return addresses


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
        raise RuntimeError("Cannot initialize image syscall boundary")
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
                raise RuntimeError("Cannot restrict image worker")
        if library.seccomp_load(ctx)!=0:
            raise RuntimeError("Cannot enforce image worker boundary")
    finally:
        library.seccomp_release(ctx)


def validate_image_bytes(media_type,raw):
    if media_type not in ALLOWED_MEDIA_TYPES:
        raise ValueError("Only PNG, JPEG and WebP images are supported")
    if not isinstance(raw,(bytes,bytearray)) or not raw:
        raise ValueError("Public image is empty")
    if len(raw)>MAX_IMAGE_BYTES:
        raise ValueError("Public image exceeds two megabytes")
    if media_type=="image/png" and not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("PNG signature does not match declared media type")
    if media_type=="image/jpeg" and not raw.startswith(b"\xff\xd8\xff"):
        raise ValueError("JPEG signature does not match declared media type")
    if media_type=="image/webp" and not (
        len(raw)>=12
        and raw[:4]==b"RIFF"
        and raw[8:12]==b"WEBP"
    ):
        raise ValueError("WebP signature does not match declared media type")


def fetch(url):
    parsed=validate_image_url(url)
    addresses=public_addresses(parsed.hostname)
    context=ssl.create_default_context()

    class PinnedHTTPS(http.client.HTTPSConnection):
        def connect(self):
            sock=socket.create_connection((addresses[0],443),timeout=8)
            self.sock=context.wrap_socket(sock,server_hostname=parsed.hostname)

    connection=PinnedHTTPS(parsed.hostname,timeout=8)
    try:
        path=(parsed.path or "/")+("?" + parsed.query if parsed.query else "")
        connection.request(
            "GET",
            path,
            headers={
                "User-Agent":"Reverend-Public-Image/1",
                "Accept":"image/png,image/jpeg,image/webp",
                "Accept-Encoding":"identity",
            },
        )
        response=connection.getresponse()
        if 300<=response.status<400:
            raise ValueError("Image redirects are refused")
        if response.status!=200:
            raise ValueError("Public image returned HTTP "+str(response.status))
        media_type=response.getheader("Content-Type","").split(";")[0].strip().lower()
        if media_type not in ALLOWED_MEDIA_TYPES:
            raise ValueError("Only PNG, JPEG and WebP images are supported")
        if response.getheader("Content-Encoding","identity")!="identity":
            raise ValueError("Compressed image responses are refused")
        declared=response.getheader("Content-Length")
        if declared:
            try:
                declared_bytes=int(declared)
            except ValueError as exc:
                raise ValueError("Invalid public image content length") from exc
            if declared_bytes<0 or declared_bytes>MAX_IMAGE_BYTES:
                raise ValueError("Public image exceeds two megabytes")
        raw=response.read(MAX_IMAGE_BYTES+1)
        validate_image_bytes(media_type,raw)
        return {
            "url":url,
            "media_type":media_type,
            "content_hash":hashlib.sha256(raw).hexdigest(),
            "bytes":len(raw),
            "data":base64.b64encode(raw).decode("ascii"),
        }
    finally:
        connection.close()


def main():
    try:
        payload=json.loads(sys.stdin.read(4097))
        if not isinstance(payload,dict) or set(payload)!={"url"}:
            raise ValueError("Expected one public image URL")
        validate_image_url(payload["url"])
        deny_process_execution()
        print(json.dumps(fetch(payload["url"])))
    except Exception as exc:
        print(json.dumps({"error":str(exc)[:1000]}))
        return 1
    return 0


if __name__=="__main__":
    raise SystemExit(main())
