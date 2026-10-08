"""Routes for the Datasets: what each collection holds."""

from data_reaper.domain.ports.repository_sets import (
    AbstractReadRepositories,
)
from data_reaper.presentation.api.dependencies import (
    get_current_user,
    get_read_repositories,
)
from data_reaper.schemas.auth import UserOut
from data_reaper.schemas.dataset import DatasetOut
from data_reaper.services import dataset_record_service
from fastapi import Depends
from fastapi.routing import APIRouter

router = APIRouter(prefix="/api/datasets", tags=["Datasets"])


@router.get("", response_model=list[DatasetOut])
async def get_datasets(
    read_repositories: AbstractReadRepositories = Depends(get_read_repositories),
    _: UserOut = Depends(get_current_user),
) -> list[DatasetOut]:
    """List the Datasets with their columns and records per source."""
    return await dataset_record_service.get_datasets(read_repositories)
