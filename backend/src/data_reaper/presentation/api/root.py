"""The public root route."""

from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

router = APIRouter(redirect_slashes=True)


@router.get("/", include_in_schema=False)
def index() -> JSONResponse:
    """Return a welcome message."""
    return JSONResponse(
        content={"message": "Welcome to the Data Reaper API."},
        status_code=200,
    )
