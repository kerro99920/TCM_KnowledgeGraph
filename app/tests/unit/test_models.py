"""Unit tests for data models."""

import pytest
from datetime import datetime

from tcm_kgraph.models.entities import (
    Medicine,
    MedicineProperty,
    Prescription,
    Disease,
    Symptom,
)
from tcm_kgraph.models.schemas import (
    HealthResponse,
    HealthStatus,
    SearchRequest,
    SearchResult,
    ChatRequest,
    ChatResponse,
    PaginatedResponse,
)


class TestMedicineModel:
    """Tests for Medicine entity model."""

    def test_create_medicine_minimal(self):
        """Test creating a medicine with minimal fields."""
        medicine = Medicine(name="黄芪")
        assert medicine.name == "黄芪"
        assert medicine.aliases == []
        assert medicine.functions == []

    def test_create_medicine_full(self, sample_medicine_data):
        """Test creating a medicine with all fields."""
        properties = MedicineProperty(
            nature=sample_medicine_data["nature"],
            flavor=sample_medicine_data["flavors"],
            meridians=sample_medicine_data["meridians"],
        )
        medicine = Medicine(
            name=sample_medicine_data["name"],
            pinyin=sample_medicine_data["pinyin"],
            aliases=sample_medicine_data["aliases"],
            properties=properties,
            functions=sample_medicine_data["functions"],
            indications=sample_medicine_data["indications"],
            usage=sample_medicine_data["usage"],
        )

        assert medicine.name == "黄芪"
        assert medicine.pinyin == "Huang Qi"
        assert len(medicine.aliases) == 2
        assert medicine.properties.nature == "温"
        assert len(medicine.functions) == 2

    def test_medicine_property_immutable(self):
        """Test that MedicineProperty is immutable (frozen)."""
        prop = MedicineProperty(nature="温", flavor=["甘"])
        with pytest.raises(Exception):
            prop.nature = "寒"


class TestPrescriptionModel:
    """Tests for Prescription entity model."""

    def test_create_prescription_minimal(self):
        """Test creating a prescription with minimal fields."""
        prescription = Prescription(name="四君子汤")
        assert prescription.name == "四君子汤"
        assert prescription.composition == []

    def test_create_prescription_full(self, sample_prescription_data):
        """Test creating a prescription with all fields."""
        prescription = Prescription(
            name=sample_prescription_data["name"],
            pinyin=sample_prescription_data["pinyin"],
            source_book=sample_prescription_data["source_book"],
            composition=sample_prescription_data["composition"],
            functions=sample_prescription_data["functions"],
            indications=sample_prescription_data["indications"],
        )

        assert prescription.name == "四君子汤"
        assert len(prescription.composition) == 4
        assert prescription.composition[0]["medicine_name"] == "人参"


class TestSchemas:
    """Tests for API schemas."""

    def test_health_response(self):
        """Test HealthResponse schema."""
        response = HealthResponse(
            status=HealthStatus.HEALTHY,
            version="1.0.0",
            components={"neo4j": HealthStatus.HEALTHY},
        )
        assert response.status == HealthStatus.HEALTHY
        assert response.version == "1.0.0"

    def test_search_request_validation(self):
        """Test SearchRequest validation."""
        # Valid request
        request = SearchRequest(query="黄芪", limit=10)
        assert request.query == "黄芪"
        assert request.limit == 10

        # Invalid: empty query
        with pytest.raises(Exception):
            SearchRequest(query="", limit=10)

        # Invalid: limit too high
        with pytest.raises(Exception):
            SearchRequest(query="test", limit=200)

    def test_search_result(self):
        """Test SearchResult schema."""
        result = SearchResult(
            entity_type="Medicine",
            entity_id="123",
            name="黄芪",
            score=0.95,
            snippet="补气升阳...",
        )
        assert result.score >= 0 and result.score <= 1

    def test_chat_request(self):
        """Test ChatRequest schema."""
        request = ChatRequest(
            message="黄芪有什么功效?",
            use_knowledge_graph=True,
        )
        assert request.message == "黄芪有什么功效?"
        assert request.history == []

    def test_paginated_response(self):
        """Test PaginatedResponse creation."""
        items = [{"id": 1}, {"id": 2}, {"id": 3}]
        response = PaginatedResponse.create(
            items=items,
            total=10,
            page=1,
            page_size=3,
        )

        assert len(response.items) == 3
        assert response.total == 10
        assert response.page == 1
        assert response.total_pages == 4
