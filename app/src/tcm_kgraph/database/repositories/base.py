"""Base repository pattern implementation."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from tcm_kgraph.database.neo4j_client import Neo4jClient
from tcm_kgraph.core.logging import get_logger


T = TypeVar("T", bound=BaseModel)
logger = get_logger(__name__)


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository providing common CRUD operations.

    This class implements the Repository pattern for graph database operations,
    providing a clean separation between domain logic and data access.
    """

    def __init__(self, client: Neo4jClient) -> None:
        """
        Initialize repository with Neo4j client.

        Args:
            client: Neo4j async client instance
        """
        self._client = client

    @property
    @abstractmethod
    def node_label(self) -> str:
        """Primary node label for this repository."""
        ...

    @property
    @abstractmethod
    def entity_class(self) -> type[T]:
        """Entity class for this repository."""
        ...

    def _to_entity(self, data: dict[str, Any]) -> T:
        """Convert database record to entity."""
        return self.entity_class.model_validate(data)

    def _to_dict(self, entity: T) -> dict[str, Any]:
        """Convert entity to database-compatible dictionary."""
        return entity.model_dump(exclude_none=True, exclude={"id"})

    async def create(self, entity: T) -> T:
        """
        Create a new entity in the database.

        Args:
            entity: Entity to create

        Returns:
            Created entity with ID
        """
        props = self._to_dict(entity)
        result = await self._client.create_node([self.node_label], props)
        logger.debug(f"Created {self.node_label} node: {result.get('name', result.get('id'))}")
        return self._to_entity(result)

    async def get_by_id(self, entity_id: str) -> T | None:
        """
        Get entity by ID.

        Args:
            entity_id: Entity element ID

        Returns:
            Entity if found, None otherwise
        """
        query = f"""
        MATCH (n:{self.node_label})
        WHERE elementId(n) = $id
        RETURN n, elementId(n) as id
        """
        results = await self._client.execute(query, {"id": entity_id})
        if results:
            data = dict(results[0]["n"])
            data["id"] = results[0]["id"]
            return self._to_entity(data)
        return None

    async def get_by_name(self, name: str) -> T | None:
        """
        Get entity by name.

        Args:
            name: Entity name

        Returns:
            Entity if found, None otherwise
        """
        results = await self._client.find_nodes(
            labels=[self.node_label],
            properties={"name": name},
            limit=1,
        )
        if results:
            return self._to_entity(results[0])
        return None

    async def find_all(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[T]:
        """
        Find all entities with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of entities
        """
        query = f"""
        MATCH (n:{self.node_label})
        RETURN n, elementId(n) as id
        SKIP $skip
        LIMIT $limit
        """
        results = await self._client.execute(query, {"skip": skip, "limit": limit})
        entities = []
        for record in results:
            data = dict(record["n"])
            data["id"] = record["id"]
            entities.append(self._to_entity(data))
        return entities

    async def count(self) -> int:
        """
        Count total entities.

        Returns:
            Total count of entities
        """
        query = f"""
        MATCH (n:{self.node_label})
        RETURN count(n) as count
        """
        results = await self._client.execute(query)
        return results[0]["count"] if results else 0

    async def update(self, entity_id: str, updates: dict[str, Any]) -> T | None:
        """
        Update an entity.

        Args:
            entity_id: Entity element ID
            updates: Dictionary of properties to update

        Returns:
            Updated entity if found, None otherwise
        """
        # Filter out None values and id
        updates = {k: v for k, v in updates.items() if v is not None and k != "id"}
        if not updates:
            return await self.get_by_id(entity_id)

        set_clauses = ", ".join([f"n.{k} = ${k}" for k in updates])
        query = f"""
        MATCH (n:{self.node_label})
        WHERE elementId(n) = $id
        SET {set_clauses}
        RETURN n, elementId(n) as id
        """
        params = {"id": entity_id, **updates}
        results = await self._client.execute_write(query, params)
        if results:
            data = dict(results[0]["n"])
            data["id"] = results[0]["id"]
            return self._to_entity(data)
        return None

    async def delete(self, entity_id: str) -> bool:
        """
        Delete an entity.

        Args:
            entity_id: Entity element ID

        Returns:
            True if deleted, False if not found
        """
        query = f"""
        MATCH (n:{self.node_label})
        WHERE elementId(n) = $id
        DETACH DELETE n
        RETURN count(n) as deleted
        """
        results = await self._client.execute_write(query, {"id": entity_id})
        return results[0]["deleted"] > 0 if results else False

    async def search(
        self,
        query_text: str,
        fields: list[str] | None = None,
        limit: int = 10,
    ) -> list[T]:
        """
        Search entities by text in specified fields.

        Args:
            query_text: Search text
            fields: Fields to search in (default: name, aliases)
            limit: Maximum results

        Returns:
            List of matching entities
        """
        fields = fields or ["name"]
        conditions = [f"toLower(n.{f}) CONTAINS toLower($query)" for f in fields]
        where_clause = " OR ".join(conditions)

        query = f"""
        MATCH (n:{self.node_label})
        WHERE {where_clause}
        RETURN n, elementId(n) as id
        LIMIT $limit
        """
        results = await self._client.execute(query, {"query": query_text, "limit": limit})
        entities = []
        for record in results:
            data = dict(record["n"])
            data["id"] = record["id"]
            entities.append(self._to_entity(data))
        return entities
