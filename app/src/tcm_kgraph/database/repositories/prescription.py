"""Prescription repository for TCM formula entities."""

from typing import Any

from tcm_kgraph.database.neo4j_client import Neo4jClient
from tcm_kgraph.database.repositories.base import BaseRepository
from tcm_kgraph.models.entities import Prescription
from tcm_kgraph.core.logging import get_logger


logger = get_logger(__name__)


class PrescriptionRepository(BaseRepository[Prescription]):
    """Repository for Prescription (方剂) entities."""

    def __init__(self, client: Neo4jClient) -> None:
        super().__init__(client)

    @property
    def node_label(self) -> str:
        return "Prescription"

    @property
    def entity_class(self) -> type[Prescription]:
        return Prescription

    async def find_by_function(self, function: str, limit: int = 20) -> list[Prescription]:
        """
        Find prescriptions by function/effect.

        Args:
            function: Function keyword to search for
            limit: Maximum results

        Returns:
            List of prescriptions with matching functions
        """
        query = """
        MATCH (n:Prescription)
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

    async def find_by_source_book(self, source_book: str, limit: int = 20) -> list[Prescription]:
        """
        Find prescriptions by source book (出处).

        Args:
            source_book: Source book name
            limit: Maximum results

        Returns:
            List of prescriptions from the source book
        """
        query = """
        MATCH (n:Prescription)
        WHERE toLower(n.source_book) CONTAINS toLower($source_book)
        RETURN n, elementId(n) as id
        LIMIT $limit
        """
        results = await self._client.execute(query, {"source_book": source_book, "limit": limit})
        entities = []
        for record in results:
            data = dict(record["n"])
            data["id"] = record["id"]
            entities.append(self._to_entity(data))
        return entities

    async def find_containing_medicine(
        self,
        medicine_name: str,
        limit: int = 20,
    ) -> list[Prescription]:
        """
        Find prescriptions containing a specific medicine.

        Args:
            medicine_name: Medicine name to search for
            limit: Maximum results

        Returns:
            List of prescriptions containing the medicine
        """
        query = """
        MATCH (p:Prescription)-[:CONTAINS]->(m:Medicine)
        WHERE toLower(m.name) = toLower($medicine_name)
        RETURN p, elementId(p) as id
        LIMIT $limit
        """
        results = await self._client.execute(query, {"medicine_name": medicine_name, "limit": limit})
        entities = []
        for record in results:
            data = dict(record["p"])
            data["id"] = record["id"]
            entities.append(self._to_entity(data))
        return entities

    async def get_composition(self, prescription_id: str) -> list[dict[str, Any]]:
        """
        Get the composition (药物组成) of a prescription.

        Args:
            prescription_id: Prescription element ID

        Returns:
            List of medicines in the prescription with dosage info
        """
        query = """
        MATCH (p:Prescription)-[r:CONTAINS]->(m:Medicine)
        WHERE elementId(p) = $prescription_id
        RETURN m.name as medicine_name, elementId(m) as medicine_id,
               r.dosage as dosage, r.role as role
        ORDER BY r.role, m.name
        """
        return await self._client.execute(query, {"prescription_id": prescription_id})

    async def get_related_diseases(
        self,
        prescription_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Get diseases treated by this prescription.

        Args:
            prescription_id: Prescription element ID
            limit: Maximum results

        Returns:
            List of related diseases
        """
        query = """
        MATCH (p:Prescription)-[:TREATS]->(d:Disease)
        WHERE elementId(p) = $prescription_id
        RETURN d.name as disease_name, elementId(d) as disease_id
        LIMIT $limit
        """
        return await self._client.execute(query, {"prescription_id": prescription_id, "limit": limit})

    async def create_with_composition(
        self,
        prescription: Prescription,
        composition: list[dict[str, str]],
    ) -> Prescription:
        """
        Create prescription with medicine composition relationships.

        Args:
            prescription: Prescription entity to create
            composition: List of dicts with 'medicine_name', 'dosage', and optional 'role'

        Returns:
            Created prescription
        """
        # Create the prescription node
        created = await self.create(prescription)

        # Create relationships to medicines
        if created.id:
            for comp in composition:
                query = """
                MATCH (p:Prescription), (m:Medicine)
                WHERE elementId(p) = $prescription_id AND m.name = $medicine_name
                MERGE (p)-[r:CONTAINS]->(m)
                SET r.dosage = $dosage, r.role = $role
                """
                await self._client.execute_write(
                    query,
                    {
                        "prescription_id": created.id,
                        "medicine_name": comp.get("medicine_name", ""),
                        "dosage": comp.get("dosage", ""),
                        "role": comp.get("role", ""),
                    },
                )

        logger.info(f"Created prescription '{prescription.name}' with {len(composition)} medicines")
        return created

    async def find_similar(
        self,
        prescription_id: str,
        min_common_medicines: int = 3,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Find similar prescriptions based on shared medicines.

        Args:
            prescription_id: Source prescription element ID
            min_common_medicines: Minimum number of shared medicines
            limit: Maximum results

        Returns:
            List of similar prescriptions with similarity info
        """
        query = """
        MATCH (p1:Prescription)-[:CONTAINS]->(m:Medicine)<-[:CONTAINS]-(p2:Prescription)
        WHERE elementId(p1) = $prescription_id AND p1 <> p2
        WITH p2, count(m) as common_count
        WHERE common_count >= $min_common
        RETURN p2.name as name, elementId(p2) as id, common_count
        ORDER BY common_count DESC
        LIMIT $limit
        """
        return await self._client.execute(
            query,
            {
                "prescription_id": prescription_id,
                "min_common": min_common_medicines,
                "limit": limit,
            },
        )
