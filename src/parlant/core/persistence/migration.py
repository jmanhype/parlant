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
# limitations under the License

from abc import ABC, abstractmethod
from typing import TypedDict, cast
from typing_extensions import override

from lagom import Container

from parlant.core.agents import _AgentDocument, AgentDocumentStore
from parlant.core.common import SchemaVersion, VersionReport
from parlant.core.context_variables import ContextVariableDocumentStore
from parlant.core.customers import CustomerDocumentStore
from parlant.core.documents.agents import _AgentDocument_v1
from parlant.core.documents.glossary import _TermDocument_v1
from parlant.core.evaluations import EvaluationDocumentStore
from parlant.core.glossary import GlossaryVectorStore, _TermDocument
from parlant.core.guideline_connections import GuidelineConnectionDocumentStore
from parlant.core.guideline_tool_associations import GuidelineToolAssociationDocumentStore
from parlant.core.guidelines import GuidelineDocumentStore
from parlant.core.logging import Logger
from parlant.core.persistence.common import VersionedDatabase
from parlant.core.persistence.document_database import DocumentCollection, DocumentDatabase
from parlant.core.persistence.vector_database import VectorCollection, VectorDatabase
from parlant.core.services.tools.service_registry import ServiceDocumentRegistry
from parlant.core.sessions import SessionDocumentStore
from parlant.core.tags import TagDocumentStore


AGENTS: str = "agents"
CONTEXT_VARIABLES: str = "context_variables"
CUSTOMERS: str = "customers"
EVALUATIONS: str = "evaluations"
GLOSSARY: str = "glossary"
GUIDELINE_CONNECTIONS: str = "guideline_connections"
GUIDELINE_TOOL_ASSOCIATIONS: str = "guideline_tool_associations"
GUIDELINES: str = "guidelines"
SERVICES: str = "services"
SESSIONS: str = "sessions"
TAGS: str = "tags"


class DatabaseContainer(TypedDict, total=True):
    agents: DocumentDatabase
    context_variables: DocumentDatabase
    customers: DocumentDatabase
    evaluations: DocumentDatabase
    glossary: VectorDatabase
    guideline_connections: DocumentDatabase
    guideline_tool_associations: DocumentDatabase
    guidelines: DocumentDatabase
    services: DocumentDatabase
    sessions: DocumentDatabase
    tags: DocumentDatabase


STORE_SCHEMA_VERSIONS: VersionReport = {
    AGENTS: AgentDocumentStore.VERSION,
    CONTEXT_VARIABLES: ContextVariableDocumentStore.VERSION,
    CUSTOMERS: CustomerDocumentStore.VERSION,
    EVALUATIONS: EvaluationDocumentStore.VERSION,
    GLOSSARY: GlossaryVectorStore.VERSION,
    GUIDELINE_CONNECTIONS: GuidelineConnectionDocumentStore.VERSION,
    GUIDELINE_TOOL_ASSOCIATIONS: GuidelineToolAssociationDocumentStore.VERSION,
    GUIDELINES: GuidelineDocumentStore.VERSION,
    SERVICES: ServiceDocumentRegistry.VERSION,
    SESSIONS: SessionDocumentStore.VERSION,
    TAGS: TagDocumentStore.VERSION,
}


def verify_schema_version(
    logger: Logger,
    database: VersionedDatabase,
    store_version: SchemaVersion,
    migration: bool = False,
) -> bool:
    if database.version == store_version:
        return True

    if store_version > database.version:
        log = logger.info if migration else logger.error
        log(
            f"`{database.name}`: store expects version={store_version}, but version={database.version} was found in the database."
        )
    else:
        logger.critical(
            f"version={database.version} - found in the database - is not supported, please update your code or delete the cache."
        )
    return False


class Migration(ABC):
    @property
    @abstractmethod
    def required_versions(self) -> VersionReport:
        """Return the versions this migrations requires to run."""
        ...

    @abstractmethod
    async def do_migration(self, container: DatabaseContainer) -> None:
        """Perform the migration."""
        ...


async def perform_migrations(migration_container: Container) -> None:
    database_container = migration_container[DatabaseContainer]

    for migration in MIGRATIONS:
        required_versions = migration.required_versions
        run_migration = len(required_versions) > 0
        for name, db_obj in database_container.items():
            database = cast(VersionedDatabase, db_obj)
            if name not in required_versions or required_versions[name] != database.version:
                run_migration = False
                break

        if not run_migration:
            continue

        await migration.do_migration(database_container)


class Migration_V0ToV1(Migration):
    @property
    @override
    def required_versions(self) -> VersionReport:
        return {
            AGENTS: SchemaVersion(0),
            CONTEXT_VARIABLES: SchemaVersion(0),
            CUSTOMERS: SchemaVersion(0),
            EVALUATIONS: SchemaVersion(0),
            GLOSSARY: SchemaVersion(0),
            GUIDELINE_CONNECTIONS: SchemaVersion(0),
            GUIDELINE_TOOL_ASSOCIATIONS: SchemaVersion(0),
            GUIDELINES: SchemaVersion(0),
            SERVICES: SchemaVersion(0),
            SESSIONS: SchemaVersion(0),
            TAGS: SchemaVersion(0),
        }

    @override
    async def do_migration(self, container: DatabaseContainer) -> None:
        # agents
        async with container["agents"] as agents_db:
            agents_v0_collection: DocumentCollection[
                _AgentDocument
            ] = await agents_db.get_collection(AGENTS)
            agents_v1_collection: DocumentCollection[
                _AgentDocument_v1
            ] = await agents_db.get_or_create_collection(
                f"{AGENTS.lower()}_v1",
                _AgentDocument_v1,
            )
            for agent_v0_document in await agents_v0_collection.find({}):
                await agents_v1_collection.insert_one(_AgentDocument_v1(agent_v0_document))

            await agents_db.delete_collection(AGENTS)
            agents_db.version = STORE_SCHEMA_VERSIONS[AGENTS]

        # context_variables
        # customers
        # evaluations
        # glossary
        async with container["glossary"] as glossary_db:
            term_v0_collection: VectorCollection[_TermDocument] = await glossary_db.get_collection(
                "glossary"
            )
            term_v1_collection: VectorCollection[
                _TermDocument_v1
            ] = await glossary_db.get_or_create_collection(
                "glossary_v1",
                _TermDocument_v1,
                embedder_type=type(term_v0_collection._embedder),
            )
            for term_v0_document in await term_v0_collection.find({}):
                await term_v1_collection.insert_one(_TermDocument_v1(term_v0_document))

            await glossary_db.delete_collection("glossary")
            glossary_db.version = STORE_SCHEMA_VERSIONS["glossary"]

        # guideline_connections
        # guideline_tool_associations
        # guidelines
        # sessions
        # tools

        return None


MIGRATIONS: list[Migration] = [
    Migration_V0ToV1(),
]
