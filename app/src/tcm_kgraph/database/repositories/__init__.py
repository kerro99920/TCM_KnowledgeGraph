"""Repository pattern implementations for data access."""

from tcm_kgraph.database.repositories.base import BaseRepository
from tcm_kgraph.database.repositories.medicine import MedicineRepository
from tcm_kgraph.database.repositories.prescription import PrescriptionRepository

__all__ = ["BaseRepository", "MedicineRepository", "PrescriptionRepository"]
