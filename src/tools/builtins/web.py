import json
import re
from http import HTTPStatus
from urllib.parse import urlencode, unquote, urlparse

from src.tools.builtins.text_cleaning import normalize_whitespace
from src.tools.builtins.web_helpers import is_blocked_host, is_valid_http_url, unwrap_search_result_url


def search_web(_workspace_path: str, params: dict) -> str:
    query = str(params.get("query", "")).strip()
    max_results = int(params.get("max_results", 5))

    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError("search_web requires 'requests' and 'beautifulsoup4'.") from exc

    if not query:
        raise ValueError("Query cannot be empty.")
    if len(query) > 500:
        raise ValueError("Query is too long.")
    if max_results <= 0 or max_results > 10:
        raise ValueError("max_results must be between 1 and 10.")

    browser_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
    }
    seen_urls: set[str] = set()
    combined_results: list[dict[str, str]] = []
    collect_limit = max_results * 6
    attempted_queries = _build_query_variants(query)
    provider_attempts: list[dict[str, object]] = []
    providers = (
        ("duckduckgo_html", _search_duckduckgo_html),
        ("brave_html", _search_brave_html),
        ("yahoo_html", _search_yahoo_html),
        ("bing_rss", _search_bing_rss),
    )

    for provider_name, provider_search in providers:
        provider_blocked = False
        provider_error: str | None = None
        for attempt_query in attempted_queries:
            try:
                result = provider_search(
                    query=attempt_query,
                    headers=browser_headers,
                    max_results=max_results,
                    requests_module=requests,
                    soup_module=BeautifulSoup,
                )
            except requests.RequestException as exc:
                provider_error = f"request failed for '{attempt_query}': {exc}"
                continue

            if result["blocked"]:
                provider_blocked = True
                provider_error = f"provider challenge page detected for '{attempt_query}'"
                break

            for item in result["results"]:
                href = str(item.get("url", ""))
                title = str(item.get("title", ""))
                snippet = str(item.get("snippet", ""))
                if not href or not title:
                    continue
                if not _is_relevant_result(query=attempt_query, title=title, snippet=snippet, url=href):
                    continue
                if not is_valid_http_url(href) or is_blocked_host(href):
                    continue
                if href in seen_urls:
                    continue
                seen_urls.add(href)
                combined_results.append({"title": title, "url": href, "snippet": snippet})
                if len(combined_results) >= collect_limit:
                    break
            if len(combined_results) >= collect_limit:
                break

        provider_attempts.append(
            {
                "provider": provider_name,
                "blocked": provider_blocked,
                "error": provider_error,
            }
        )
        if len(combined_results) >= collect_limit:
            break

    ranked_results = sorted(
        combined_results,
        key=lambda item: _result_priority_score(item["url"], item.get("title", "")),
    )

    payload: dict[str, object] = {
        "query": query,
        "attempted_queries": attempted_queries,
        "results": ranked_results[:max_results],
        "providers_attempted": provider_attempts,
    }
    if not combined_results:
        payload["error"] = _build_no_results_error(provider_attempts)
    return json.dumps(payload, ensure_ascii=True)


def read_url(_workspace_path: str, params: dict) -> str:
    url = str(params.get("url", "")).strip()
    timeout_seconds = int(params.get("timeout_seconds", 15))
    max_chars = int(params.get("max_chars", 8000))

    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError("read_url requires 'requests' and 'beautifulsoup4'.") from exc

    if not is_valid_http_url(url):
        raise ValueError("Invalid URL. Only http/https URLs are allowed.")
    if is_blocked_host(url):
        raise ValueError("Blocked URL host.")
    if timeout_seconds <= 0 or timeout_seconds > 60:
        raise ValueError("timeout_seconds must be between 1 and 60.")
    if max_chars < 500 or max_chars > 50000:
        raise ValueError("max_chars must be between 500 and 50000.")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=timeout_seconds)
    if response.status_code >= 400:
        payload = {
            "url": url,
            "title": "Inaccessible page",
            "text": "",
            "truncated": False,
            "accessible": False,
            "http_status": response.status_code,
            "http_reason": HTTPStatus(response.status_code).phrase
            if response.status_code in HTTPStatus._value2member_map_
            else "HTTP Error",
            "blocked_reason": _infer_blocked_reason(response.status_code),
        }
        return json.dumps(payload, ensure_ascii=True)

    content_type = (response.headers.get("content-type") or "").lower()
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        raise ValueError("Unsupported content type. Only HTML pages are supported.")

    soup = BeautifulSoup(response.text, "html.parser")
    for tag_name in ("script", "style", "noscript", "nav", "footer", "header"):
        for element in soup.find_all(tag_name):
            element.decompose()

    title = normalize_whitespace(soup.title.get_text(" ", strip=True) if soup.title else "")
    text = normalize_whitespace(soup.get_text(" ", strip=True))
    if not text:
        raise ValueError("No readable text extracted from page.")

    payload = {
        "url": url,
        "title": title or "Untitled",
        "text": text[:max_chars],
        "truncated": len(text) > max_chars,
        "accessible": True,
    }
    return json.dumps(payload, ensure_ascii=True)


