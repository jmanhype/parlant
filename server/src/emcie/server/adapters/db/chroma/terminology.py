from datetime import datetime, timezone
from typing import Optional, Sequence, TypedDict

from emcie.server.adapters.db.chroma.database import ChromaDatabase
from emcie.server.core.common import ItemNotFoundError, UniqueId, generate_id
from emcie.server.core.nlp.embedding import Embedder
from emcie.server.core.persistence.common import ObjectId
from emcie.server.core.terminology import Term, TermId, TerminologyStore


class TermDocument(TypedDict, total=False):
    id: ObjectId
    term_set: str
    creation_utc: str
    name: str
    description: str
    synonyms: Optional[str]
    content: str


def _serialize_term(term: Term, term_set: str, content: str) -> TermDocument:
    return TermDocument(
        id=ObjectId(term.id),
        term_set=term_set,
        creation_utc=term.creation_utc.isoformat(),
        name=term.name,
        description=term.description,
        synonyms=(", ").join(term.synonyms) if term.synonyms is not None else "",
        content=content,
    )


def _deserialize_term_documet(term_document: TermDocument) -> Term:
    return Term(
        id=TermId(term_document["id"]),
        creation_utc=datetime.fromisoformat(term_document["creation_utc"]),
        name=term_document["name"],
        description=term_document["description"],
        synonyms=term_document["synonyms"].split(", ") if term_document["synonyms"] else None,
    )


class TerminologyChromaStore(TerminologyStore):
    def __init__(self, chroma_db: ChromaDatabase, embedder_type: type[Embedder]):
        self._collection = chroma_db.get_or_create_collection(
            name="terminology",
            schema=TermDocument,
            embedder_type=embedder_type,
        )
        self._n_results = 20

    async def create_term(
        self,
        term_set: str,
        name: str,
        description: str,
        creation_utc: Optional[datetime] = None,
        synonyms: Optional[Sequence[str]] = None,
    ) -> Term:
        creation_utc = creation_utc or datetime.now(timezone.utc)

        content = self._assemble_term_content(
            name=name,
            description=description,
            synonyms=synonyms,
        )

        term = Term(
            id=TermId(generate_id()),
            creation_utc=creation_utc,
            name=name,
            description=description,
            synonyms=list(synonyms) if synonyms else None,
        )

        await self._collection.insert_one(document=_serialize_term(term, term_set, content))

        return term

    async def update_term(
        self,
        term_set: str,
        name: str,
        description: str,
        synonyms: Sequence[str],
    ) -> Term:
        content = self._assemble_term_content(
            name=name,
            description=description,
            synonyms=synonyms,
        )

        document_to_update = await self._collection.find_one(
            {"$and": [{"term_set": {"$eq": term_set}}, {"name": {"$eq": name}}]}
        )

        if not document_to_update:
            raise ItemNotFoundError(item_id=UniqueId(name))

        update_result = await self._collection.update_one(
            filters={"$and": [{"term_set": {"$eq": term_set}}, {"name": {"$eq": name}}]},
            updated_document={
                "content": content,
                "name": name,
                "description": description,
                "synonyms": ", ".join(synonyms) if synonyms else "",
            },
        )

        assert update_result.updated_document

        return _deserialize_term_documet(term_document=update_result.updated_document)

    async def read_term(
        self,
        term_set: str,
        name: str,
    ) -> Term:
        term_document = await self._collection.find_one(
            filters={"$and": [{"term_set": {"$eq": term_set}}, {"name": {"$eq": name}}]}
        )
        if not term_document:
            raise ItemNotFoundError(item_id=UniqueId(name), message=f"term_set={term_set}")

        return _deserialize_term_documet(term_document=term_document)

    async def list_terms(
        self,
        term_set: str,
    ) -> Sequence[Term]:
        return [
            _deserialize_term_documet(term_document=d)
            for d in await self._collection.find(filters={"term_set": {"$eq": term_set}})
        ]

    async def delete_term(
        self,
        term_set: str,
        name: str,
    ) -> TermId:
        term_document = await self._collection.find_one(
            filters={"$and": [{"term_set": {"$eq": term_set}}, {"name": {"$eq": name}}]}
        )

        if not term_document:
            raise ItemNotFoundError(item_id=UniqueId(name))

        await self._collection.delete_one(
            filters={"$and": [{"term_set": {"$eq": term_set}}, {"name": {"$eq": name}}]}
        )

        return TermId(term_document["id"])

    async def find_relevant_terms(
        self,
        term_set: str,
        query: str,
    ) -> Sequence[Term]:
        return [
            _deserialize_term_documet(d)
            for d in await self._collection.find_similar_documents(
                filters={"term_set": {"$eq": term_set}},
                query=query,
                k=self._n_results,
            )
        ]

    def _assemble_term_content(
        self,
        name: str,
        description: str,
        synonyms: Optional[Sequence[str]],
    ) -> str:
        content = f"{name}"

        if synonyms:
            content += f", {', '.join(synonyms)}"

        content += f": {description}"

        return content
