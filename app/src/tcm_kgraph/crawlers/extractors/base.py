"""Base extractor class for HTML content parsing."""

from abc import ABC, abstractmethod
from typing import Any

from bs4 import BeautifulSoup


class BaseExtractor(ABC):
    """
    Abstract base class for content extractors.

    Extractors are responsible for parsing HTML content and
    extracting structured data from web pages.
    """

    def __init__(self, parser: str = "lxml") -> None:
        """
        Initialize extractor.

        Args:
            parser: BeautifulSoup parser to use (lxml, html.parser, etc.)
        """
        self.parser = parser

    def parse(self, html: str) -> BeautifulSoup:
        """
        Parse HTML string to BeautifulSoup object.

        Args:
            html: HTML content string

        Returns:
            BeautifulSoup object
        """
        return BeautifulSoup(html, self.parser)

    @abstractmethod
    def extract(self, html: str, url: str | None = None) -> dict[str, Any]:
        """
        Extract data from HTML content.

        Args:
            html: HTML content string
            url: Source URL for context

        Returns:
            Dictionary with extracted data
        """
        ...

    @staticmethod
    def clean_text(text: str | None) -> str:
        """
        Clean and normalize text content.

        Args:
            text: Text to clean

        Returns:
            Cleaned text
        """
        if not text:
            return ""
        # Remove extra whitespace
        return " ".join(text.split())

    @staticmethod
    def extract_text(element: Any) -> str:
        """
        Extract text from BeautifulSoup element.

        Args:
            element: BeautifulSoup element

        Returns:
            Extracted text or empty string
        """
        if element is None:
            return ""
        return BaseExtractor.clean_text(element.get_text())