def _build_query_variants(query: str) -> list[str]:
    base = query.strip()
    variants = [base, f'"{base}"']
    base_lower = base.lower()
    technical_tokens = (
        "openclaw",
        "github",
        "repository",
        "repo",
        "api",
        "sdk",
        "docs",
        "documentation",
        "tool",
        "agent",
        "framework",
        "python",
    )
    is_technical = any(token in base_lower for token in technical_tokens)
    if is_technical and "github" not in base_lower:
        variants.append(f"{base} github")
    if is_technical and "documentation" not in base_lower and "docs" not in base_lower:
        variants.append(f"{base} documentation")

    deduped: list[str] = []
    seen: set[str] = set()
    for variant in variants:
        normalized = " ".join(variant.split())
        if normalized.lower() in seen:
            continue
        seen.add(normalized.lower())
        deduped.append(normalized)
    return deduped


def _search_duckduckgo_html(*, query: str, headers: dict[str, str], max_results: int, requests_module: object, soup_module: object) -> dict[str, object]:
    params = urlencode({"q": query})
    url = f"https://duckduckgo.com/html/?{params}"
    response = requests_module.get(url, headers=headers, timeout=15)
    response.raise_for_status()

    text = response.text
    lowered = text.lower()
    if "anomaly-modal" in lowered or "bots use duckduckgo" in lowered:
        return {"blocked": True, "results": []}

    soup = soup_module(text, "html.parser")
    parsed_results: list[dict[str, str]] = []
    for result in soup.select(".result")[: max_results * 2]:
        link = result.select_one(".result__a")
        snippet = result.select_one(".result__snippet")
        if not link:
            continue
        href = unwrap_search_result_url(link.get("href", ""))
        title = link.get_text(" ", strip=True)
        if not href or not title:
            continue
        parsed_results.append(
            {"title": title, "url": href, "snippet": snippet.get_text(" ", strip=True) if snippet else ""}
        )
    return {"blocked": False, "results": parsed_results}


def _search_bing_rss(*, query: str, headers: dict[str, str], max_results: int, requests_module: object, soup_module: object) -> dict[str, object]:
    params = urlencode({"q": query})
    url = f"https://www.bing.com/search?{params}&format=rss"
    response = requests_module.get(url, headers=headers, timeout=15)
    response.raise_for_status()

    text = response.text
    lowered = text.lower()
    if "unusual traffic" in lowered and "captcha" in lowered:
        return {"blocked": True, "results": []}

    soup = soup_module(text, "xml")
    parsed_results: list[dict[str, str]] = []
    for item in soup.find_all("item")[: max_results * 3]:
        link_node = item.find("link")
        title_node = item.find("title")
        desc_node = item.find("description")
        href = (link_node.get_text(strip=True) if link_node else "").strip()
        title = (title_node.get_text(" ", strip=True) if title_node else "").strip()
        snippet = (desc_node.get_text(" ", strip=True) if desc_node else "").strip()
        if not href or not title:
            continue
        parsed_results.append({"title": title, "url": href, "snippet": snippet})
    return {"blocked": False, "results": parsed_results}


def _search_brave_html(*, query: str, headers: dict[str, str], max_results: int, requests_module: object, soup_module: object) -> dict[str, object]:
    params = urlencode({"q": query})
    url = f"https://search.brave.com/search?{params}"
    response = requests_module.get(url, headers=headers, timeout=15)
    response.raise_for_status()

    text = response.text
    lowered = text.lower()
    if "verify you are human" in lowered or "captcha" in lowered:
        return {"blocked": True, "results": []}

    soup = soup_module(text, "html.parser")
    parsed_results: list[dict[str, str]] = []
    for container in soup.select("div.snippet")[: max_results * 3]:
        link = container.select_one("a[href]")
        if not link:
            continue
        href = link.get("href", "")
        if not href.startswith("http://") and not href.startswith("https://"):
            continue
        title = link.get_text(" ", strip=True)
        snippet_node = container.select_one(".snippet-description") or container.select_one("p")
        parsed_results.append(
            {
                "title": title or href,
                "url": href,
                "snippet": snippet_node.get_text(" ", strip=True) if snippet_node else "",
            }
        )
    return {"blocked": False, "results": parsed_results}


