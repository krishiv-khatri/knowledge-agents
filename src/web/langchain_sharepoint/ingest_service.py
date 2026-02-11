from datetime import datetime
import traceback
from logging import Logger
from typing import List
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from markitdown import MarkItDown
from web.langchain_confluence.repo import PGVectorRepo
from web.langchain_confluence.util import split_markdown_tables
from web.langchain_sharepoint.client import SharepointApiClient
from web.langchain_sharepoint.schemas import IngestConfig

class IngestService:
    """    
    Since
    -----
    0.0.3
    """

    def __init__(self, sharepoint_client: SharepointApiClient, vectorstore_repo: PGVectorRepo, logger: Logger):
        """
        Args:
            sharepoint_client (SharepointApiClient): The sharepoint API client
            vectorstore_repo: The repository holding the vector embedding
            logger: The shared logger

        Since
        -----
        0.0.7
        """
        self._sharepoint_client = sharepoint_client
        self._vectorstore_repo = vectorstore_repo
        self._logger = logger
        self._ingest_cfgs = []

    def add_ingest_cfg(self, ingest_cfg: IngestConfig):
        """
        Add the ingest configuration that need to be ingest periodically

        Args:
            ingest_cfg (IngestConfig): The ingest configuration

        Since
        -----
        0.0.7
        """
        self._ingest_cfgs.append(ingest_cfg)

    async def reingest(self):
        """
        Since
        -----
        0.0.1
        """
        for ingest_cfg in self._ingest_cfgs:
            await self.ingest(ingest_cfg)

    async def ingest(self, ingest_cfg: IngestConfig, batch_id: str = datetime.now().strftime("%y/%m/%d-%H%m%s")):
        """
        Args:

        Since
        ----- 
        0.0.3
        """
        if self._logger:
            self._logger.info(f"{'INGEST':15} PROCESS START <batch_id: {batch_id}>")
      
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

        md = MarkItDown()

        
        
        if self._logger:
            self._logger.info(f"{'INGEST':15} <url:{ingest_cfg.relative_url}, exclude:{ingest_cfg.exclude_regex[0]}, include:{ingest_cfg.include_regex[0]}>")

        async for prop in self._sharepoint_client.list_folder_contents(ingest_cfg.relative_url, True, ingest_cfg.exclude_regex[0], ingest_cfg.include_regex[0]):
            try:
                page_id = prop['page_id']
                full_url = prop['url']
                last_modified = prop['last_modified']
                title = prop['title']

                # TRY GETTING if there are any existing chunked documents in the vectorstore by searching if the URL matched
                should_skip = False
                existing_docs: List[Document] = await self._vectorstore_repo.aget_by_metadata(metadata={"url": full_url }, limit = 1)

                self._logger.info(f"{'INGEST':15} EXISTING DOC <page_id:{page_id},len:{len(existing_docs)}>")

                if len(existing_docs) >= 1:
                    existing_last_modified = existing_docs[0].metadata["last_modified"]
                    if last_modified <= existing_last_modified:
                        self._logger.info(f"{'INGEST':15} SKIP doc <title {title},url:{full_url}, last_mod:{last_modified}, mod:{existing_last_modified}>")
                        should_skip = True
                    else:
                        # Delete all the embedding with same meta URL
                        self._logger.info(f"{'INGEST':15} DELETE doc <title {title},url:{full_url}>")
                        await self._vectorstore_repo.adelete_doc_by_meta(full_url)
                        self._logger.info(f"{'INGEST':15} DELETED doc <title {title},url:{full_url}>")
                else:
                    # No existing documents in the vectorstore, need to process
                    pass

                if should_skip:
                    continue
                else:
                    local_path = await self._sharepoint_client.aget_page_content(page_id)
                    print(f"Local path: {local_path}")
                    # page_id is the path
                    result = md.convert(source=local_path)
                    # split tables before structural splitting
                    formatted_content = split_markdown_tables(result.text_content, rows_per_chunk=5)
                    
                    input_metadata={"page_id": page_id, "title": title, "url": full_url, "last_modified": last_modified}
                    doc = Document(page_content=formatted_content, metadata=input_metadata)

                    self._logger.info(f"{'INGEST':15} PROCESS <title {title}, url: {full_url}>")
                    all_splits = []
                    #print(doc)
                    # Get text splits from structural splitter
                    split_texts = structural_splitter.split_text(doc.page_content)

                    self._logger.info(f"{'INGEST':15} SPLIT structural <title {title}, 1 -> {len(split_texts)}>")

                    input_metadata = doc.metadata.copy()
                    for split_text in split_texts:
                        if len(split_text.page_content) > 8000:
                            # Use semantic splitter for large chunks
                            sem_chunk_texts = semantic_splitter.split_text(split_text.page_content)
                            self._logger.info(f"{'INGEST':15} SPLIT semantic <title {title}, 1 -> {len(sem_chunk_texts)}>")
                            idx = 0
                            for sem_chunk_text in sem_chunk_texts:                            
                                self._logger.info(f"{'INGEST':15} SPLIT semantic chunk <idx: {idx}, len:{len(sem_chunk_text)}>")
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

                    # Delete all the embedding with same meta URL
                    await self._vectorstore_repo.adelete_doc_by_meta(input_metadata['url'])
                    await self._vectorstore_repo._pg_vector.aadd_documents(all_splits)

                    self._logger.info(f"{'INGEST':15} PROCESSED <title {title}, url: {full_url} chunk:{len(all_splits)}>")
            except Exception as e:
                print(f"Failed to fetch page {page_id}: {e}")
                traceback.print_exception(e)

        if self._logger:
            self._logger.info(f"{'INGEST':15} PROCESSED END <batch_id: {batch_id}>")


