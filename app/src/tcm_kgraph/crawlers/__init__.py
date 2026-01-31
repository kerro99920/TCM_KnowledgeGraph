"""Web crawlers for TCM data collection."""

from tcm_kgraph.crawlers.base import BaseCrawler
from tcm_kgraph.crawlers.http_client import HttpClient
from tcm_kgraph.crawlers.medicine import MedicineCrawler
from tcm_kgraph.crawlers.prescription import PrescriptionCrawler

__all__ = [
    "BaseCrawler",
    "HttpClient",
    "MedicineCrawler",
    "PrescriptionCrawler",
]
