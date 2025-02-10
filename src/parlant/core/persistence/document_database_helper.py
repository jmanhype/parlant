from typing import Optional, Protocol
from typing_extensions import TypedDict, Self
from parlant.core.common import Version, generate_id
from parlant.core.persistence.common import MigrationError, ObjectId
from parlant.core.persistence.document_database import DocumentDatabase, identity_loader


class _MetadataDocument(TypedDict, total=False):
    id: ObjectId
    version: Version.String


class VersionedStore(Protocol):
    VERSION: Version


class MigrationHelper:
    def __init__(
        self,
        store: VersionedStore,
        database: DocumentDatabase,
        allow_migration: bool,
    ):
        self._store_name = store.__class__.__name__
        self._runtime_store_version = store.VERSION.to_string()
        self._database = database
        self._allow_migration = allow_migration

    async def __aenter__(self) -> Self:
        migration_required = await self._is_migration_required(
            self._database,
            self._runtime_store_version,
        )

        if migration_required and not self._allow_migration:
            raise MigrationError(f"Migration required for {self._store_name}.")

        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[object],
    ) -> bool:
        if exc_type is None:
            await self._update_metadata_version(self._database, self._runtime_store_version)

        return False

    async def _is_migration_required(
        self,
        database: DocumentDatabase,
        runtime_store_version: Version.String,
    ) -> bool:
        metadata_collection = await database.get_or_create_collection(
            "metadata",
            _MetadataDocument,
            identity_loader,
        )

        if metadata := await metadata_collection.find_one({}):
            return metadata["version"] != runtime_store_version
        else:
            await metadata_collection.insert_one(
                {
                    "id": ObjectId(generate_id()),
                    "version": runtime_store_version,
                }
            )
            return False  # No migration is required for a new store

    async def _update_metadata_version(
        self,
        database: DocumentDatabase,
        runtime_store_version: Version.String,
    ) -> None:
        metadata_collection = await database.get_or_create_collection(
            "metadata",
            _MetadataDocument,
            identity_loader,
        )

        for doc in await metadata_collection.find({}):
            await metadata_collection.update_one(
                filters={"id": {"$eq": doc["id"]}},
                params={"version": runtime_store_version},
            )
