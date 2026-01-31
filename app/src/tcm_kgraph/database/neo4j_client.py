"""Async Neo4j client for graph database operations."""

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from tcm_kgraph.core.exceptions import ConnectionError, QueryError
from tcm_kgraph.core.logging import get_logger


logger = get_logger(__name__)


class Neo4jClient:
    """Async client for Neo4j graph database operations."""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
        max_connection_pool_size: int = 50,
    ) -> None:
        """
        Initialize Neo4j client.

        Args:
            uri: Neo4j connection URI (e.g., bolt://localhost:7687)
            user: Database username
            password: Database password
            database: Database name
            max_connection_pool_size: Maximum connection pool size
        """
        self._uri = uri
        self._database = database
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(
            uri,
            auth=(user, password),
            max_connection_pool_size=max_connection_pool_size,
        )
        logger.info(f"Neo4j client initialized for {uri}")

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Get a database session context manager."""
        session = self._driver.session(database=self._database)
        try:
            yield session
        finally:
            await session.close()

    async def verify_connectivity(self) -> bool:
        """
        Verify database connectivity.

        Returns:
            True if connection is successful

        Raises:
            ConnectionError: If connection fails
        """
        try:
            await self._driver.verify_connectivity()
            logger.debug("Neo4j connectivity verified")
            return True
        except ServiceUnavailable as e:
            raise ConnectionError(
                "Failed to connect to Neo4j",
                details={"uri": self._uri, "error": str(e)},
            ) from e

    async def execute(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a Cypher query and return results.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records as dictionaries

        Raises:
            QueryError: If query execution fails
        """
        parameters = parameters or {}
        try:
            async with self.session() as session:
                result = await session.run(query, parameters)
                records = [record.data() async for record in result]
                logger.debug(f"Query executed, returned {len(records)} records")
                return records
        except Neo4jError as e:
            raise QueryError(
                f"Query execution failed: {e.message}",
                query=query,
                details={"parameters": parameters, "code": e.code},
            ) from e

    async def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a write transaction.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records as dictionaries

        Raises:
            QueryError: If query execution fails
        """
        parameters = parameters or {}

        async def _write_tx(tx: Any) -> list[dict[str, Any]]:
            result = await tx.run(query, parameters)
            return [record.data() async for record in result]

        try:
            async with self.session() as session:
                records = await session.execute_write(_write_tx)
                logger.debug(f"Write transaction executed, returned {len(records)} records")
                return records
        except Neo4jError as e:
            raise QueryError(
                f"Write transaction failed: {e.message}",
                query=query,
                details={"parameters": parameters, "code": e.code},
            ) from e

    async def create_node(
        self,
        labels: list[str],
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Create a new node.

        Args:
            labels: Node labels
            properties: Node properties

        Returns:
            Created node data
        """
        labels_str = ":".join(labels)
        query = f"""
        CREATE (n:{labels_str} $props)
        RETURN n, elementId(n) as id
        """
        results = await self.execute_write(query, {"props": properties})
        if results:
            node_data = dict(results[0]["n"])
            node_data["id"] = results[0]["id"]
            return node_data
        return {}

    async def create_relationship(
        self,
        from_node_id: str,
        to_node_id: str,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a relationship between two nodes.

        Args:
            from_node_id: Source node element ID
            to_node_id: Target node element ID
            relationship_type: Relationship type
            properties: Relationship properties

        Returns:
            Created relationship data
        """
        properties = properties or {}
        query = f"""
        MATCH (a), (b)
        WHERE elementId(a) = $from_id AND elementId(b) = $to_id
        CREATE (a)-[r:{relationship_type} $props]->(b)
        RETURN type(r) as type, properties(r) as properties
        """
        results = await self.execute_write(
            query, {"from_id": from_node_id, "to_id": to_node_id, "props": properties}
        )
        if results:
            return results[0]
        return {}

    async def find_nodes(
        self,
        labels: list[str] | None = None,
        properties: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Find nodes by labels and/or properties.

        Args:
            labels: Node labels to filter by
            properties: Properties to match
            limit: Maximum number of results

        Returns:
            List of matching nodes
        """
        labels_str = ":" + ":".join(labels) if labels else ""
        where_clause = ""
        params: dict[str, Any] = {"limit": limit}

        if properties:
            conditions = [f"n.{k} = ${k}" for k in properties]
            where_clause = "WHERE " + " AND ".join(conditions)
            params.update(properties)

        query = f"""
        MATCH (n{labels_str})
        {where_clause}
        RETURN n, elementId(n) as id
        LIMIT $limit
        """
        results = await self.execute(query, params)
        nodes = []
        for record in results:
            node_data = dict(record["n"])
            node_data["id"] = record["id"]
            nodes.append(node_data)
        return nodes

    async def get_node_relationships(
        self,
        node_id: str,
        direction: str = "both",
        relationship_types: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get relationships for a node.

        Args:
            node_id: Node element ID
            direction: Relationship direction (in/out/both)
            relationship_types: Filter by relationship types
            limit: Maximum number of results

        Returns:
            List of relationships with connected nodes
        """
        type_filter = ""
        if relationship_types:
            type_filter = ":" + "|".join(relationship_types)

        if direction == "out":
            pattern = f"-[r{type_filter}]->"
        elif direction == "in":
            pattern = f"<-[r{type_filter}]-"
        else:
            pattern = f"-[r{type_filter}]-"

        query = f"""
        MATCH (n){pattern}(m)
        WHERE elementId(n) = $node_id
        RETURN type(r) as rel_type, properties(r) as rel_props,
               labels(m) as target_labels, properties(m) as target_props,
               elementId(m) as target_id
        LIMIT $limit
        """
        return await self.execute(query, {"node_id": node_id, "limit": limit})

    async def close(self) -> None:
        """Close the driver connection."""
        await self._driver.close()
        logger.info("Neo4j client closed")
