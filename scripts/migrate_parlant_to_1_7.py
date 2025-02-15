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
from contextlib import asynccontextmanager, AsyncExitStack
import importlib
import logging
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
from parlant.core.nlp.embedding import EmbedderFactory
from parlant.core.persistence.common import ObjectId
from parlant.core.persistence.document_database import DocumentDatabase, identity_loader
from parlant.core.persistence.document_database_helper import _MetadataDocument
from parlant.core.persistence.vector_database import BaseDocument

DEFAULT_HOME_DIR = "runtime-data" if Path("runtime-data").exists() else "parlant-data"
PARLANT_HOME_DIR = Path(os.environ.get("PARLANT_HOME", DEFAULT_HOME_DIR))
PARLANT_HOME_DIR.mkdir(parents=True, exist_ok=True)

EXIT_STACK: AsyncExitStack

sys.path.append(PARLANT_HOME_DIR.as_posix())
sys.path.append(".")

LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def migrate() -> None:
    EXIT_STACK = AsyncExitStack()

    agents_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "agents.json")
    )
    await migrate_document_database(agents_db, "agents")

    context_variables_db = await EXIT_STACK.enter_async_context(
        JSONFileDocumentDatabase(LOGGER, PARLANT_HOME_DIR / "context_variables.json")
    )
    await migrate_document_database(context_variables_db, "context_variables")

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
    await migrate_document_database(guideline_tool_associations_db, "guideline_tool_associations")

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
    await migrate_document_database(services_db, "services")

    await migrate_glossary()


async def migrate_document_database(db: DocumentDatabase, collection_name: str) -> None:
    try:
        collection = db.get_collection(collection_name)
    except ValueError:
        return

    metadata_collection = db.get_or_create_collection(
        "metadata",
        _MetadataDocument,
        identity_loader,
    )

    if document := collection.find_one({}):
        await metadata_collection.insert_one(
            {
                "id": ObjectId(generate_id()),
                "version": document["version"],
            }
        )


async def migrate_glossary(nlp_service_name: str) -> None:
    try:
        embedder_factory = EmbedderFactory(Container())

        db = ChromaDatabase(LOGGER, PARLANT_HOME_DIR, embedder_factory)

        old_collection = db.chroma_client.get_collection("glossary")

        if document := old_collection.find_one({}):
            version = document["version"]
            embedder_module = importlib.import_module(
                old_collection.metadata["embedder_module_path"]
            )
            embedder_type = getattr(
                embedder_module,
                old_collection.metadata["embedder_type_path"],
            )

            all_items = old_collection.get(include=["documents", "embeddings", "metadatas", "ids"])

            _ = db.create_collection(
                "glossary",
                BaseDocument,
                embedder_type,
            )

            chroma_unembedded_collection = db.chroma_client.get(name="glossary_unembedded")
            chroma_new_collection = db.chroma_client.get(
                name=db.format_collection_name("glossary", embedder_type)
            )

            for i in range(len(all_items["metadatas"])):
                new_doc = {
                    **all_items["metadatas"][i],
                    "checksum": md5_checksum(all_items["documents"][i]),
                }

                chroma_unembedded_collection.add(
                    ids=[all_items["ids"][i]],
                    embeddings=[0],
                    metadatas=[cast(chromadb.types.Metadata, new_doc)],
                    documents=[new_doc],
                )

                chroma_new_collection.add(
                    ids=[all_items["ids"][i]],
                    embeddings=all_items["embeddings"][i],
                    metadatas=[cast(chromadb.types.Metadata, new_doc)],
                    documents=[new_doc],
                )

            chroma_unembedded_collection.modify(metadata={"version": i})
            chroma_new_collection.modify(metadata={"version": i})

            db.upsert_metadata(
                "version",
                version,
            )

        db.chroma_client.delete_collection(old_collection.name)

    except Exception as e:
        die(f"Error migrating glossary: {e}")


def die(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    sys.exit(1)


def main() -> None:
    try:
        asyncio.run(migrate())
    except StartupError as e:
        die(e.message)


if __name__ == "__main__":
    main()
