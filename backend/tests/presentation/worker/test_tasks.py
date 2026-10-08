import json
import logging
from contextlib import asynccontextmanager

import pytest
from data_reaper.core.logging import JsonFormatter
from data_reaper.presentation.worker import tasks


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.setFormatter(JsonFormatter())
        self.lines = []

    def emit(self, record):
        self.lines.append(json.loads(self.format(record)))


@pytest.mark.anyio
async def test_logs_of_an_import_carry_its_import_id(monkeypatch):
    @asynccontextmanager
    async def open_infrastructure():
        yield object()

    async def process_import(infrastructure, import_id):
        logging.getLogger("data_reaper.services.example").info("Step")
        return "imported"

    monkeypatch.setattr(tasks, "open_import_infrastructure", open_infrastructure)
    monkeypatch.setattr(
        tasks.import_processing_service, "process_import", process_import
    )
    handler = _ListHandler()
    logger = logging.getLogger("data_reaper.services.example")
    logger.addHandler(handler)
    try:
        assert "imported" == await tasks._import_dataset_file("import-1")
        logger.info("After the import")
    finally:
        logger.removeHandler(handler)

    assert "import-1" == handler.lines[0]["import_id"]
    assert "import_id" not in handler.lines[1]


@pytest.mark.anyio
async def test_discovery_hands_its_ports_to_the_service(monkeypatch):
    seen = []

    @asynccontextmanager
    async def open_repositories():
        yield "factories"

    async def dispatch_new_files(factories, file_storage, import_dispatcher):
        seen.append((factories, file_storage, import_dispatcher))
        return 2

    monkeypatch.setattr(tasks, "open_task_repositories", open_repositories)
    monkeypatch.setattr(tasks, "create_dataset_file_storage", lambda: "storage")
    monkeypatch.setattr(tasks, "create_import_dispatcher", lambda: "dispatcher")
    monkeypatch.setattr(
        tasks.dataset_import_service, "dispatch_new_files", dispatch_new_files
    )

    assert 2 == await tasks._discover_dataset_files()
    assert [("factories", "storage", "dispatcher")] == seen
