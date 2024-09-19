from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum, auto
from typing import NewType, Optional, Sequence, TypedDict
import networkx  # type: ignore

from emcie.server.core.common import ItemNotFoundError, UniqueId, generate_id
from emcie.server.core.guidelines import GuidelineId
from emcie.server.core.persistence.common import ObjectId
from emcie.server.core.persistence.document_database import (
    DocumentDatabase,
)

GuidelineConnectionId = NewType("GuidelineConnectionId", str)


class ConnectionKind(Enum):
    ENTAILS = auto()
    SUGGESTS = auto()


@dataclass(frozen=True)
class GuidelineConnection:
    id: GuidelineConnectionId
    creation_utc: datetime
    source: GuidelineId
    target: GuidelineId
    kind: ConnectionKind


class GuidelineConnectionStore(ABC):
    @abstractmethod
    async def update_connection(
        self,
        source: GuidelineId,
        target: GuidelineId,
        kind: ConnectionKind,
    ) -> GuidelineConnection: ...

    @abstractmethod
    async def delete_connection(
        self,
        id: GuidelineConnectionId,
    ) -> None: ...

    @abstractmethod
    async def list_connections(
        self,
        indirect: bool,
        source: Optional[GuidelineId] = None,
        target: Optional[GuidelineId] = None,
    ) -> Sequence[GuidelineConnection]: ...


class GuidelineConnectionDocument(TypedDict, total=False):
    id: ObjectId
    creation_utc: str
    source: GuidelineId
    target: GuidelineId
    kind: str


def _serialize_guideline_connection(
    guideline_connection: GuidelineConnection,
) -> GuidelineConnectionDocument:
    return GuidelineConnectionDocument(
        id=ObjectId(guideline_connection.id),
        creation_utc=guideline_connection.creation_utc.isoformat(),
        source=guideline_connection.source,
        target=guideline_connection.target,
        kind=guideline_connection.kind.name,
    )


def _deserialize_guideline_connection_documet(
    guideline_connection_document: GuidelineConnectionDocument,
) -> GuidelineConnection:
    return GuidelineConnection(
        id=GuidelineConnectionId(guideline_connection_document["id"]),
        creation_utc=datetime.fromisoformat(guideline_connection_document["creation_utc"]),
        source=guideline_connection_document["source"],
        target=guideline_connection_document["target"],
        kind=ConnectionKind[guideline_connection_document["kind"]],
    )


class GuidelineConnectionDocumentStore(GuidelineConnectionStore):
    def __init__(self, database: DocumentDatabase) -> None:
        self._collection = database.get_or_create_collection(
            name="guideline_connections",
            schema=GuidelineConnectionDocument,
        )
        self._graph: networkx.DiGraph | None = None

    async def _get_graph(self) -> networkx.DiGraph:
        if not self._graph:
            g = networkx.DiGraph()

            connections = [
                _deserialize_guideline_connection_documet(d)
                for d in await self._collection.find(filters={})
            ]

            nodes = set()
            edges = list()

            for c in connections:
                nodes.add(c.source)
                nodes.add(c.target)
                edges.append(
                    (
                        c.source,
                        c.target,
                        {
                            "kind": c.kind,
                            "id": c.id,
                        },
                    )
                )

            g.update(edges=edges, nodes=nodes)

            self._graph = g

        return self._graph

    async def update_connection(
        self,
        source: GuidelineId,
        target: GuidelineId,
        kind: ConnectionKind,
        creation_utc: Optional[datetime] = None,
    ) -> GuidelineConnection:
        creation_utc = creation_utc or datetime.now(timezone.utc)

        guideline_connection = GuidelineConnection(
            id=GuidelineConnectionId(generate_id()),
            creation_utc=creation_utc,
            source=source,
            target=target,
            kind=kind,
        )

        result = await self._collection.update_one(
            filters={"source": {"$eq": source}, "target": {"$eq": target}},
            updated_document=_serialize_guideline_connection(guideline_connection),
            upsert=True,
        )

        assert result.updated_document

        graph = await self._get_graph()

        graph.add_node(source)
        graph.add_node(target)

        graph.add_edge(
            source,
            target,
            kind=kind,
            id=guideline_connection.id,
        )

        return guideline_connection

    async def delete_connection(
        self,
        id: GuidelineConnectionId,
    ) -> None:
        connection_document = await self._collection.find_one(filters={"id": {"$eq": id}})

        if not connection_document:
            raise ItemNotFoundError(item_id=UniqueId(id))

        connection = _deserialize_guideline_connection_documet(connection_document)

        (await self._get_graph()).remove_edge(connection.source, connection.target)

        await self._collection.delete_one(filters={"id": {"$eq": id}})

    async def list_connections(
        self,
        indirect: bool,
        source: Optional[GuidelineId] = None,
        target: Optional[GuidelineId] = None,
    ) -> Sequence[GuidelineConnection]:
        assert (source or target) and not (source and target)

        async def get_node_connections(
            source: GuidelineId,
            reversed_graph: bool = False,
        ) -> Sequence[GuidelineConnection]:
            if not graph.has_node(source):
                return []

            _graph = graph.reverse() if reversed_graph else graph

            if indirect:
                descendant_edges = networkx.bfs_edges(_graph, source)
                connections = []

                for edge_source, edge_target in descendant_edges:
                    edge_data = _graph.get_edge_data(edge_source, edge_target)

                    connection_document = await self._collection.find_one(
                        filters={"id": {"$eq": edge_data["id"]}},
                    )

                    if not connection_document:
                        raise ItemNotFoundError(item_id=UniqueId(edge_data["id"]))

                    connections.append(
                        _deserialize_guideline_connection_documet(connection_document)
                    )

                return connections

            else:
                successors = _graph.succ[source]
                connections = []

                for source, data in successors.items():
                    connection_document = await self._collection.find_one(
                        filters={"id": {"$eq": data["id"]}},
                    )

                    if not connection_document:
                        raise ItemNotFoundError(item_id=UniqueId(data["id"]))

                    connections.append(
                        _deserialize_guideline_connection_documet(connection_document)
                    )

                return connections

        graph = await self._get_graph()

        if source:
            connections = await get_node_connections(source)
        elif target:
            connections = await get_node_connections(target, reversed_graph=True)

        return connections
