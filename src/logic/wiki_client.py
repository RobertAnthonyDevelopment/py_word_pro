import json
from typing import Any
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest


class WikipediaApiError(RuntimeError):
    pass


class WikipediaApiClient:
    API_BASE = "https://en.wikipedia.org/w/api.php"
    SUMMARY_BASE = "https://en.wikipedia.org/api/rest_v1/page/summary"
    USER_AGENT = "PyWordPro/5.0 (Desktop App; support: local-user)"

    def lookup(self, query: str) -> dict[str, str]:
        normalized = self._normalize_query(query)
        if not normalized:
            raise ValueError("Wikipedia query is required.")

        titles = self.search_titles(normalized, limit=6)
        candidates = []
        for value in [normalized] + titles:
            if value and value not in candidates:
                candidates.append(value)

        first_error = None
        for title in candidates:
            try:
                summary = self.fetch_summary(title)
                if summary.get("summary"):
                    return summary
            except WikipediaApiError as exc:
                if first_error is None:
                    first_error = exc

        if titles:
            raise WikipediaApiError("Wikipedia results found, but no summary could be loaded.")
        if first_error is not None:
            raise first_error
        raise WikipediaApiError("No Wikipedia results found.")

    def search_titles(self, query: str, limit: int = 6) -> list[str]:
        normalized = self._normalize_query(query)
        if not normalized:
            return []
        try:
            cap = max(1, min(25, int(limit)))
        except (TypeError, ValueError):
            cap = 6

        params = {
            "action": "query",
            "list": "search",
            "srsearch": normalized,
            "srlimit": cap,
            "utf8": 1,
            "format": "json",
            "formatversion": 2,
        }
        payload = self._request_json(self.API_BASE, params=params)
        query_data = payload.get("query")
        if not isinstance(query_data, dict):
            return []
        results = query_data.get("search")
        if not isinstance(results, list):
            return []
        titles = []
        seen = set()
        for item in results:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            titles.append(title)
        return titles

    def fetch_summary(self, title: str) -> dict[str, str]:
        normalized_title = self._normalize_query(title).replace(" ", "_")
        if not normalized_title:
            raise ValueError("Wikipedia title is required.")
        encoded = urlparse.quote(normalized_title, safe="")
        url = f"{self.SUMMARY_BASE}/{encoded}"
        payload = self._request_json(url)

        page_title = str(payload.get("title") or "").strip() or normalized_title.replace("_", " ")
        summary = str(payload.get("extract") or "").strip()
        description = str(payload.get("description") or "").strip()

        page_url = ""
        content_urls = payload.get("content_urls")
        if isinstance(content_urls, dict):
            desktop = content_urls.get("desktop")
            if isinstance(desktop, dict):
                page_url = str(desktop.get("page") or "").strip()
            if not page_url:
                mobile = content_urls.get("mobile")
                if isinstance(mobile, dict):
                    page_url = str(mobile.get("page") or "").strip()

        if not page_url:
            page_url = f"https://en.wikipedia.org/wiki/{urlparse.quote(page_title.replace(' ', '_'), safe='')}"

        if not summary:
            summary = str(payload.get("extract_html") or "").strip()
            summary = self._strip_html(summary)

        if not summary:
            raise WikipediaApiError("Wikipedia page did not contain a usable summary.")

        return {
            "title": page_title,
            "summary": summary,
            "description": description,
            "url": page_url,
        }

    def _request_json(self, url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        full_url = url
        if params:
            full_url = f"{url}?{urlparse.urlencode(params)}"
        req = urlrequest.Request(
            url=full_url,
            headers={
                "User-Agent": self.USER_AGENT,
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urlrequest.urlopen(req, timeout=15) as response:
                raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            if isinstance(payload, dict):
                return payload
            return {}
        except urlerror.HTTPError as exc:
            message = f"Wikipedia API error ({exc.code})"
            try:
                raw = exc.read().decode("utf-8")
                parsed = json.loads(raw) if raw else {}
                if isinstance(parsed, dict):
                    detail = str(parsed.get("detail") or parsed.get("title") or "").strip()
                    if detail:
                        message = f"{message}: {detail}"
            except Exception:
                pass
            raise WikipediaApiError(message) from exc
        except urlerror.URLError as exc:
            raise WikipediaApiError(f"Wikipedia network error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise WikipediaApiError("Wikipedia response parsing failed.") from exc

    def _normalize_query(self, raw: str) -> str:
        text = str(raw or "").strip()
        if not text:
            return ""
        return " ".join(text.split())[:120]

    def _strip_html(self, text: str) -> str:
        value = str(text or "")
        chunks = []
        in_tag = False
        for ch in value:
            if ch == "<":
                in_tag = True
                continue
            if ch == ">":
                in_tag = False
                continue
            if not in_tag:
                chunks.append(ch)
        return "".join(chunks).strip()