def _search_yahoo_html(*, query: str, headers: dict[str, str], max_results: int, requests_module: object, soup_module: object) -> dict[str, object]:
    params = urlencode({"p": query})
    url = f"https://search.yahoo.com/search?{params}"
    response = requests_module.get(url, headers=headers, timeout=15)
    response.raise_for_status()

    text = response.text
    lowered = text.lower()
    if "captcha" in lowered and "robot" in lowered:
        return {"blocked": True, "results": []}

    soup = soup_module(text, "html.parser")
    parsed_results: list[dict[str, str]] = []
    for link in soup.select("a[href]"):
        raw_href = link.get("href", "")
        if "/RU=" not in raw_href:
            continue
        href = _unwrap_yahoo_result_url(raw_href)
        title = link.get_text(" ", strip=True)
        if not href or not title:
            continue
        host = (urlparse(href).hostname or "").lower()
        if host.endswith("yahoo.com") or host.endswith("yahoo.net"):
            continue
        if "search.yahoo.com/search" in href:
            continue
        if not href.startswith("http://") and not href.startswith("https://"):
            continue
        parsed_results.append({"title": title, "url": href, "snippet": ""})
        if len(parsed_results) >= max_results * 5:
            break
    return {"blocked": False, "results": parsed_results}


def _result_priority_score(url: str, title: str) -> tuple[int, int]:
    host = (urlparse(url).hostname or "").lower()
    title_lower = title.lower()
    score = 100

    if host == "github.com" or host.endswith(".github.io"):
        score -= 30
    if "docs" in host or host.startswith("docs."):
        score -= 25
    if any(token in title_lower for token in ("documentation", "readme", "official")):
        score -= 12
    if host.startswith("www.reddit.") or host.startswith("reddit."):
        score += 8
    if host.startswith("www.youtube.") or host.startswith("youtube."):
        score += 10
    return score, len(title)


def _build_no_results_error(provider_attempts: list[dict[str, object]]) -> str:
    blocked_providers = [str(item["provider"]) for item in provider_attempts if bool(item.get("blocked"))]
    error_providers = [
        f"{item['provider']} ({item['error']})"
        for item in provider_attempts
        if item.get("error") and not bool(item.get("blocked"))
    ]
    if blocked_providers and error_providers:
        return (
            "No search results. Some providers blocked by anti-bot ("
            + ", ".join(blocked_providers)
            + "); others failed requests ("
            + "; ".join(error_providers)
            + ")."
        )
    if blocked_providers:
        return "Search providers blocked this request with anti-bot challenges: " + ", ".join(blocked_providers)
    if error_providers:
        return "No search results due to provider request failures: " + "; ".join(error_providers)
    return "No search results found across query variants and providers."


def _unwrap_yahoo_result_url(value: str) -> str:
    if not value:
        return ""
    marker = "/RU="
    if marker not in value:
        return value
    start = value.find(marker)
    if start == -1:
        return value
    start += len(marker)
    end = value.find("/RK=", start)
    encoded = value[start:] if end == -1 else value[start:end]
    return unquote(encoded)


def _is_relevant_result(*, query: str, title: str, snippet: str, url: str) -> bool:
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "what",
        "about",
        "into",
        "your",
        "their",
        "history",
        "latest",
        "news",
        "usa",
        "us",
    }
    query_tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", query.lower())
        if len(token) >= 3 and token not in stopwords
    ]
    if not query_tokens:
        return True
    parsed = urlparse(url)
    host_path = f"{parsed.hostname or ''} {parsed.path or ''}"
    corpus = f"{title} {snippet} {host_path}".lower()
    overlap = sum(1 for token in set(query_tokens) if token in corpus)
    needed = 1 if len(set(query_tokens)) <= 3 else 2
    return overlap >= needed


def _infer_blocked_reason(status_code: int) -> str:
    if status_code == 401:
        return "authentication_required"
    if status_code == 402:
        return "paywall_or_payment_required"
    if status_code == 403:
        return "forbidden_or_bot_block"
    if status_code == 404:
        return "not_found"
    if status_code == 429:
        return "rate_limited"
    if status_code >= 500:
        return "server_error"
    return "http_error"
