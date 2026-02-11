import traceback
from logging import Logger
from typing import List
from html2text import html2text
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from langchain_core.documents import Document
from langchain_core.runnables import Runnable
from web.langchain_confluence.client import ConfluenceApiClient
from web.langchain_confluence.repo import PGVectorRepo
from web.langchain_confluence.util import split_markdown_tables

class IngestService:
    """    
    Since
    -----
    0.0.1
    """

    def __init__(self, confluence_client: ConfluenceApiClient, vectorstore_repo: PGVectorRepo, summaries_langgraph: Runnable, logger: Logger):
        """
        Args:
            confluence_client (ConfluenceApiClient): The asyncio confluence client used for extracting confluence page
            vectorstore_repo (PGVectorRepo): The repository holding the vector embedding
            summaries_langgraph (Runnable): 
            logger: The shared logger

        Since
        -----
        0.0.1 (Updated at 0.0.7)
        """
        self._confluence_client = confluence_client
        self._vectorstore_repo = vectorstore_repo
        self._summaries_langgraph = summaries_langgraph
        self._logger = logger
        self._ingest_spaces = []

    def add_ingest_space(self, space: str):
        """
        Add the confluence space that need to be ingest periodically

        Args:
            space: The confluence space name

        Since
        -----
        0.0.1
        """
        self._ingest_spaces.append(space)

    async def reingest(self):
        """
        Since
        -----
        0.0.1
        """
        for space in self._ingest_spaces:
            await self.ingest(space, False, self._summaries_langgraph)

    async def ingest(self, space: str, gen_summary: bool, summaries_runnable: Runnable):
        """
        Args:

        Since
        ----- 
        0.0.1 NOT STABLE (parameter argument will change)
        """
        docs = []
        properties = await self._confluence_client.aget_all_page_properties(space)
        self._logger.info(f"{'INGRESS':15} INGEST <space: {space}, collection_name: {self._vectorstore_repo.collection_name} total_page:{len(properties)}>")

        # Use MarkdownHeaderTextSplitter for heading-based splitting
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2")
        ]

        structural_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on, strip_headers=False)

        semantic_splitter = SemanticChunker(
            embeddings=self._vectorstore_repo._pg_vector.embeddings,
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=95,
            number_of_chunks=3
        )

        recusive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=4096,
            chunk_overlap=20,
            length_function=len,
            is_separator_regex=False,
        )

        for page_id, title, last_modified in properties:
            try:
                # Build the full page URL from the configured Confluence base URL
                confluence_base = self._confluence_client._base_url.rstrip("/")
                full_url = f"{confluence_base}/pages/viewpage.action?pageId={page_id}"        
                # TRY GETTING if there are any existing chunked documents in the vectorstore by searching if the URL matched
                should_skip = False
                existing_docs: List[Document] = await self._vectorstore_repo.aget_by_metadata(metadata={"url": full_url }, limit = 1)
                if len(existing_docs) >= 1:
                    existing_last_modified = existing_docs[0].metadata["last_modified"]
                    if last_modified <= existing_last_modified:
                        self._logger.info(f"{'INGRESS':15} SKIP doc <title {title}, url: {full_url}, last_mod: {last_modified}, mod: {existing_last_modified}")
                        should_skip = True
                    else:
                        # Delete all the embedding with same meta URL
                        self._logger.info(f"{'INGRESS':15} NEEDED <title {title}, url: {full_url}, last_mod: {last_modified}, mod: {existing_last_modified}")
                        self._logger.info(f"{'INGRESS':15} DELETE doc <title {title}, url: {full_url}>")
                        await self._vectorstore_repo.adelete_doc_by_meta(full_url)
                        self._logger.info(f"{'INGRESS':15} DELETED doc <title {title}, url: {full_url}>")
                else:
                    # No existing documents in the vectorstore, need to process
                    pass

                if should_skip:
                    continue
                else:
                    html: str = await self._confluence_client.aget_page_content(page_id)
                    content = html2text(html)

                    # split tables before structural splitting
                    formatted_content = split_markdown_tables(content, rows_per_chunk=5)
                    
                    input_metadata={"page_id": page_id, "title": title, "url": full_url, "last_modified": last_modified}
                    doc = Document(page_content=formatted_content, metadata=input_metadata)

                    self._logger.info(f"{'INGRESS':15} PROCESS <title {title}, url: {full_url}>")
                    all_splits = []
                    #print(doc)
                    # Get text splits from structural splitter
                    split_texts = structural_splitter.split_text(doc.page_content)

                    self._logger.info(f"{'INGRESS':15} SPLIT structural <title {title}, 1 -> {len(split_texts)}>")

                    input_metadata = doc.metadata.copy()
                    for split_text in split_texts:
                        if len(split_text.page_content) > 8000:
                            # Use semantic splitter for large chunks
                            sem_chunk_texts = semantic_splitter.split_text(split_text.page_content)
                            self._logger.info(f"{'INGRESS':15} SPLIT semantic <title {title}, 1 -> {len(sem_chunk_texts)}>")
                            idx = 0
                            for sem_chunk_text in sem_chunk_texts:
                                self._logger.info(f"{'INGRESS':15} SPLIT semantic chunk <idx: {idx}, len:{len(sem_chunk_text)}>")
                                if len(sem_chunk_text) > 8000:
                                    self._logger.info(f"{'INGRESS':15} SPLIT semantic chunk recursively <idx: {idx}, len:{len(sem_chunk_text)}>")
                                    sem_chunk_sub_chunks = recusive_splitter.split_text(sem_chunk_text)
                                    for sem_chunk_sub_chunk in sem_chunk_sub_chunks:
                                        self._logger.info(f"{'INGRESS':15} SPLIT semantic chunk recursively <idx: {idx}, len:{len(sem_chunk_text)} -> len:{len(sem_chunk_sub_chunk)}>")
                                        all_splits.append(
                                            Document(page_content=sem_chunk_sub_chunk, metadata=input_metadata)
                                        )
                                else:
                                    # Create Document with merged metadata
                                    all_splits.append(
                                        Document(page_content=sem_chunk_text, metadata=input_metadata)
                                    )
                                idx += 1
                        else:
                            # Create Document directly for smaller chunks
                            all_splits.append(
                                Document(page_content=split_text.page_content, metadata=input_metadata)
                            )

                        # for chunk in all_splits:
                        #     if len(chunk.page_content) > 8000:
                        #         print(len(chunk.page_content))
                    
                    if len(all_splits) > 0:
                        await self._vectorstore_repo.adelete_doc_by_meta(input_metadata['url'])
                        await self._vectorstore_repo._pg_vector.aadd_documents(all_splits)

                    if gen_summary:
                        self._logger.info(f"{'INGRESS':15} SUMMARIES <title {title}>")
                        summary = await summaries_runnable.ainvoke({ "text": content })
                        self._logger.info(f"{'INGRESS':15} SUMMARIES <title {title}> DONE")
                        docs.append(Document(page_content="", metadata=input_metadata))
                        # TODO: Refactor and get rid of pages
                        await self._vectorstore_repo.aadd_pages(docs)
                        await self._vectorstore_repo.aupdate_summary(summary=summary, doc_id=int(page_id))

                    self._logger.info(f"{'INGRESS':15} PROCESSED <title {title}, url: {full_url} chunk:{len(all_splits)}>")
            except Exception as e:
                self._logger.info(f"{'INGRESS':15} ERROR <title {title}, url: {full_url} err:{e}>")
                print(f"Failed to fetch page {page_id}: {e}")
                traceback.print_exception(e)

        self._logger.info(f"{'INGRESS':15} PROCESSED END <total_page: {len(properties)}>")