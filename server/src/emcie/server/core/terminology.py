from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NewType, Optional, Sequence

from emcie.server.base_models import DefaultBaseModel
from emcie.server.core.common import ItemNotFoundError, UniqueId, generate_id
from emcie.server.core.persistence.chroma_database import ChromaCollection, ChromaDatabase
from emcie.server.core.persistence.common import NoMatchingDocumentsError

TermId = NewType("TermId", str)


@dataclass(frozen=True)
class Term:
    id: TermId
    creation_utc: datetime
    name: str
    description: str
    synonyms: Optional[list[str]]

    def __repr__(self) -> str:
        term_string = f"Name: {self.name}, Description: {self.description}"
        if self.synonyms:
            term_string += f", Sysnonyms: {", ".join(self.synonyms)}"
        return term_string

    def __hash__(self) -> int:
        return hash(self.id)


class TerminologyStore:
    @abstractmethod
    async def create_term(
        self,
        term_set: str,
        name: str,
        description: str,
        creation_utc: Optional[datetime] = None,
        synonyms: Optional[Sequence[str]] = None,
    ) -> Term: ...

    @abstractmethod
    async def update_term(
        self,
        term_set: str,
        name: str,
        description: str,
        synonyms: Sequence[str],
    ) -> Term: ...

    @abstractmethod
    async def read_term(
        self,
        term_set: str,
        name: str,
    ) -> Term: ...

    @abstractmethod
    async def list_terms(
        self,
        term_set: str,
    ) -> Sequence[Term]: ...

    @abstractmethod
    async def delete_term(
        self,
        term_set: str,
        name: str,
    ) -> TermId: ...

    @abstractmethod
    async def find_relevant_terms(
        self,
        term_set: str,
        query: str,
    ) -> Sequence[Term]: ...


class TerminologyChromaStore(TerminologyStore):
    class TermDocument(DefaultBaseModel):
        id: TermId
        term_set: str
        creation_utc: datetime
        name: str
        content: str
        description: str
        synonyms: Optional[str]

    def __init__(
        self,
        chroma_db: ChromaDatabase,
    ):
        try:
            chroma_db.delete_collection("terminology")
        except ValueError:
            pass
        self._collection: ChromaCollection = chroma_db.get_or_create_collection(
            name="terminology",
            schema=self.TermDocument,
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

        term_id = TermId(generate_id())

        document = {
            "id": term_id,
            "term_set": term_set,
            "content": content,
            "name": name,
            "description": description,
            "creation_utc": creation_utc,
            "synonyms": ", ".join(synonyms) if synonyms else "",
        }

        await self._collection.insert_one(document=document)

        return Term(
            id=term_id,
            creation_utc=creation_utc,
            name=name,
            description=description,
            synonyms=list(synonyms) if synonyms else None,
        )

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

        updated_document = {
            "term_set": term_set,
            "content": content,
            "name": name,
            "description": description,
            "synonyms": ", ".join(synonyms) if synonyms else "",
        }

        term_id = await self._collection.update_one(
            filters={"$and": [{"term_set": {"$eq": term_set}}, {"name": {"$eq": name}}]},
            updated_document=updated_document,
        )

        term_doc = await self._collection.find_one({"id": {"$eq": term_id}})

        return Term(
            id=TermId(term_id),
            creation_utc=term_doc["creation_utc"],
            name=name,
            description=description,
            synonyms=list(synonyms) if synonyms else None,
        )

    async def read_term(
        self,
        term_set: str,
        name: str,
    ) -> Term:
        try:
            term_document = await self._collection.find_one(
                filters={"$and": [{"term_set": {"$eq": term_set}}, {"name": {"$eq": name}}]}
            )
        except NoMatchingDocumentsError:
            raise ItemNotFoundError(item_id=UniqueId(name), message=f"term_set={term_set}")

        return Term(
            id=term_document["id"],
            creation_utc=term_document["creation_utc"],
            name=term_document["name"],
            description=term_document["description"],
            synonyms=term_document["synonyms"].split(", "),
        )

    async def list_terms(
        self,
        term_set: str,
    ) -> Sequence[Term]:
        return [
            Term(
                id=d["id"],
                creation_utc=d["creation_utc"],
                name=d["name"],
                description=d["description"],
                synonyms=d["synonyms"].split(", "),
            )
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
            Term(
                id=d["id"],
                creation_utc=d["creation_utc"],
                name=d["name"],
                description=d["description"],
                synonyms=d["synonyms"].split(", "),
            )
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
