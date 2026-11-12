"""Load the project .env file and normalize a Neon connection string."""

import os
from pathlib import Path


def load_env() -> None:
    for parent in Path(__file__).resolve().parents:
        path = parent / ".env"
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, value = text.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        return


def model_provider() -> str:
    """The provider name an agent version uses when none is given. One name, one adapter."""
    load_env()
    return os.environ.get("MODEL_PROVIDER", "openai").strip() or "openai"


def model_name() -> str:
    """The default model id, e.g. the one the policy drafter calls."""
    load_env()
    return os.environ.get("MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


def model_configured() -> bool:
    """True when a key is present, so callers can skip the model instead of failing."""
    load_env()
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def database_url() -> str:
    load_env()
    url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return _with_resolved_host(url)


def _with_resolved_host(url: str) -> str:
    """Keep the Neon hostname for TLS, and add an address when local DNS refuses it."""
    if "://" not in url or "hostaddr=" in url:
        return url
    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
    import socket

    parts = urlparse(url)
    if not parts.hostname:
        return url
    try:
        socket.getaddrinfo(parts.hostname, parts.port or 5432)
        return url
    except socket.gaierror:
        address = _lookup_ipv4(parts.hostname)
    if not address:
        return url
    query = dict(parse_qsl(parts.query))
    query["hostaddr"] = address
    return urlunparse(parts._replace(query=urlencode(query)))


def _lookup_ipv4(hostname: str) -> str:
    try:
        import dns.resolver
    except ImportError:
        return ""
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = ["1.1.1.1", "8.8.8.8"]
    resolver.lifetime = 5
    try:
        answer = resolver.resolve(hostname, "A")
    except Exception:
        return ""
    return str(answer[0]) if answer else ""
