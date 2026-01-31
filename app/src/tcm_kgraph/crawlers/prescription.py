"""Prescription crawler for TCM formula information."""

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


class PrescriptionCrawler(BaseCrawler):
    """
    Crawler for Traditional Chinese Medicine prescription/formula information.

    Supports crawling prescription lists and detail pages from common
    TCM information websites.
    """

    # Default target site configuration
    DEFAULT_BASE_URL = "https://www.zysj.com.cn"
    LIST_URL_TEMPLATE = "/fangji/index__{page}.html"
    ENCODING = "utf-8"

    def __init__(
        self,
        client: HttpClient,
        output_dir: Path | None = None,
        base_url: str | None = None,
    ) -> None:
        """
        Initialize prescription crawler.

        Args:
            client: HTTP client instance
            output_dir: Directory for saving crawled data
            base_url: Custom base URL (uses default if not provided)
        """
        super().__init__(client, output_dir)
        self._base_url = base_url or self.DEFAULT_BASE_URL
        self._extractor = FullTextExtractor(
            content_selector=".fangji-content, .content, #content, article",
        )

    @property
    def name(self) -> str:
        return "PrescriptionCrawler"

    @property
    def base_url(self) -> str:
        return self._base_url

    async def crawl_list(
        self,
        page: int = 1,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Crawl prescription list page.

        Args:
            page: Page number
            limit: Maximum items to return

        Returns:
            List of prescription items with URLs and names
        """
        url = urljoin(self.base_url, self.LIST_URL_TEMPLATE.format(page=page))
        logger.debug(f"Crawling prescription list: {url}")

        html = await self.client.get(url, encoding=self.ENCODING)
        items = self._parse_list(html)

        if limit:
            items = items[:limit]

        logger.info(f"Found {len(items)} prescriptions on page {page}")
        return items

    def _parse_list(self, html: str) -> list[dict[str, Any]]:
        """Parse prescription list page HTML."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        items: list[dict[str, Any]] = []

        # Try common list patterns
        link_selectors = [
            ".prescription-list a",
            ".fangji-list a",
            ".formula-list a",
            ".list-content a",
            "ul.list li a",
            "table.list td a",
        ]

        links = []
        for selector in link_selectors:
            links = soup.select(selector)
            if links:
                break

        # Fallback: find all links with prescription-like URLs
        if not links:
            links = soup.find_all("a", href=re.compile(r"fangji|prescription|formula", re.I))

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
        Crawl prescription detail page.

        Args:
            url: Detail page URL

        Returns:
            Extracted prescription data
        """
        logger.debug(f"Crawling prescription detail: {url}")
        html = await self.client.get(url, encoding=self.ENCODING)
        return await self.parse_detail(html, url)

    async def parse_detail(self, html: str, url: str) -> dict[str, Any]:
        """
        Parse prescription detail page.

        Args:
            html: Page HTML content
            url: Source URL

        Returns:
            Extracted prescription data
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

        # 出处/来源
        source_match = re.search(r"(?:出处|来源|出自)[：:]\s*([^。\n]+)", text)
        if source_match:
            data["source_book"] = source_match.group(1).strip()

        # 组成
        composition_match = re.search(r"(?:组成|药物组成)[：:]\s*([^。]+)", text)
        if composition_match:
            composition_text = composition_match.group(1).strip()
            data["composition_text"] = composition_text
            data["composition"] = self._parse_composition(composition_text)

        # 功效/功用
        function_match = re.search(r"(?:功效|功用)[：:]\s*([^。\n]+)", text)
        if function_match:
            functions = [f.strip() for f in function_match.group(1).split("、") if f.strip()]
            data["functions"] = functions

        # 主治
        indication_match = re.search(r"主治[：:]\s*([^。\n]+)", text)
        if indication_match:
            indications = [i.strip() for i in indication_match.group(1).split("、") if i.strip()]
            data["indications"] = indications

        # 用法/用法用量
        usage_match = re.search(r"用法[用量：:]*\s*([^。\n]+)", text)
        if usage_match:
            data["dosage"] = usage_match.group(1).strip()

        # 制法
        prep_match = re.search(r"制法[：:]\s*([^。\n]+)", text)
        if prep_match:
            data["preparation"] = prep_match.group(1).strip()

        # 方解
        explain_match = re.search(r"方解[：:]\s*([^。]+。)", text)
        if explain_match:
            data["formula_explanation"] = explain_match.group(1).strip()

        # 禁忌
        contra_match = re.search(r"禁忌[：:]\s*([^。\n]+)", text)
        if contra_match:
            contras = [c.strip() for c in contra_match.group(1).split("、") if c.strip()]
            data["contraindications"] = contras

        # 加减
        modify_match = re.search(r"(?:加减|随证加减)[：:]\s*([^。]+)", text)
        if modify_match:
            modifications = [m.strip() for m in modify_match.group(1).split("；") if m.strip()]
            data["modifications"] = modifications

        return data

    def _extract_name(self, soup: Any) -> str | None:
        """Extract prescription name from page."""
        # Try common name locations
        selectors = [
            "h1.title",
            ".prescription-name",
            ".fangji-name",
            ".formula-name",
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

    def _parse_composition(self, text: str) -> list[dict[str, str]]:
        """
        Parse composition text to extract medicines and dosages.

        Args:
            text: Composition text (e.g., "人参10g、白术15g、甘草6g")

        Returns:
            List of dicts with 'medicine_name' and 'dosage'
        """
        composition: list[dict[str, str]] = []

        # Common patterns for composition
        # Pattern: 药名+剂量 (e.g., "人参10g" or "人参 10克")
        pattern = r"([^\d\s,，、]+?)\s*(\d+(?:\.\d+)?(?:g|克|两|钱|分|升|ml)?)"
        matches = re.findall(pattern, text)

        for name, dosage in matches:
            name = name.strip()
            if name and len(name) < 20:
                composition.append({
                    "medicine_name": name,
                    "dosage": dosage.strip(),
                })

        # If no matches with dosage, try splitting by delimiters
        if not composition:
            parts = re.split(r"[,，、；;]", text)
            for part in parts:
                part = part.strip()
                if part and len(part) < 30:
                    # Try to separate name and dosage
                    match = re.match(r"(.+?)\s*(\d+.*)$", part)
                    if match:
                        composition.append({
                            "medicine_name": match.group(1).strip(),
                            "dosage": match.group(2).strip(),
                        })
                    else:
                        composition.append({
                            "medicine_name": part,
                            "dosage": "",
                        })

        return composition
