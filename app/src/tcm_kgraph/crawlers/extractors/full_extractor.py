"""Full text extractor for complete page content."""

from typing import Any

from tcm_kgraph.crawlers.extractors.base import BaseExtractor


class FullTextExtractor(BaseExtractor):
    """
    Extractor for capturing full text content from pages.

    Useful for LLM-based information extraction where the complete
    text content is needed for processing.
    """

    def __init__(
        self,
        content_selector: str | None = None,
        exclude_selectors: list[str] | None = None,
        parser: str = "lxml",
    ) -> None:
        """
        Initialize full text extractor.

        Args:
            content_selector: CSS selector for main content area
            exclude_selectors: CSS selectors for elements to exclude
            parser: BeautifulSoup parser
        """
        super().__init__(parser)
        self.content_selector = content_selector
        self.exclude_selectors = exclude_selectors or [
            "script",
            "style",
            "nav",
            "header",
            "footer",
            ".sidebar",
            ".advertisement",
            ".comments",
        ]

    def extract(self, html: str, url: str | None = None) -> dict[str, Any]:
        """
        Extract full text content from HTML.

        Args:
            html: HTML content
            url: Source URL

        Returns:
            Dictionary with 'raw_text', 'title', and 'source_url'
        """
        soup = self.parse(html)

        # Remove unwanted elements
        for selector in self.exclude_selectors:
            for element in soup.select(selector):
                element.decompose()

        # Get content area
        if self.content_selector:
            content = soup.select_one(self.content_selector)
        else:
            content = soup.body or soup

        # Extract title
        title = ""
        title_element = soup.find("title")
        if title_element:
            title = self.extract_text(title_element)
        else:
            h1 = soup.find("h1")
            if h1:
                title = self.extract_text(h1)

        # Extract full text
        raw_text = ""
        if content:
            # Get text with some structure preserved
            lines = []
            for element in content.find_all(["p", "div", "li", "h1", "h2", "h3", "h4", "td"]):
                text = self.extract_text(element)
                if text and len(text) > 1:
                    lines.append(text)
            raw_text = "\n".join(lines)

        return {
            "title": title,
            "raw_text": raw_text,
            "source_url": url,
        }

    def extract_sections(self, html: str) -> dict[str, str]:
        """
        Extract text organized by sections (headings).

        Args:
            html: HTML content

        Returns:
            Dictionary mapping section headers to content
        """
        soup = self.parse(html)

        # Remove unwanted elements
        for selector in self.exclude_selectors:
            for element in soup.select(selector):
                element.decompose()

        sections: dict[str, str] = {}
        current_section = "introduction"
        current_content: list[str] = []

        content = soup.body or soup
        for element in content.find_all(["h1", "h2", "h3", "h4", "p", "div", "li"]):
            if element.name in ("h1", "h2", "h3", "h4"):
                # Save previous section
                if current_content:
                    sections[current_section] = "\n".join(current_content)
                # Start new section
                current_section = self.extract_text(element)
                current_content = []
            else:
                text = self.extract_text(element)
                if text and len(text) > 1:
                    current_content.append(text)

        # Save last section
        if current_content:
            sections[current_section] = "\n".join(current_content)

        return sections
