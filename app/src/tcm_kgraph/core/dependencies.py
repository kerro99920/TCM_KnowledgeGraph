"""Dependency injection container for application-wide resources."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tcm_kgraph.core.config import Settings, get_settings
from tcm_kgraph.core.logging import get_logger

if TYPE_CHECKING:
    from tcm_kgraph.database.neo4j_client import Neo4jClient
    from tcm_kgraph.llm.client import LLMClient
    from tcm_kgraph.llm.embeddings import EmbeddingModel

logger = get_logger(__name__)


@dataclass
class Container:
    """
    Dependency injection container holding application-wide resources.

    This container manages the lifecycle of shared resources like database
    connections, LLM clients, and embedding models.
    """

    settings: Settings = field(default_factory=get_settings)
    _neo4j_client: "Neo4jClient | None" = field(default=None, repr=False)
    _llm_client: "LLMClient | None" = field(default=None, repr=False)
    _embedding_model: "EmbeddingModel | None" = field(default=None, repr=False)

    @property
    def neo4j_client(self) -> "Neo4jClient":
        """Get or create Neo4j client."""
        if self._neo4j_client is None:
            from tcm_kgraph.database.neo4j_client import Neo4jClient

            self._neo4j_client = Neo4jClient(
                uri=self.settings.neo4j_uri,
                user=self.settings.neo4j_user,
                password=self.settings.neo4j_password.get_secret_value(),
                database=self.settings.neo4j_database,
            )
            logger.info("Neo4j client initialized")
        return self._neo4j_client

    @property
    def llm_client(self) -> "LLMClient":
        """Get or create LLM client."""
        if self._llm_client is None:
            from tcm_kgraph.llm.client import LLMClient

            self._llm_client = LLMClient(
                api_key=self.settings.llm_api_key.get_secret_value(),
                base_url=self.settings.llm_base_url,
                model=self.settings.llm_model,
                temperature=self.settings.llm_temperature,
                max_tokens=self.settings.llm_max_tokens,
            )
            logger.info("LLM client initialized")
        return self._llm_client

    @property
    def embedding_model(self) -> "EmbeddingModel":
        """Get or create embedding model."""
        if self._embedding_model is None:
            from tcm_kgraph.llm.embeddings import EmbeddingModel

            self._embedding_model = EmbeddingModel(
                model_path=self.settings.embedding_model_path,
                device=self.settings.embedding_device,
            )
            logger.info("Embedding model initialized")
        return self._embedding_model

    async def close(self) -> None:
        """Close all managed resources."""
        if self._neo4j_client is not None:
            await self._neo4j_client.close()
            self._neo4j_client = None
            logger.info("Neo4j client closed")

        if self._embedding_model is not None:
            self._embedding_model = None
            logger.info("Embedding model released")

        if self._llm_client is not None:
            self._llm_client = None
            logger.info("LLM client released")


# Global container instance
_container: Container | None = None


def get_container() -> Container:
    """Get or create the global dependency container."""
    global _container
    if _container is None:
        _container = Container()
    return _container


async def cleanup_container() -> None:
    """Clean up and close the global container."""
    global _container
    if _container is not None:
        await _container.close()
        _container = None
