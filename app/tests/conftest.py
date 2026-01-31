"""Pytest configuration and fixtures."""

import asyncio
from typing import AsyncIterator, Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from tcm_kgraph.api.app import create_app
from tcm_kgraph.core.config import Settings
from tcm_kgraph.database.neo4j_client import Neo4jClient
from tcm_kgraph.llm.client import LLMClient


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with mock values."""
    return Settings(
        llm_api_key="test-api-key",
        neo4j_password="test-password",
        embedding_model_path="test/model",
        log_level="DEBUG",
    )


@pytest.fixture
def mock_neo4j_client() -> AsyncMock:
    """Create mock Neo4j client."""
    client = AsyncMock(spec=Neo4jClient)
    client.verify_connectivity = AsyncMock(return_value=True)
    client.execute = AsyncMock(return_value=[])
    client.execute_write = AsyncMock(return_value=[])
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Create mock LLM client."""
    client = MagicMock(spec=LLMClient)
    client.chat = AsyncMock(return_value="Test response")
    client.generate = AsyncMock(return_value="Test generated text")
    client.extract_json = AsyncMock(return_value={"test": "data"})
    return client


@pytest.fixture
async def test_client(
    mock_neo4j_client: AsyncMock,
    mock_llm_client: MagicMock,
) -> AsyncIterator[AsyncClient]:
    """Create test HTTP client for API testing."""
    app = create_app()

    # Override container with mocks
    from tcm_kgraph.core.dependencies import Container

    mock_container = MagicMock(spec=Container)
    mock_container.neo4j_client = mock_neo4j_client
    mock_container.llm_client = mock_llm_client
    app.state.container = mock_container

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# Sample test data fixtures
@pytest.fixture
def sample_medicine_data() -> dict:
    """Sample medicine data for testing."""
    return {
        "name": "黄芪",
        "pinyin": "Huang Qi",
        "aliases": ["黄耆", "绵芪"],
        "nature": "温",
        "flavors": ["甘"],
        "meridians": ["肺经", "脾经"],
        "functions": ["补气升阳", "固表止汗"],
        "indications": ["气虚乏力", "食少便溏"],
        "usage": "9-30g",
    }


@pytest.fixture
def sample_prescription_data() -> dict:
    """Sample prescription data for testing."""
    return {
        "name": "四君子汤",
        "pinyin": "Si Jun Zi Tang",
        "source_book": "《太平惠民和剂局方》",
        "composition": [
            {"medicine_name": "人参", "dosage": "10g"},
            {"medicine_name": "白术", "dosage": "9g"},
            {"medicine_name": "茯苓", "dosage": "9g"},
            {"medicine_name": "甘草", "dosage": "6g"},
        ],
        "functions": ["益气健脾"],
        "indications": ["脾胃气虚证"],
    }


@pytest.fixture
def sample_medicine_text() -> str:
    """Sample medicine raw text for extraction testing."""
    return """
    黄芪
    拼音名：Huang Qi
    别名：黄耆、绵芪
    来源：豆科植物蒙古黄芪或膜荚黄芪的干燥根。
    性味：甘，温。
    归经：肺经、脾经。
    功效：补气升阳，固表止汗，利水消肿，生津养血，托毒生肌。
    主治：气虚乏力，食少便溏，中气下陷，久泻脱肛，便血崩漏。
    用法用量：9-30g。
    禁忌：表实邪盛、气滞湿阻、食积停滞者慎用。
    """
