# Copyright 2024 Emcie Co Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
from contextlib import AsyncExitStack
import importlib
import os
from typing import cast
import chromadb
from lagom import Container
from typing_extensions import NoReturn
from pathlib import Path
import sys

from parlant.adapters.db.json_file import JSONFileDocumentDatabase
from parlant.adapters.vector_db.chroma import ChromaDatabase
from parlant.bin.server import StartupError
from parlant.core.common import generate_id, md5_checksum
from parlant.core.contextual_correlator import ContextualCorrelator
from parlant.core.logging import LogLevel, StdoutLogger
from parlant.core.nlp.embedding import EmbedderFactory
from parlant.core.persistence.common import ObjectId
from parlant.core.persistence.document_database import DocumentDatabase, identity_loader
from parlant.core.persistence.document_database_helper import _MetadataDocument
from parlant.core.persistence.vector_database import BaseDocument

PARENT_DIR = Path(__file__).parent.parent
DEFAULT_HOME_DIR = (
    (PARENT_DIR / "runtime-data").as_posix()
    if (PARENT_DIR / "runtime-data").exists()
    else (PARENT_DIR / "parlant-data").as_posix()
)
PARLANT_HOME_DIR = Path(os.environ.get("PARLANT_HOME", DEFAULT_HOME_DIR))
PARLANT_HOME_DIR.mkdir(parents=True, exist_ok=True)

EXIT_STACK = AsyncExitStack()

sys.path.append(PARLANT_HOME_DIR.as_posix())
sys.path.append(".")

LOGGER = StdoutLogger(
    correlator=ContextualCorrelator(),
    log_level=LogLevel.INFO,
)


async def migrate() -> None:
    LOGGER.info("Starting migration process...")

    agents_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "agents.json")
    )
    await migrate_document_database(agents_db, "agents")

    context_variables_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "context_variables.json")
    )
    await migrate_document_database(context_variables_db, "variables")

    tags_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "tags.json")
    )
    await migrate_document_database(tags_db, "tags")

    customers_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "customers.json")
    )
    await migrate_document_database(customers_db, "customers")

    sessions_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "sessions.json")
    )
    await migrate_document_database(sessions_db, "sessions")

    guideline_tool_associations_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "guideline_tool_associations.json")
    )
    await migrate_document_database(guideline_tool_associations_db, "associations")

    guidelines_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "guidelines.json")
    )
    await migrate_document_database(guidelines_db, "guidelines")

    guideline_connections_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "guideline_connections.json")
    )
    await migrate_document_database(guideline_connections_db, "guideline_connections")

    evaluations_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "evaluations.json")
    )
    await migrate_document_database(evaluations_db, "evaluations")

    services_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "services.json")
    )
    await migrate_document_database(services_db, "tool_services")

    await migrate_glossary()
    LOGGER.info("Migration completed successfully")


async def migrate_document_database(db: DocumentDatabase, collection_name: str) -> None:
    LOGGER.info(f"Migrating {collection_name} database...")
    try:
        collection = await db.get_collection(
            collection_name,
            BaseDocument,
            identity_loader,
        )

    except ValueError:
        LOGGER.info(f"Collection {collection_name} not found, skipping...")
        return

    try:
        metadata_collection = await db.get_collection(
            "metadata",
            BaseDocument,
            identity_loader,
        )
        await db.delete_collection("metadata")

    except ValueError:
        pass

    metadata_collection = await db.get_or_create_collection(
        "metadata",
        _MetadataDocument,
        identity_loader,
    )

    if document := await collection.find_one({}):
        await metadata_collection.insert_one(
            {
                "id": ObjectId(generate_id()),
                "version": document["version"],
            }
        )
        LOGGER.info(f"Successfully migrated {collection_name} database")
    else:
        LOGGER.info(f"No documents found in {collection_name} collection.")


async def migrate_glossary() -> None:
    LOGGER.info("Starting glossary migration...")
    try:
        embedder_factory = EmbedderFactory(Container())

        db = await EXIT_STACK.enter_async_context(
            ChromaDatabase(LOGGER, PARLANT_HOME_DIR, embedder_factory)
        )

        try:
            old_collection = db.chroma_client.get_collection("glossary")
        except chromadb.errors.InvalidCollectionException:
            LOGGER.info("Glossary collection not found, skipping...")
            return

        if docs := old_collection.peek(limit=1)["metadatas"]:
            document = docs[0]

            version = document["version"]

            embedder_module = importlib.import_module(
                old_collection.metadata["embedder_module_path"]
            )
            embedder_type = getattr(
                embedder_module,
                old_collection.metadata["embedder_type_path"],
            )

            all_items = old_collection.get(include=["documents", "embeddings", "metadatas"])
            LOGGER.info(f"Found {len(all_items['ids'])} items to migrate")

            chroma_unembedded_collection = next(
                (
                    collection
                    for collection in db.chroma_client.list_collections()
                    if collection.name == "glossary_unembedded"
                ),
                None,
            ) or db.chroma_client.create_collection(name="glossary_unembedded")

            chroma_new_collection = next(
                (
                    collection
                    for collection in db.chroma_client.list_collections()
                    if collection.name == db.format_collection_name("glossary", embedder_type)
                ),
                None,
            ) or db.chroma_client.create_collection(
                name=db.format_collection_name("glossary", embedder_type)
            )

            for i in range(len(all_items["metadatas"])):
                new_doc = {
                    **all_items["metadatas"][i],
                    "checksum": md5_checksum(all_items["documents"][i]),
                }

                chroma_unembedded_collection.add(
                    ids=[all_items["ids"][i]],
                    documents=[new_doc["content"]],
                    metadatas=[cast(chromadb.types.Metadata, new_doc)],
                    embeddings=[0],
                )

                chroma_new_collection.add(
                    ids=[all_items["ids"][i]],
                    documents=[new_doc["content"]],
                    metadatas=[cast(chromadb.types.Metadata, new_doc)],
                    embeddings=all_items["embeddings"][i],
                )

            # Version starts at 1
            chroma_unembedded_collection.modify(
                metadata={"version": 1 + len(all_items["metadatas"])}
            )
            chroma_new_collection.modify(metadata={"version": 1 + len(all_items["metadatas"])})

            db.upsert_metadata(
                "version",
                version,
            )
            LOGGER.info("Successfully migrated glossary data")

        db.chroma_client.delete_collection(old_collection.name)
        LOGGER.info("Cleaned up old glossary collection")

    except Exception as e:
        LOGGER.error(f"Failed to migrate glossary: {e}")
        die(f"Error migrating glossary: {e}")


def die(message: str) -> NoReturn:
    LOGGER.critical(message)
    print(message, file=sys.stderr)
    sys.exit(1)


def main() -> None:
    try:
        asyncio.run(migrate())
    except StartupError as e:
        die(e.message)


if __name__ == "__main__":
    main()
