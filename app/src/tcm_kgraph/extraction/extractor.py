"""LLM-based entity and relation extractor."""

from typing import Any

from tcm_kgraph.core.exceptions import EntityExtractionError, RelationExtractionError
from tcm_kgraph.core.logging import get_logger
from tcm_kgraph.extraction.prompts import ExtractionPrompts
from tcm_kgraph.llm.client import LLMClient
from tcm_kgraph.models.entities import Medicine, Prescription


logger = get_logger(__name__)


class EntityExtractor:
    """
    LLM-based extractor for TCM entities and relations.

    Uses prompt engineering to extract structured information
    from unstructured TCM text content.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        """
        Initialize extractor.

        Args:
            llm_client: LLM client for text generation
        """
        self._llm = llm_client
        self._prompts = ExtractionPrompts()

    async def extract_medicine(self, text: str) -> dict[str, Any]:
        """
        Extract medicine entity from text.

        Args:
            text: Raw text about a medicine

        Returns:
            Extracted medicine data as dictionary

        Raises:
            EntityExtractionError: If extraction fails
        """
        try:
            prompt = self._prompts.MEDICINE_EXTRACTION.format(text=text)
            result = await self._llm.extract_json(
                prompt=prompt,
                system_prompt=self._prompts.SYSTEM_PROMPT,
            )
            logger.debug(f"Extracted medicine: {result.get('name', 'unknown')}")
            return result
        except Exception as e:
            raise EntityExtractionError(
                f"Failed to extract medicine from text: {e}",
                details={"text_length": len(text)},
            ) from e

    async def extract_prescription(self, text: str) -> dict[str, Any]:
        """
        Extract prescription entity from text.

        Args:
            text: Raw text about a prescription

        Returns:
            Extracted prescription data as dictionary

        Raises:
            EntityExtractionError: If extraction fails
        """
        try:
            prompt = self._prompts.PRESCRIPTION_EXTRACTION.format(text=text)
            result = await self._llm.extract_json(
                prompt=prompt,
                system_prompt=self._prompts.SYSTEM_PROMPT,
            )
            logger.debug(f"Extracted prescription: {result.get('name', 'unknown')}")
            return result
        except Exception as e:
            raise EntityExtractionError(
                f"Failed to extract prescription from text: {e}",
                details={"text_length": len(text)},
            ) from e

    async def extract_relations(self, text: str) -> list[dict[str, Any]]:
        """
        Extract relations from text.

        Args:
            text: Raw text containing entity relations

        Returns:
            List of extracted relations

        Raises:
            RelationExtractionError: If extraction fails
        """
        try:
            prompt = self._prompts.RELATION_EXTRACTION.format(text=text)
            result = await self._llm.extract_json(
                prompt=prompt,
                system_prompt=self._prompts.SYSTEM_PROMPT,
            )
            relations = result.get("relations", [])
            logger.debug(f"Extracted {len(relations)} relations")
            return relations
        except Exception as e:
            raise RelationExtractionError(
                f"Failed to extract relations from text: {e}",
                details={"text_length": len(text)},
            ) from e

    async def link_entities(self, terms: list[str]) -> list[dict[str, Any]]:
        """
        Link entity mentions to standard entities.

        Args:
            terms: List of term strings to normalize

        Returns:
            List of linked entity data

        Raises:
            EntityExtractionError: If linking fails
        """
        try:
            terms_text = "\n".join(f"- {term}" for term in terms)
            prompt = self._prompts.ENTITY_LINKING.format(terms=terms_text)
            result = await self._llm.extract_json(
                prompt=prompt,
                system_prompt=self._prompts.SYSTEM_PROMPT,
            )
            entities = result.get("entities", [])
            logger.debug(f"Linked {len(entities)} entities")
            return entities
        except Exception as e:
            raise EntityExtractionError(
                f"Failed to link entities: {e}",
                details={"num_terms": len(terms)},
            ) from e

    async def text_to_medicine(self, text: str) -> Medicine:
        """
        Extract and create Medicine entity from text.

        Args:
            text: Raw text about a medicine

        Returns:
            Medicine entity object
        """
        data = await self.extract_medicine(text)

        # Map extracted fields to Medicine model
        properties_data = {
            "nature": data.get("nature"),
            "flavor": data.get("flavors", []),
            "meridians": data.get("meridians", []),
        }

        return Medicine(
            name=data.get("name", ""),
            aliases=data.get("aliases", []),
            pinyin=data.get("pinyin"),
            properties=properties_data,
            functions=data.get("functions", []),
            indications=data.get("indications", []),
            usage=data.get("usage"),
            contraindications=data.get("contraindications", []),
            source=data.get("source"),
            raw_text=text,
        )

    async def text_to_prescription(self, text: str) -> Prescription:
        """
        Extract and create Prescription entity from text.

        Args:
            text: Raw text about a prescription

        Returns:
            Prescription entity object
        """
        data = await self.extract_prescription(text)

        return Prescription(
            name=data.get("name", ""),
            aliases=data.get("aliases", []),
            pinyin=data.get("pinyin"),
            source_book=data.get("source_book"),
            composition=data.get("composition", []),
            functions=data.get("functions", []),
            indications=data.get("indications", []),
            dosage=data.get("dosage"),
            contraindications=data.get("contraindications", []),
            formula_explanation=data.get("formula_explanation"),
            raw_text=text,
        )

    async def question_to_cypher(self, question: str) -> tuple[str, str]:
        """
        Convert natural language question to Cypher query.

        Args:
            question: Natural language question

        Returns:
            Tuple of (cypher_query, explanation)

        Raises:
            ExtractionError: If conversion fails
        """
        try:
            prompt = self._prompts.QUESTION_TO_CYPHER.format(question=question)
            result = await self._llm.extract_json(
                prompt=prompt,
                system_prompt=self._prompts.SYSTEM_PROMPT,
            )
            cypher = result.get("cypher", "")
            explanation = result.get("explanation", "")
            logger.debug(f"Generated Cypher: {cypher}")
            return cypher, explanation
        except Exception as e:
            raise EntityExtractionError(
                f"Failed to convert question to Cypher: {e}",
                details={"question": question},
            ) from e
