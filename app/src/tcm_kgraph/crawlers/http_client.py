"""Async HTTP client with retry logic and rate limiting."""

import asyncio
from typing import Any

import httpx

from tcm_kgraph.core.exceptions import HTTPError
from tcm_kgraph.core.logging import get_logger


logger = get_logger(__name__)


class HttpClient:
    """
    Async HTTP client with built-in retry logic and rate limiting.

    Features:
    - Automatic retries with exponential backoff
    - Rate limiting with configurable delay
    - Connection pooling
    - Custom headers and encoding handling
    """

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    def __init__(
        self,
        timeout: float = 15.0,
        max_retries: int = 3,
        delay: float = 1.0,
        concurrent_limit: int = 5,
        headers: dict[str, str] | None = None,
    ) -> None:
        """
        Initialize HTTP client.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            delay: Delay between requests in seconds
            concurrent_limit: Maximum concurrent requests
            headers: Custom headers to merge with defaults
        """
        self._timeout = timeout
        self._max_retries = max_retries
        self._delay = delay
        self._semaphore = asyncio.Semaphore(concurrent_limit)

        merged_headers = {**self.DEFAULT_HEADERS, **(headers or {})}
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers=merged_headers,
            follow_redirects=True,
            http2=False,
        )
        self._last_request_time: float = 0

    async def _wait_for_rate_limit(self) -> None:
        """Wait to respect rate limiting."""
        if self._delay > 0:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < self._delay:
                await asyncio.sleep(self._delay - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        encoding: str | None = None,
    ) -> str:
        """
        Perform GET request with retries.

        Args:
            url: URL to fetch
            params: Query parameters
            encoding: Response encoding (auto-detected if None)

        Returns:
            Response text content

        Raises:
            HTTPError: If request fails after all retries
        """
        async with self._semaphore:
            last_error: Exception | None = None

            for attempt in range(self._max_retries + 1):
                try:
                    await self._wait_for_rate_limit()

                    response = await self._client.get(url, params=params)
                    response.raise_for_status()

                    # Handle encoding
                    if encoding:
                        response.encoding = encoding
                    elif response.encoding is None:
                        # Try to detect encoding from content
                        response.encoding = "utf-8"

                    logger.debug(f"GET {url} - Status: {response.status_code}")
                    return response.text

                except httpx.HTTPStatusError as e:
                    last_error = e
                    logger.warning(
                        f"HTTP error {e.response.status_code} for {url} (attempt {attempt + 1})"
                    )
                    if e.response.status_code >= 400 and e.response.status_code < 500:
                        # Don't retry client errors
                        break

                except httpx.RequestError as e:
                    last_error = e
                    logger.warning(f"Request error for {url} (attempt {attempt + 1}): {e}")

                # Exponential backoff
                if attempt < self._max_retries:
                    wait_time = (2**attempt) * 0.5
                    await asyncio.sleep(wait_time)

            # All retries failed
            status_code = None
            if isinstance(last_error, httpx.HTTPStatusError):
                status_code = last_error.response.status_code

            raise HTTPError(
                f"Failed to fetch {url} after {self._max_retries + 1} attempts",
                url=url,
                status_code=status_code,
                details={"error": str(last_error)},
            )

    async def get_many(
        self,
        urls: list[str],
        encoding: str | None = None,
    ) -> list[tuple[str, str | Exception]]:
        """
        Fetch multiple URLs concurrently.

        Args:
            urls: List of URLs to fetch
            encoding: Response encoding

        Returns:
            List of (url, content_or_error) tuples
        """
        async def fetch_one(url: str) -> tuple[str, str | Exception]:
            try:
                content = await self.get(url, encoding=encoding)
                return (url, content)
            except Exception as e:
                return (url, e)

        tasks = [fetch_one(url) for url in urls]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
        logger.debug("HTTP client closed")

    async def __aenter__(self) -> "HttpClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
