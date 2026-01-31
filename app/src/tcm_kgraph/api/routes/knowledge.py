"""Knowledge graph query endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from tcm_kgraph.api.dependencies import Neo4jDep, EmbeddingDep
from tcm_kgraph.models.schemas import (
    EntityResponse,
    GraphQueryRequest,
    GraphQueryResponse,
    PaginatedResponse,
    SearchRequest,
    SearchResult,
)
from tcm_kgraph.database.repositories import MedicineRepository, PrescriptionRepository
from tcm_kgraph.core.logging import get_logger


logger = get_logger(__name__)
router = APIRouter()


@router.get("/medicines")
async def list_medicines(
    neo4j: Neo4jDep,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> PaginatedResponse[dict[str, Any]]:
    """
    List all medicines with pagination.
    """
    repo = MedicineRepository(neo4j)
    skip = (page - 1) * page_size

    medicines = await repo.find_all(skip=skip, limit=page_size)
    total = await repo.count()

    items = [m.model_dump() for m in medicines]

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/medicines/{name}")
async def get_medicine(
    name: str,
    neo4j: Neo4jDep,
    include_relations: bool = Query(default=True, description="Include related entities"),
) -> EntityResponse:
    """
    Get a medicine by name with optional related entities.
    """
    repo = MedicineRepository(neo4j)
    medicine = await repo.get_by_name(name)

    if not medicine:
        raise HTTPException(status_code=404, detail=f"Medicine '{name}' not found")

    related_entities: list[dict[str, Any]] = []
    if include_relations and medicine.id:
        # Get related prescriptions
        prescriptions = await repo.get_related_prescriptions(medicine.id)
        for p in prescriptions:
            related_entities.append({
                "type": "Prescription",
                "name": p.get("prescription_name"),
                "relation": "CONTAINS",
                "dosage": p.get("dosage"),
            })

    return EntityResponse(
        entity_type="Medicine",
        entity_id=medicine.id or "",
        data=medicine.model_dump(),
        related_entities=related_entities,
    )


@router.get("/prescriptions")
async def list_prescriptions(
    neo4j: Neo4jDep,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> PaginatedResponse[dict[str, Any]]:
    """
    List all prescriptions with pagination.
    """
    repo = PrescriptionRepository(neo4j)
    skip = (page - 1) * page_size

    prescriptions = await repo.find_all(skip=skip, limit=page_size)
    total = await repo.count()

    items = [p.model_dump() for p in prescriptions]

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/prescriptions/{name}")
async def get_prescription(
    name: str,
    neo4j: Neo4jDep,
    include_composition: bool = Query(default=True, description="Include medicine composition"),
) -> EntityResponse:
    """
    Get a prescription by name with optional composition.
    """
    repo = PrescriptionRepository(neo4j)
    prescription = await repo.get_by_name(name)

    if not prescription:
        raise HTTPException(status_code=404, detail=f"Prescription '{name}' not found")

    related_entities: list[dict[str, Any]] = []
    if include_composition and prescription.id:
        # Get composition
        composition = await repo.get_composition(prescription.id)
        for c in composition:
            related_entities.append({
                "type": "Medicine",
                "name": c.get("medicine_name"),
                "relation": "CONTAINS",
                "dosage": c.get("dosage"),
                "role": c.get("role"),
            })

    return EntityResponse(
        entity_type="Prescription",
        entity_id=prescription.id or "",
        data=prescription.model_dump(),
        related_entities=related_entities,
    )


@router.post("/search")
async def search_entities(
    request: SearchRequest,
    neo4j: Neo4jDep,
    embedding: EmbeddingDep,
) -> list[SearchResult]:
    """
    Search for entities using keyword or semantic search.
    """
    results: list[SearchResult] = []

    # Keyword search in both medicines and prescriptions
    medicine_repo = MedicineRepository(neo4j)
    prescription_repo = PrescriptionRepository(neo4j)

    # Search medicines
    if not request.entity_types or "Medicine" in request.entity_types:
        medicines = await medicine_repo.search(
            request.query,
            fields=["name", "aliases", "functions"],
            limit=request.limit,
        )
        for m in medicines:
            results.append(SearchResult(
                entity_type="Medicine",
                entity_id=m.id or "",
                name=m.name,
                score=0.8,  # Keyword match score
                snippet=", ".join(m.functions[:3]) if m.functions else None,
                metadata={"nature": m.properties.nature} if m.properties else {},
            ))

    # Search prescriptions
    if not request.entity_types or "Prescription" in request.entity_types:
        prescriptions = await prescription_repo.search(
            request.query,
            fields=["name", "aliases", "functions"],
            limit=request.limit,
        )
        for p in prescriptions:
            results.append(SearchResult(
                entity_type="Prescription",
                entity_id=p.id or "",
                name=p.name,
                score=0.8,
                snippet=", ".join(p.functions[:3]) if p.functions else None,
                metadata={"source_book": p.source_book},
            ))

    # Sort by score and limit
    results.sort(key=lambda x: x.score, reverse=True)
    return results[: request.limit]


@router.post("/query")
async def query_graph(
    request: GraphQueryRequest,
    neo4j: Neo4jDep,
) -> GraphQueryResponse:
    """
    Execute a Cypher query on the knowledge graph.
    """
    cypher = request.cypher

    if not cypher and request.natural_language:
        # TODO: Convert natural language to Cypher
        raise HTTPException(
            status_code=501,
            detail="Natural language query conversion not yet implemented",
        )

    if not cypher:
        raise HTTPException(
            status_code=400,
            detail="Either 'cypher' or 'natural_language' must be provided",
        )

    try:
        results = await neo4j.execute(cypher, request.parameters)

        # Parse results into nodes and relationships
        nodes: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []

        for record in results:
            for key, value in record.items():
                if isinstance(value, dict):
                    if "type" in value and "properties" in value:
                        relationships.append(value)
                    else:
                        nodes.append(value)

        return GraphQueryResponse(
            nodes=nodes,
            relationships=relationships,
            raw_results=results,
            generated_cypher=cypher if request.natural_language else None,
        )
    except Exception as e:
        logger.error(f"Graph query failed: {e}")
        raise HTTPException(status_code=400, detail=f"Query execution failed: {e}")
