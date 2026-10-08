import pytest
from csv_samples import PLACES_HEADER, file_name, place_line
from data_reaper.core.config import get_settings
from data_reaper.main import app
from data_reaper.presentation.api.dependencies import (
    get_dataset_file_storage,
    get_import_dispatcher,
)
from pymongo import AsyncMongoClient, monitoring


class _CommandRecorder(monitoring.CommandListener):
    """Keep every command the driver sends."""

    def __init__(self) -> None:
        self.commands: list[dict] = []

    def started(self, event: monitoring.CommandStartedEvent) -> None:
        self.commands.append(dict(event.command))

    def succeeded(self, event: monitoring.CommandSucceededEvent) -> None:
        pass

    def failed(self, event: monitoring.CommandFailedEvent) -> None:
        pass


def _transactional(commands: list[dict]) -> list[str]:
    return [
        next(iter(command))
        for command in commands
        if "txnNumber" in command or False is command.get("autocommit")
    ]


@pytest.mark.anyio
async def test_reads_start_no_transaction_but_writes_do(
    mongo_database, serve_app, act_as, file_storage, import_dispatcher
):
    _client, database_name = mongo_database
    recorder = _CommandRecorder()
    mongo_client = AsyncMongoClient(
        get_settings().mongo_url, event_listeners=[recorder]
    )
    file_storage.add(file_name(1), PLACES_HEADER, place_line("r1"))
    act_as("admin")
    try:
        async with serve_app(mongo_client, database_name) as client:
            app.dependency_overrides[get_dataset_file_storage] = lambda: file_storage
            app.dependency_overrides[get_import_dispatcher] = lambda: import_dispatcher
            created = await client.post("/api/dataset-imports/scan")
            write_commands = _transactional(recorder.commands)
            recorder.commands.clear()

            listed = await client.get("/api/dataset-imports")
            read_commands = _transactional(recorder.commands)
    finally:
        await mongo_client.close()

    assert 202 == created.status_code
    assert "commitTransaction" in write_commands
    assert 200 == listed.status_code
    assert recorder.commands
    assert [] == read_commands
