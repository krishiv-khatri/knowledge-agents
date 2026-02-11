from typing import Any, Dict, List
import asyncpg
import json
from langchain_postgres import PGVector
from langchain_core.documents import Document
from sqlalchemy import Sequence, select
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, func

class PGVectorRepo:
    """
    A wrapper for `langchain_postgres` repo to provide some extra functionality

    Since
    --------
    0.0.1
    """
    def __init__(self, pg_vector: PGVector, url: str):
        """
        Since
        --------
        0.0.1
        """
        self._pg_vector = pg_vector
        self.url = url

    @property
    def collection_name(self):
        """
        Since
        --------
        0.0.10
        """
        return self._pg_vector.collection_name

    def delete_doc_by_meta(self, page_id: str):
        """
        Delete a set of documents by the given parameter

        Since
        --------
        0.0.1
        """
        # This method is allowed to use ALL private variable in pg_vector 
        with Session(self._pg_vector._engine) as session:
            # See langchain_postgres/vectorstore.py#_get_embedding_collection_store for understanding the schema of 'EmbeddingStore'
            table = self._pg_vector.EmbeddingStore
            stmt = delete(table)
            # https://neon.tech/postgresql/postgresql-json-functions/postgresql-jsonb_extract_path_text
            #stmt = stmt.where(func.jsonb_extract_path_text(table.cmetadata, 'url') == page_id)
            stmt = stmt.where(func.jsonb_extract_path_text(table.cmetadata, 'url') == page_id)
            session.execute(stmt)
            session.commit()
       
    async def adelete_doc_by_meta(self, page_id: str):
        """
        Asynchronously delete a set of documents by the given parameter

        Since
        --------
        0.0.1
        """
        # By design, PGVectorRepo is ALLOWED to access all private variable of PGVector as it's main duty
        # is to provide some handy method for other to use
        async with AsyncSession(self._pg_vector._async_engine) as session:
            await self._pg_vector.__apost_init__()
            # See langchain_postgres/vectorstore.py#_get_embedding_collection_store for understanding the schema of 'EmbeddingStore'
            table = self._pg_vector.EmbeddingStore
            stmt = delete(table)
            # https://neon.tech/postgresql/postgresql-json-functions/postgresql-jsonb_extract_path_text
            #stmt = stmt.where(func.jsonb_extract_path_text(table.cmetadata, 'url') == page_id)
            stmt = stmt.where(func.jsonb_extract_path_text(table.cmetadata, 'url') == page_id)
            await session.execute(stmt)
            await session.commit()

    async def aget_by_metadata(self, metadata: Dict, limit = 100) -> List[Document]:
        """
        Asynchronously get the documents WHERE documents metadata matched with the data input
        by `metadata`.

        Since
        --------
        0.0.1
        """
        docs = []
        async with AsyncSession(self._pg_vector._async_engine) as session:
            await self._pg_vector.__apost_init__()
            collection = await self._pg_vector.aget_collection(session)
            filter_by = [self._pg_vector.EmbeddingStore.collection_id == collection.uuid]
            # See langchain_postgres/vectorstore.py#_get_embedding_collection_store for understanding the schema of 'EmbeddingStore'
            table = self._pg_vector.EmbeddingStore
            stmt = select(table).filter(*filter_by)
            for key, value in metadata.items():
                stmt = stmt.where(func.jsonb_extract_path_text(table.cmetadata, key) == value)

            results: Sequence[Any] = (await session.execute(stmt)).scalars().all()

            for result in results:
                docs.append(
                    Document(
                        id=str(result.id),
                        page_content=result.document,
                        metadata=result.cmetadata,
                    )
                )
                if len(docs) >= limit:
                    break
        return docs
    
    async def aget_pages_summary_by_ids(self, doc_ids: List[str]) -> List[Document]:
        """
        Get the pages summary in batch by given a set of confluence page IDs.

        Since
        --------
        0.0.1
        """
        result_docs: List[Document] = []
        conn = await asyncpg.connect(self.url)
        try:
            result_set = await conn.fetch("SELECT id, metadata, summary FROM documents WHERE id = ANY($1)", doc_ids)
            for row in result_set:
                # print(row)
                # print(row['id'])
                # print(row['metadata'])
                # print(row['summary'])
                summary = row['summary']
                if summary:
                    result_docs.append(Document(id=row['id'], metadata=json.loads(row['metadata']), page_content=summary))                    
        finally:
            if conn:
                await conn.close()
        return result_docs

    async def aget_page_by_id(self, doc_id):
        """
        Since
        --------
        0.0.1
        """
        conn = await asyncpg.connect(self.url)
        row = await conn.fetchrow('SELECT * FROM documents WHERE id = $1', int(doc_id))
        await conn.close()
        return row

    async def aadd_pages(self, documents: List[Document]):
        """
        Since
        --------
        0.0.1
        """
        conn = await asyncpg.connect(self.url)
        for doc in documents:
             # Extract content and metadata from the LangChain Document
            content = doc.page_content
            metadata = doc.metadata
    
             # Use a unique identifier from metadata, 'id'
            doc_id = metadata.get('page_id') if metadata else None
            if doc_id is None:
                raise ValueError("Document metadata must include an 'id' key for identification")
    
            # insert if not exists, else update
            await conn.execute('''
                INSERT INTO documents (id, content, metadata) 
                VALUES ($1, $2, $3)
                ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content, metadata = EXCLUDED.metadata
            ''', int(doc_id), content, json.dumps(metadata))
    
        await conn.close()

    async def aupdate_summary(self, summary, doc_id):
        """
        Since
        --------
        0.0.1
        """
        conn = await asyncpg.connect(self.url)

        # Store the summary in the new column
        await conn.execute(
           "UPDATE documents SET summary = $1 WHERE id = $2",
                summary, doc_id
            )
        #print(f"Summarized doc {doc_id}")
        await conn.close()
