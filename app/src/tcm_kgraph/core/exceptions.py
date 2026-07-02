"""Custom exception hierarchy for TCM Knowledge Graph."""

from typing import Any


class TCMKGraphError(Exception):
    """Base exception for all TCM Knowledge Graph errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class ConfigurationError(TCMKGraphError):
    """Raised when there is a configuration error."""

    pass


class CrawlerError(TCMKGraphError):
    """Base exception for crawler-related errors."""

    pass


class HTTPError(CrawlerError):
    """Raised when HTTP request fails."""

    def __init__(
        self,
        message: str,
        url: str,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        details.update({"url": url, "status_code": status_code})
        super().__init__(message, details)
        self.url = url
        self.status_code = status_code


class ParseError(CrawlerError):
    """Raised when content parsing fails."""

    def __init__(
        self,
        message: str,
        url: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        if url:
            details["url"] = url
        super().__init__(message, details)
        self.url = url


class DatabaseError(TCMKGraphError):
    """Base exception for database-related errors."""

    pass


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""

    pass


class QueryError(DatabaseError):
    """Raised when database query fails."""

    def __init__(
        self,
        message: str,
        query: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        if query:
            details["query"] = query
        super().__init__(message, details)
        self.query = query


class ExtractionError(TCMKGraphError):
    """Base exception for information extraction errors."""

    pass


class EntityExtractionError(ExtractionError):
    """Raised when entity extraction fails."""

    pass


class RelationExtractionError(ExtractionError):
    """Raised when relation extraction fails."""

    pass


class LLMError(TCMKGraphError):
    """Base exception for LLM-related errors."""

    pass


class LLMAPIError(LLMError):
    """Raised when LLM API call fails."""

    def __init__(
        self,
        message: str,
        model: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        if model:
            details["model"] = model
        super().__init__(message, details)
        self.model = model
