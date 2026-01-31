"""LLM-based information extraction module."""

from tcm_kgraph.extraction.extractor import EntityExtractor
from tcm_kgraph.extraction.prompts import ExtractionPrompts

__all__ = ["EntityExtractor", "ExtractionPrompts"]
