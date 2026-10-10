"""Localhost guard: the service can later start processes, so only this machine's window may talk to it."""

POST_HEADER = "X-CC"


def host_ok(host_header, port: int) -> bool:
    """True when the Host header names this service on loopback."""
    return host_header in (f"127.0.0.1:{port}", f"localhost:{port}")


def post_ok(headers) -> bool:
    """POSTs must carry X-CC: 1 (a plain HTML form or image tag cannot add it)."""
    return headers.get(POST_HEADER) == "1"
