class InvalidSchema(Exception):
    """Raises when an invalid schema is passed."""
    pass

class CrawlerError(Exception):
    """Base class for all crawler-related errors."""

class RequestError(CrawlerError):
    """Raised when a network request fails."""

class ParseError(CrawlerError):
    """Raised when HTML parsing or extraction fails."""

class FormatterError(CrawlerError):
    """Raised when pre/postformatter fails or invalid type conversion."""

class PaginationError(CrawlerError):
    """Raised when pagination schema is invalid."""