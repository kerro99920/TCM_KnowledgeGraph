"""Base crawler class for web scraping."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from tcm_kgraph.crawlers.http_client import HttpClient
from tcm_kgraph.core.logging import get_logger


logger = get_logger(__name__)


class BaseCrawler(ABC):
    """
    Abstract base class for web crawlers.

    Provides common functionality for crawling TCM websites,
    including list page parsing, detail fetching, and data export.
    """

    def __init__(
        self,
        client: HttpClient,
        output_dir: Path | None = None,
    ) -> None:
        """
        Initialize crawler.

        Args:
            client: HTTP client instance
            output_dir: Directory for saving crawled data
        """
        self.client = client
        self.output_dir = output_dir

    @property
    @abstractmethod
    def name(self) -> str:
        """Crawler name for logging and identification."""
        ...

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Base URL for the target website."""
        ...

    @abstractmethod
    async def crawl_list(
        self,
        page: int = 1,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Crawl list page to extract item URLs and basic info.

        Args:
            page: Page number to crawl
            limit: Maximum items to return

        Returns:
            List of dicts with 'url', 'name', and other basic info
        """
        ...

    @abstractmethod
    async def crawl_detail(self, url: str) -> dict[str, Any]:
        """
        Crawl detail page to extract full information.

        Args:
            url: Detail page URL

        Returns:
            Dictionary with extracted data
        """
        ...

    @abstractmethod
    async def parse_detail(self, html: str, url: str) -> dict[str, Any]:
        """
        Parse detail page HTML to extract structured data.

        Args:
            html: Page HTML content
            url: Source URL

        Returns:
            Dictionary with extracted data
        """
        ...

    async def crawl_all(
        self,
        max_pages: int = 1,
        items_per_page: int | None = None,
        save_raw: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Crawl all items from list and detail pages.

        Args:
            max_pages: Maximum pages to crawl
            items_per_page: Items limit per page
            save_raw: Whether to save raw text files

        Returns:
            List of all crawled items
        """
        all_items: list[dict[str, Any]] = []

        for page in range(1, max_pages + 1):
            logger.info(f"{self.name}: Crawling page {page}/{max_pages}")

            try:
                items = await self.crawl_list(page=page, limit=items_per_page)
                if not items:
                    logger.info(f"{self.name}: No more items on page {page}")
                    break

                for item in items:
                    url = item.get("url")
                    if not url:
                        continue

                    try:
                        detail = await self.crawl_detail(url)
                        detail.update(item)  # Merge list info with detail
                        all_items.append(detail)

                        if save_raw and self.output_dir:
                            await self._save_raw(detail)

                        logger.debug(f"{self.name}: Crawled {detail.get('name', url)}")

                    except Exception as e:
                        logger.error(f"{self.name}: Failed to crawl detail {url}: {e}")

            except Exception as e:
                logger.error(f"{self.name}: Failed to crawl page {page}: {e}")

        logger.info(f"{self.name}: Completed crawling {len(all_items)} items")
        return all_items

    async def _save_raw(self, item: dict[str, Any]) -> None:
        """Save raw item data to file."""
        if not self.output_dir:
            return

        self.output_dir.mkdir(parents=True, exist_ok=True)

        name = item.get("name", "unknown")
        # Sanitize filename
        safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in name)
        file_path = self.output_dir / f"{safe_name}.txt"

        content = item.get("raw_text", "")
        if not content:
            # Generate content from item data
            content = self._format_item(item)

        file_path.write_text(content, encoding="utf-8")
        logger.debug(f"Saved raw data to {file_path}")

    def _format_item(self, item: dict[str, Any]) -> str:
        """Format item data as text content."""
        lines = []
        for key, value in item.items():
            if key in ("raw_text", "url", "source_url"):
                continue
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            lines.append(f"{key}: {value}")
        return "\n".join(lines)
