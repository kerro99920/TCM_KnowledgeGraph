"""Medicine repository for TCM drug entities."""

from typing import Any

from tcm_kgraph.database.neo4j_client import Neo4jClient
from tcm_kgraph.database.repositories.base import BaseRepository
from tcm_kgraph.models.entities import Medicine
from tcm_kgraph.core.logging import get_logger


logger = get_logger(__name__)


class MedicineRepository(BaseRepository[Medicine]):
    """Repository for Medicine (中药) entities."""

    def __init__(self, client: Neo4jClient) -> None:
        super().__init__(client)

    @property
    def node_label(self) -> str:
        return "Medicine"

    @property
    def entity_class(self) -> type[Medicine]:
        return Medicine

    async def find_by_function(self, function: str, limit: int = 20) -> list[Medicine]:
        """
        Find medicines by function/effect.

        Args:
            function: Function keyword to search for
            limit: Maximum results

        Returns:
            List of medicines with matching functions
        """
        query = """
        MATCH (n:Medicine)
        WHERE any(f IN n.functions WHERE toLower(f) CONTAINS toLower($function))
        RETURN n, elementId(n) as id
        LIMIT $limit
        """
        results = await self._client.execute(query, {"function": function, "limit": limit})
        entities = []
        for record in results:
            data = dict(record["n"])
            data["id"] = record["id"]
            entities.append(self._to_entity(data))
        return entities

    async def find_by_meridian(self, meridian: str, limit: int = 20) -> list[Medicine]:
        """
        Find medicines by meridian (归经).

        Args:
            meridian: Meridian name
            limit: Maximum results

        Returns:
            List of medicines associated with the meridian
        """
        query = """
        MATCH (n:Medicine)
        WHERE any(m IN n.properties.meridians WHERE toLower(m) CONTAINS toLower($meridian))
        RETURN n, elementId(n) as id
        LIMIT $limit
        """
        results = await self._client.execute(query, {"meridian": meridian, "limit": limit})
        entities = []
        for record in results:
            data = dict(record["n"])
            data["id"] = record["id"]
            entities.append(self._to_entity(data))
        return entities

    async def find_by_nature(self, nature: str, limit: int = 20) -> list[Medicine]:
        """
        Find medicines by nature (药性: 寒/热/温/凉/平).

        Args:
            nature: Medicine nature
            limit: Maximum results

        Returns:
            List of medicines with matching nature
        """
        query = """
        MATCH (n:Medicine)
        WHERE n.properties.nature = $nature
        RETURN n, elementId(n) as id
        LIMIT $limit
        """
        results = await self._client.execute(query, {"nature": nature, "limit": limit})
        entities = []
        for record in results:
            data = dict(record["n"])
            data["id"] = record["id"]
            entities.append(self._to_entity(data))
        return entities

    async def get_related_prescriptions(
        self,
        medicine_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Get prescriptions containing this medicine.

        Args:
            medicine_id: Medicine element ID
            limit: Maximum results

        Returns:
            List of related prescriptions with relationship details
        """
        query = """
        MATCH (m:Medicine)<-[r:CONTAINS]-(p:Prescription)
        WHERE elementId(m) = $medicine_id
        RETURN p.name as prescription_name, elementId(p) as prescription_id,
               r.dosage as dosage, r.role as role
        LIMIT $limit
        """
        return await self._client.execute(query, {"medicine_id": medicine_id, "limit": limit})

    async def create_with_relationships(
        self,
        medicine: Medicine,
        related_diseases: list[str] | None = None,
        contraindicated_with: list[str] | None = None,
    ) -> Medicine:
        """
        Create medicine with relationships.

        Args:
            medicine: Medicine entity to create
            related_diseases: List of disease names this medicine treats
            contraindicated_with: List of medicine names this is contraindicated with

        Returns:
            Created medicine
        """
        # Create the medicine node
        created = await self.create(medicine)

        # Create relationships to diseases
        if related_diseases and created.id:
            for disease_name in related_diseases:
                query = """
                MATCH (m:Medicine), (d:Disease)
                WHERE elementId(m) = $medicine_id AND d.name = $disease_name
                MERGE (m)-[:TREATS]->(d)
                """
                await self._client.execute_write(
                    query, {"medicine_id": created.id, "disease_name": disease_name}
                )

        # Create contraindication relationships
        if contraindicated_with and created.id:
            for other_medicine in contraindicated_with:
                query = """
                MATCH (m1:Medicine), (m2:Medicine)
                WHERE elementId(m1) = $medicine_id AND m2.name = $other_name
                MERGE (m1)-[:CONTRAINDICATED_WITH]->(m2)
                """
                await self._client.execute_write(
                    query, {"medicine_id": created.id, "other_name": other_medicine}
                )

        logger.info(f"Created medicine '{medicine.name}' with relationships")
        return created
