"""Controlled public-Web gateway: search, read, extract and normalize only."""
from __future__ import annotations

import datetime
import html
import http.client
import ipaddress
import json
import pathlib
import re
import socket
import ssl
import time
import urllib.robotparser
import xml.etree.ElementTree as ET
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

USER_AGENT = "Atlas-Controlled-Research/2.0 (+local evidence research; no automated contact)"
BLOCKED_SUFFIXES = (".local", ".localhost", ".internal", ".lan", ".home", ".onion")
BLOCKED_PATH_WORDS = {"login", "signin", "sign-in", "auth", "oauth", "captcha", "checkout", "cart", "payment", "admin", "upload"}
BLOCKED_EXTENSIONS = {".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".apk", ".iso", ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".bin", ".scr", ".bat", ".cmd", ".ps1", ".jar"}
SENSITIVE_QUERY_KEYS = {"password", "passwd", "token", "api_key", "apikey", "secret", "authorization", "auth", "session", "cookie", "code"}
WEB_REQUESTS: list[float] = []
ROBOTS: dict[str, object] = {}
LAST_WEB = 0.0


def _text(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise ValueError("Invalid or oversized string")
    return value.strip()


def canonical_url(url):
    parsed = urlsplit(_text(url, 2000))
    host = (parsed.hostname or "").rstrip(".").lower()
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443) or not host or parsed.fragment:
        raise ValueError("BLOCKED_BY_POLICY: HTTPS public URL required; credentials, fragments and custom ports forbidden")
    try:
        ipaddress.ip_address(host)
        raise ValueError("BLOCKED_BY_POLICY: IP literals are forbidden")
    except ValueError as error:
        if "BLOCKED_BY_POLICY" in str(error):
            raise
    if "." not in host or not re.fullmatch(r"[a-z0-9.-]+", host) or any(part.startswith("xn--") for part in host.split(".")):
        raise ValueError("BLOCKED_BY_POLICY: ambiguous or non-public hostname")
    if host.endswith(BLOCKED_SUFFIXES):
        raise ValueError("BLOCKED_BY_POLICY: dangerous domain suffix")
    segments = {unquote(part).casefold() for part in parsed.path.split("/") if part}
    if segments & BLOCKED_PATH_WORDS:
        raise ValueError("BLOCKED_BY_POLICY: login, CAPTCHA, payment or upload path")
    if pathlib.PurePosixPath(parsed.path).suffix.casefold() in BLOCKED_EXTENSIONS:
        raise ValueError("BLOCKED_BY_POLICY: dangerous download type")
    if any(key.casefold() in SENSITIVE_QUERY_KEYS for key, _ in parse_qsl(parsed.query, keep_blank_values=True)):
        raise ValueError("BLOCKED_BY_POLICY: sensitive query parameter")
    return urlunsplit(("https", host, re.sub("/+", "/", parsed.path or "/"), parsed.query, ""))


def _global_address(host):
    addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("BLOCKED_BY_POLICY: private, loopback, reserved and metadata addresses blocked")
    return sorted(addresses, key=lambda value: (ipaddress.ip_address(value).version, value))[0]


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, hostname, address):
        super().__init__(hostname, timeout=12, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        raw = socket.create_connection((self.address, 443), timeout=self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


def _web_slot():
    global LAST_WEB
    current = time.monotonic()
    wait = 1.0 - (current - LAST_WEB)
    if wait > 0:
        time.sleep(wait)
    current = time.monotonic()
    WEB_REQUESTS[:] = [stamp for stamp in WEB_REQUESTS if current - stamp < 600]
    if len(WEB_REQUESTS) >= 30:
        raise ValueError("BLOCKED_BY_POLICY: Web request budget exhausted (30/10min)")
    WEB_REQUESTS.append(current)
    LAST_WEB = current


def _request_public(url, accept, limit=300000):
    normalized = canonical_url(url)
    parsed = urlsplit(normalized)
    address = _global_address(parsed.hostname)
    last_error = None
    for attempt in range(2):
        _web_slot()
        connection = PinnedHTTPS(parsed.hostname, address)
        try:
            target = (parsed.path or "/") + ("?" + parsed.query if parsed.query else "")
            connection.request("GET", target, headers={"User-Agent": USER_AGENT, "Accept": accept, "Accept-Encoding": "identity"})
            response = connection.getresponse()
            body = response.read(limit + 1)
            if response.status == 200:
                return normalized, response, body[:limit]
            if response.status in (429, 500, 502, 503, 504) and attempt == 0:
                last_error = "HTTP " + str(response.status)
                time.sleep(1)
                continue
            raise ValueError("HTTP " + str(response.status) + "; redirects, authentication and paywalls are not followed")
        except (OSError, TimeoutError) as error:
            last_error = type(error).__name__
            if attempt == 0:
                time.sleep(1)
                continue
            raise ValueError("Web request failed after bounded retry: " + last_error)
        finally:
            connection.close()
    raise ValueError("Web request failed after bounded retry: " + str(last_error))


def _robots_allowed(url):
    parsed = urlsplit(url)
    host = parsed.hostname
    if host not in ROBOTS:
        robots_url = "https://" + host + "/robots.txt"
        try:
            _, _, body = _request_public(robots_url, "text/plain", 100000)
            policy = urllib.robotparser.RobotFileParser()
            policy.set_url(robots_url)
            policy.parse(body.decode("utf-8", "replace").splitlines())
            ROBOTS[host] = policy
        except ValueError as error:
            if "HTTP 404" in str(error):
                ROBOTS[host] = True
            else:
                raise ValueError("BLOCKED_BY_POLICY: robots policy unavailable")
    policy = ROBOTS[host]
    return policy is True or policy.can_fetch(USER_AGENT, url)


def _source_type(host, path):
    if host.endswith((".gov", ".gov.uk", ".europa.eu")):
        return "public_authority"
    if host.endswith((".edu", ".ac.uk")):
        return "academic"
    if "docs" in host or "/docs" in path:
        return "documentation"
    if any(word in host for word in ("news", "reuters", "apnews")):
        return "news"
    if any(word in path.casefold() for word in ("pricing", "plans", "product")):
        return "product_or_pricing"
    return "public_web"


def search_web(query):
    query = _text(query, 200)
    if any(word in query.casefold() for word in ("password", "api key", "private key", "seed phrase", "mnemonic", "token")):
        raise ValueError("BLOCKED_BY_POLICY: sensitive search query")
    stop={"small","business","software","pricing","price","market","team","teams","public","tool","tools"}
    provider_query=" ".join([word for word in re.findall(r"[a-z0-9]+",query.casefold()) if word not in stop][:4]) or query
    results=[]
    providers=[]
    wikipedia="https://en.wikipedia.org/w/api.php?"+urlencode({"action":"query","list":"search","srsearch":query,"format":"json","srlimit":5})
    _,_,body=_request_public(wikipedia,"application/json",200000)
    for item in json.loads(body).get("query",{}).get("search",[]):
        title=str(item.get("title", ""))
        results.append({"title":title,"url":"https://en.wikipedia.org/wiki/"+title.replace(" ","_"),"description":re.sub(r"\s+"," ",html.unescape(re.sub("<[^>]+>"," ",item.get("snippet", ""))))[:1000],"date":"","provider":"Wikipedia"})
    providers.append("Wikipedia")
    hackernews="https://hn.algolia.com/api/v1/search?"+urlencode({"query":provider_query,"tags":"story","hitsPerPage":5})
    _,_,body=_request_public(hackernews,"application/json",200000)
    for item in json.loads(body).get("hits",[]):
        link=item.get("url") or ("https://news.ycombinator.com/item?id="+str(item.get("objectID", "")))
        results.append({"title":str(item.get("title") or "Hacker News discussion")[:300],"url":link,"description":str(item.get("story_text") or "Public product and market discussion")[:1000],"date":str(item.get("created_at") or "")[:80],"provider":"Hacker News Algolia"})
    providers.append("Hacker News Algolia")
    github="https://api.github.com/search/repositories?"+urlencode({"q":provider_query,"sort":"stars","order":"desc","per_page":5})
    _,_,body=_request_public(github,"application/json",300000)
    for item in json.loads(body).get("items",[]):
        results.append({"title":str(item.get("full_name") or item.get("name") or "GitHub repository")[:300],"url":item.get("html_url", ""),"description":str(item.get("description") or "Public software repository")[:1000],"date":str(item.get("updated_at") or "")[:80],"provider":"GitHub public API"})
    providers.append("GitHub public API")
    seen = set()
    normalized=[]
    for item in results:
        link=item.get("url", "")
        try:
            link = canonical_url(link)
        except ValueError:
            continue
        if link in seen:
            continue
        seen.add(link);normalized.append({**item,"url":link})
    if not normalized:
        raise ValueError("Search returned no safe public results")
    buckets={provider:[item for item in normalized if item.get("provider")==provider] for provider in providers}
    interleaved=[]
    for index in range(5):
        for provider in providers:
            if index<len(buckets[provider]):interleaved.append(buckets[provider][index])
    return {"untrusted":True,"provider":"Atlas federated public APIs","providers":providers,"query":query,"retrieved_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"results":interleaved[:12]}


def fetch(url):
    normalized = canonical_url(url)
    if not _robots_allowed(normalized):
        raise ValueError("BLOCKED_BY_POLICY: robots.txt disallows retrieval")
    normalized, response, data = _request_public(normalized, "text/html,text/plain,application/json,application/xhtml+xml,application/xml", 300000)
    content_type = response.getheader("Content-Type", "").split(";")[0]
    if content_type not in ("text/html", "text/plain", "application/json", "application/xhtml+xml", "text/xml", "application/xml"):
        raise ValueError("BLOCKED_BY_POLICY: unsupported or dangerous content type")
    source = data.decode("utf-8", "replace")
    title_match = re.search(r"<title[^>]*>(.*?)</title>", source, re.S | re.I)
    date_match = re.search(r"(?:article:published_time|datePublished|pubdate)[^>]{0,160}(\d{4}-\d{2}-\d{2}[^<\"' ]*)", source, re.I)
    source = re.sub(r"<(script|style|noscript|svg)\b[^>]*>.*?</\1>", " ", source, flags=re.S | re.I)
    plain = re.sub(r"\s+", " ", html.unescape(re.sub("<[^>]+>", " ", source))).strip()
    if re.search(r"verify you are human|complete (?:the )?captcha|captcha challenge|access denied.{0,80}captcha", plain, re.I):
        raise ValueError("BLOCKED_BY_POLICY: CAPTCHA or anti-bot challenge; no bypass attempted")
    parsed = urlsplit(normalized)
    return {
        "untrusted": True,
        "url": normalized,
        "domain": parsed.hostname,
        "title": re.sub(r"\s+", " ", html.unescape(title_match.group(1))).strip()[:300] if title_match else parsed.hostname,
        "date": date_match.group(1)[:80] if date_match else None,
        "retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "excerpt": plain[:6000],
        "source_type": _source_type(parsed.hostname, parsed.path),
        "confidence": "unverified_single_source",
        "robots_allowed": True,
        "content_type": content_type,
    }
