"""Field-based extractor for structured data."""

import re
from typing import Any

from tcm_kgraph.crawlers.extractors.base import BaseExtractor


class FieldConfig:
    """Configuration for a single field extraction."""

    def __init__(
        self,
        name: str,
        selector: str | None = None,
        pattern: str | None = None,
        label: str | None = None,
        attribute: str | None = None,
        is_list: bool = False,
        post_process: str | None = None,
    ) -> None:
        """
        Configure field extraction.

        Args:
            name: Output field name
            selector: CSS selector to find element
            pattern: Regex pattern to extract value
            label: Label text to find (for label:value pairs)
            attribute: Element attribute to extract (default: text)
            is_list: Whether to extract multiple values
            post_process: Post-processing method ('strip', 'split_comma', etc.)
        """
        self.name = name
        self.selector = selector
        self.pattern = pattern
        self.label = label
        self.attribute = attribute
        self.is_list = is_list
        self.post_process = post_process


class FieldExtractor(BaseExtractor):
    """
    Extractor for structured field-based data.

    Extracts specific fields from HTML using CSS selectors,
    regex patterns, or label matching.
    """

    def __init__(
        self,
        fields: list[FieldConfig],
        content_selector: str | None = None,
        parser: str = "lxml",
    ) -> None:
        """
        Initialize field extractor.

        Args:
            fields: List of field configurations
            content_selector: CSS selector for main content area
            parser: BeautifulSoup parser
        """
        super().__init__(parser)
        self.fields = fields
        self.content_selector = content_selector

    def extract(self, html: str, url: str | None = None) -> dict[str, Any]:
        """
        Extract configured fields from HTML.

        Args:
            html: HTML content
            url: Source URL

        Returns:
            Dictionary with extracted field values
        """
        soup = self.parse(html)

        # Get content area
        if self.content_selector:
            content = soup.select_one(self.content_selector)
            if content is None:
                content = soup
        else:
            content = soup

        result: dict[str, Any] = {"source_url": url}

        for field in self.fields:
            value = self._extract_field(content, field, html)
            if value is not None:
                result[field.name] = value

        return result

    def _extract_field(
        self,
        content: Any,
        field: FieldConfig,
        html: str,
    ) -> Any:
        """Extract a single field value."""
        value: Any = None

        # Try CSS selector
        if field.selector:
            if field.is_list:
                elements = content.select(field.selector)
                values = []
                for elem in elements:
                    v = self._get_element_value(elem, field.attribute)
                    if v:
                        values.append(v)
                value = values if values else None
            else:
                element = content.select_one(field.selector)
                if element:
                    value = self._get_element_value(element, field.attribute)

        # Try label matching
        elif field.label:
            value = self._extract_by_label(content, field.label, field.is_list)

        # Try regex pattern
        elif field.pattern:
            matches = re.findall(field.pattern, html, re.IGNORECASE | re.DOTALL)
            if matches:
                if field.is_list:
                    value = [self.clean_text(m) for m in matches]
                else:
                    value = self.clean_text(matches[0])

        # Post-process
        if value is not None and field.post_process:
            value = self._post_process(value, field.post_process)

        return value

    def _get_element_value(self, element: Any, attribute: str | None) -> str:
        """Get value from element (text or attribute)."""
        if attribute:
            return element.get(attribute, "")
        return self.extract_text(element)

    def _extract_by_label(
        self,
        content: Any,
        label: str,
        is_list: bool,
    ) -> str | list[str] | None:
        """Extract value by finding label text."""
        # Common patterns for label:value pairs
        patterns = [
            # <dt>Label</dt><dd>Value</dd>
            ("dt", "dd"),
            # <th>Label</th><td>Value</td>
            ("th", "td"),
            # <span class="label">Label</span><span class="value">Value</span>
            (".label", ".value"),
        ]

        for label_sel, value_sel in patterns:
            for elem in content.select(label_sel):
                if label.lower() in self.extract_text(elem).lower():
                    # Find adjacent value element
                    value_elem = elem.find_next_sibling()
                    if value_elem:
                        text = self.extract_text(value_elem)
                        if is_list:
                            return [t.strip() for t in text.split("、") if t.strip()]
                        return text

        # Try finding text followed by colon
        text = content.get_text()
        pattern = rf"{re.escape(label)}[：:]\s*([^\n]+)"
        match = re.search(pattern, text)
        if match:
            result = self.clean_text(match.group(1))
            if is_list:
                return [t.strip() for t in result.split("、") if t.strip()]
            return result

        return None

    def _post_process(self, value: Any, method: str) -> Any:
        """Apply post-processing to extracted value."""
        if method == "strip" and isinstance(value, str):
            return value.strip()

        if method == "split_comma":
            if isinstance(value, str):
                return [v.strip() for v in value.split(",") if v.strip()]
            return value

        if method == "split_chinese_comma":
            if isinstance(value, str):
                return [v.strip() for v in value.split("、") if v.strip()]
            return value

        if method == "lowercase" and isinstance(value, str):
            return value.lower()

        return value
