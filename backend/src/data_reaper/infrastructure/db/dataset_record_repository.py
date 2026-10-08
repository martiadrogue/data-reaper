"""Shared MongoDB plumbing for the dataset record repositories.

Places and events are stored, queried, and bulk-upserted the same way;
each subclass only names its entity and collection.
"""

import dataclasses
import re
from typing import Any, Generic, TypeVar

from data_reaper.domain.bundles.record_query import RecordQuery
from data_reaper.domain.model.entities import DatasetEvent, DatasetPlace
from data_reaper.infrastructure.db.mongo_repository import (
    MongoRepository,
    Query,
    translate_errors,
)
from pymongo import ASCENDING, ReplaceOne

RecordT = TypeVar("RecordT", DatasetPlace, DatasetEvent)

BY_NAME: list[tuple[str, int]] = [("name", ASCENDING)]


class MongoDatasetRecordRepository(MongoRepository[RecordT], Generic[RecordT]):
    """Base for one Dataset's collection; source + `item_id` unique."""

    conflict_message = "A record with this source and item_id already exists."

    async def get_by_id(self, record_id: str) -> RecordT | None:
        """Return the record with this id, if any."""
        return await self._find_one({"_id": record_id})

    async def get_all_by_item_ids(
        self, source: str, item_ids: list[str]
    ) -> list[RecordT]:
        """Return the records of `source` with these `item_id`s."""
        if not item_ids:
            return []
        return await self._find_many({"source": source, "item_id": {"$in": item_ids}})

    async def get_all(
        self, query: RecordQuery, limit: int | None = None, offset: int = 0
    ) -> list[RecordT]:
        """Return the records matching `query`, by name then id."""
        return await self._find_many(_to_filter(query), BY_NAME, limit, offset)

    async def count_all(self, query: RecordQuery) -> int:
        """Return how many records match `query`."""
        return await self._count(_to_filter(query))

    async def count_by_source(self) -> dict[str, int]:
        """Return how many records each source has."""
        pipeline = [{"$group": {"_id": "$source", "count": {"$sum": 1}}}]
        with translate_errors(self.conflict_message):
            cursor = await self._collection.aggregate(pipeline, session=self._session)
            db_groups = await cursor.to_list()
        return {db_group["_id"]: db_group["count"] for db_group in db_groups}

    async def save_all(self, records: list[RecordT]) -> list[RecordT]:
        """Insert or replace each record by its id, in one bulk write.

        Raises:
            ValidationException: two records would share a natural key
                (409), or the collection validator rejects one (400).
        """
        if not records:
            return []
        db_documents = [_to_document(record) for record in records]
        operations = [
            ReplaceOne({"_id": db_document["_id"]}, db_document, upsert=True)
            for db_document in db_documents
        ]
        with translate_errors(self.conflict_message):
            await self._collection.bulk_write(
                operations, ordered=True, session=self._session
            )
        return [self._to_domain(db_document) for db_document in db_documents]


def _to_document(record: Any) -> dict[str, Any]:
    """Map a record onto its document, `id` stored as `_id`."""
    db_document = dataclasses.asdict(record)
    db_document["_id"] = db_document.pop("id")
    return db_document


def _to_filter(query: RecordQuery) -> Query:
    """Return the MongoDB filter for a record query.

    The text is escaped, so it matches literally, never as a pattern.
    """
    db_filter: Query = {}
    if None is not query.source:
        db_filter["source"] = query.source
    if None is not query.text:
        pattern = {"$regex": re.escape(query.text), "$options": "i"}
        db_filter["$or"] = [{"name": pattern}, {"address": pattern}]
    return db_filter
