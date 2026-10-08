"""Routes for scanning the CSV folder and following its imports."""

from data_reaper.domain.ports.dataset_file_storage import (
    AbstractDatasetFileStorage,
)
from data_reaper.domain.ports.import_dispatcher import (
    AbstractImportDispatcher,
)
from data_reaper.domain.ports.repository_sets import (
    AbstractReadRepositories,
    AbstractWriteRepositories,
)
from data_reaper.presentation.api.dependencies import (
    get_current_user,
    get_dataset_file_storage,
    get_import_dispatcher,
    get_read_repositories,
    get_write_repositories,
    require_admin,
)
from data_reaper.schemas.auth import UserOut
from data_reaper.schemas.dataset_import import (
    DatasetImportOut,
    DatasetImportQuery,
    DatasetImportsPageOut,
    ImportScanOut,
)
from data_reaper.services import dataset_import_service
from fastapi import Depends, Query, status
from fastapi.routing import APIRouter

router = APIRouter(prefix="/api/dataset-imports", tags=["Dataset imports"])


@router.get("", response_model=DatasetImportsPageOut)
async def get_imports(
    query: DatasetImportQuery = Depends(),
    limit: int = Query(default=50, ge=1, le=50),
    offset: int = Query(default=0, ge=0, le=250),
    read_repositories: AbstractReadRepositories = Depends(get_read_repositories),
    _: UserOut = Depends(get_current_user),
) -> DatasetImportsPageOut:
    """List Dataset Imports, newest first, with counts per status.

    Filtered by `status`, it is one page of up to 50; unfiltered, it
    paginates up to 300 imports deep.
    """
    return await dataset_import_service.get_imports(
        read_repositories, query, limit=limit, offset=offset
    )


@router.post(
    "/scan", response_model=ImportScanOut, status_code=status.HTTP_202_ACCEPTED
)
async def scan_files(
    write_repositories: AbstractWriteRepositories = Depends(get_write_repositories),
    file_storage: AbstractDatasetFileStorage = Depends(get_dataset_file_storage),
    import_dispatcher: AbstractImportDispatcher = Depends(get_import_dispatcher),
    _: UserOut = Depends(require_admin),
) -> ImportScanOut:
    """Queue an import for every new CSV file now (admin only).

    Celery Beat does the same every minute; this skips the wait.

    Raises:
        ValidationException: 403 for non-admins; 409 if a concurrent
            scan created the same import first.
        ExternalServiceException: the folder or the queue is
            unreachable.
    """
    return await dataset_import_service.discover_files(
        write_repositories, file_storage, import_dispatcher
    )


@router.get("/{import_id}", response_model=DatasetImportOut)
async def get_import(
    import_id: str,
    read_repositories: AbstractReadRepositories = Depends(get_read_repositories),
    _: UserOut = Depends(get_current_user),
) -> DatasetImportOut:
    """Get one Dataset Import, with its counters and rejected rows.

    Raises:
        ValidationException: 404 if it is missing.
    """
    return await dataset_import_service.get_import(read_repositories, import_id)


@router.post(
    "/{import_id}/retry",
    response_model=DatasetImportOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_import(
    import_id: str,
    write_repositories: AbstractWriteRepositories = Depends(get_write_repositories),
    import_dispatcher: AbstractImportDispatcher = Depends(get_import_dispatcher),
    _: UserOut = Depends(require_admin),
) -> DatasetImportOut:
    """Queue a failed or stuck import again (admin only).

    Raises:
        ValidationException: 403 for non-admins; 404 if it is missing;
            409 if it is already imported.
        ExternalServiceException: the queue is unreachable.
    """
    return await dataset_import_service.retry_import(
        write_repositories, import_dispatcher, import_id
    )
