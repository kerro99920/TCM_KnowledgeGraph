"""Medicine crawler for TCM drug information."""

import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from tcm_kgraph.crawlers.base import BaseCrawler
from tcm_kgraph.crawlers.http_client import HttpClient
from tcm_kgraph.crawlers.extractors.base import BaseExtractor
from tcm_kgraph.crawlers.extractors.full_extractor import FullTextExtractor
from tcm_kgraph.core.logging import get_logger


logger = get_logger(__name__)


class MedicineCrawler(BaseCrawler):
    """
    Crawler for Traditional Chinese Medicine drug information.

    Supports crawling medicine lists and detail pages from common
    TCM information websites.
    """

    # Default target site configuration
    DEFAULT_BASE_URL = "https://www.zysj.com.cn"
    LIST_URL_TEMPLATE = "/zhongyaocai/index__{page}.html"
    ENCODING = "utf-8"

    def __init__(
        self,
        client: HttpClient,
        output_dir: Path | None = None,
        base_url: str | None = None,
    ) -> None:
        """
        Initialize medicine crawler.

        Args:
            client: HTTP client instance
            output_dir: Directory for saving crawled data
            base_url: Custom base URL (uses default if not provided)
        """
        super().__init__(client, output_dir)
        self._base_url = base_url or self.DEFAULT_BASE_URL
        self._extractor = FullTextExtractor(
            content_selector=".zhongyaocai-content, .content, #content, article",
        )

    @property
    def name(self) -> str:
        return "MedicineCrawler"

    @property
    def base_url(self) -> str:
        return self._base_url

    async def crawl_list(
        self,
        page: int = 1,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Crawl medicine list page.

        Args:
            page: Page number
            limit: Maximum items to return

        Returns:
            List of medicine items with URLs and names
        """
        url = urljoin(self.base_url, self.LIST_URL_TEMPLATE.format(page=page))
        logger.debug(f"Crawling medicine list: {url}")

        html = await self.client.get(url, encoding=self.ENCODING)
        items = self._parse_list(html)

        if limit:
            items = items[:limit]

        logger.info(f"Found {len(items)} medicines on page {page}")
        return items

    def _parse_list(self, html: str) -> list[dict[str, Any]]:
        """Parse medicine list page HTML."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        items: list[dict[str, Any]] = []

        # Try common list patterns
        link_selectors = [
            ".medicine-list a",
            ".drug-list a",
            ".list-content a",
            "ul.list li a",
            ".zhongyao-list a",
            "table.list td a",
        ]

        links = []
        for selector in link_selectors:
            links = soup.select(selector)
            if links:
                break

        # Fallback: find all links with medicine-like URLs
        if not links:
            links = soup.find_all("a", href=re.compile(r"zhongyao|medicine|drug", re.I))

        for link in links:
            href = link.get("href", "")
            if not href or href.startswith("#"):
                continue

            name = BaseExtractor.extract_text(link)
            if not name:
                continue

            full_url = urljoin(self.base_url, href)
            items.append({
                "name": name,
                "url": full_url,
            })

        return items

    async def crawl_detail(self, url: str) -> dict[str, Any]:
        """
        Crawl medicine detail page.

        Args:
            url: Detail page URL

        Returns:
            Extracted medicine data
        """
        logger.debug(f"Crawling medicine detail: {url}")
        html = await self.client.get(url, encoding=self.ENCODING)
        return await self.parse_detail(html, url)

    async def parse_detail(self, html: str, url: str) -> dict[str, Any]:
        """
        Parse medicine detail page.

        Args:
            html: Page HTML content
            url: Source URL

        Returns:
            Extracted medicine data
        """
        # Use full text extractor for raw content
        data = self._extractor.extract(html, url)

        # Try to extract structured fields
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # Extract name from title or h1
        name = self._extract_name(soup) or data.get("title", "")
        data["name"] = name

        # Extract common fields using patterns
        text = data.get("raw_text", "")

        # 拼音名
        pinyin_match = re.search(r"拼音[名：:]\s*([A-Za-z\s]+)", text)
        if pinyin_match:
            data["pinyin"] = pinyin_match.group(1).strip()

        # 别名
        alias_match = re.search(r"别名[：:]\s*([^。\n]+)", text)
        if alias_match:
            aliases = [a.strip() for a in alias_match.group(1).split("、") if a.strip()]
            data["aliases"] = aliases

        # 来源
        source_match = re.search(r"(?:来源|基原)[：:]\s*([^。\n]+)", text)
        if source_match:
            data["source"] = source_match.group(1).strip()

        # 性味
        nature_match = re.search(r"性味[：:]\s*([^。\n]+)", text)
        if nature_match:
            nature_text = nature_match.group(1).strip()
            data["nature_flavor"] = nature_text

        # 归经
        meridian_match = re.search(r"归经[：:]\s*([^。\n]+)", text)
        if meridian_match:
            meridians = [m.strip() for m in meridian_match.group(1).split("、") if m.strip()]
            data["meridians"] = meridians

        # 功效
        function_match = re.search(r"功效[：:]\s*([^。\n]+)", text)
        if function_match:
            functions = [f.strip() for f in function_match.group(1).split("、") if f.strip()]
            data["functions"] = functions

        # 主治
        indication_match = re.search(r"主治[：:]\s*([^。\n]+)", text)
        if indication_match:
            indications = [i.strip() for i in indication_match.group(1).split("、") if i.strip()]
            data["indications"] = indications

        # 用法用量
        usage_match = re.search(r"用法[用量：:]*\s*([^。\n]+)", text)
        if usage_match:
            data["usage"] = usage_match.group(1).strip()

        # 禁忌
        contra_match = re.search(r"禁忌[：:]\s*([^。\n]+)", text)
        if contra_match:
            contras = [c.strip() for c in contra_match.group(1).split("、") if c.strip()]
            data["contraindications"] = contras

        return data

    def _extract_name(self, soup: Any) -> str | None:
        """Extract medicine name from page."""
        # Try common name locations
        selectors = [
            "h1.title",
            ".medicine-name",
            ".drug-name",
            "h1",
            ".detail-title",
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                name = BaseExtractor.extract_text(element)
                # Clean up common suffixes
                name = re.sub(r"\s*[-–—]\s*.*$", "", name)
                if name and len(name) < 50:
                    return name

        return None
