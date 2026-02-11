#!/usr/bin/env python3
"""
RAG Evaluation Test Query Generator

This script connects to a PostgreSQL database, retrieves document chunks,
processes them using OpenAI-compatible models, and generates test queries
for RAG evaluation. Results are saved to both CSV and JSON formats.

Prerequisites:
    - PostgreSQL database with pgvector and ingested documents
    - OpenAI-compatible LLM endpoint (set OPENAI_API_KEY and OPENAI_API_BASE in .env)
    - Database credentials in .env or environment variables

Usage:
    1. Copy .env.example to .env and fill in your values.
    2. Run: python tests/create_test_set.py
"""

import asyncio
import asyncpg
import csv
import json
import logging
import os
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import JsonOutputParser
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()


@dataclass
class Config:
    """Configuration for database and OpenAI settings.
    
    All sensitive values are loaded from environment variables.
    See .env.example for the full list of required variables.
    """
    # Database settings - loaded from environment
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "knowledge_agents")
    db_user: str = os.getenv("DB_USER", "postgres")
    db_password: str = os.getenv("DB_PASSWORD", "")
    
    # Collection settings - the UUID of the vector collection to generate queries from
    collection_id: str = os.getenv("COLLECTION_ID", "")
    
    # OpenAI settings
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_api_base: str = os.getenv("OPENAI_API_BASE", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "Qwen/Qwen3-32B-AWQ")
    
    # Processing settings
    batch_size: int = 5
    output_file: str = "test_queries.csv"
    json_output_file: str = "tests/data/test_set.json"
    generate_json: bool = True


@dataclass
class DocumentChunk:
    """Data class representing a document chunk from the vector store."""
    id: int
    document: str
    metadata: Dict[str, Any]
    title: str
    collection_id: str


@dataclass
class TestQuery:
    """Data class representing a generated test query."""
    query: str
    type: str  # 'specific' or 'general'
    ground_truth: str


class DatabaseManager:
    """Handles PostgreSQL database operations using asyncpg."""
    
    def __init__(self, config: Config):
        self.config = config
        self.connection: Optional[asyncpg.Connection] = None
    
    async def connect(self) -> None:
        """Establish database connection."""
        try:
            self.connection = await asyncpg.connect(
                host=self.config.db_host,
                port=self.config.db_port,
                database=self.config.db_name,
                user=self.config.db_user,
                password=self.config.db_password
            )
            logger.info("Successfully connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Close database connection."""
        if self.connection:
            await self.connection.close()
            logger.info("Database connection closed")
    
    async def get_document_chunks(self, collection_id: Optional[str] = None, limit: Optional[int] = None) -> List[DocumentChunk]:
        """
        Retrieve document chunks from the langchain_pg_embedding table.
        
        Args:
            collection_id: Optional collection ID to filter by
            limit: Optional limit on number of documents to retrieve
            
        Returns:
            List of DocumentChunk objects
        """
        if not self.connection:
            raise RuntimeError("Database connection not established")
        
        if collection_id:
            query = """
            SELECT id, document, cmetadata, collection_id 
            FROM langchain_pg_embedding 
            WHERE collection_id = $1
            ORDER BY id
            """
            params = [collection_id]
        else:
            query = """
            SELECT id, document, cmetadata, collection_id 
            FROM langchain_pg_embedding 
            ORDER BY id
            """
            params = []
        
        if limit:
            query += f" LIMIT {limit}"
        
        try:
            rows = await self.connection.fetch(query, *params) if params else await self.connection.fetch(query)
                
            chunks = []
            for row in rows:
                metadata = json.loads(row['cmetadata'])
                chunk = DocumentChunk(
                    id=row['id'],
                    document=row['document'],
                    metadata=metadata,
                    title=metadata['title'],
                    collection_id=row['collection_id']
                )
                chunks.append(chunk)
            
            logger.info(f"Retrieved {len(chunks)} document chunks" + (f" for collection {collection_id}" if collection_id else ""))
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to retrieve document chunks: {e}")
            raise


class QueryGenerator:
    """Handles query generation using OpenAI-compatible models."""
    
    def __init__(self, config: Config):
        self.config = config
        self.llm = ChatOpenAI(
            model=config.openai_model,
            api_key=config.openai_api_key,  # type: ignore
            base_url=config.openai_api_base
        )
        
        # Prompt template for generating RAG evaluation queries
        self.prompt_template = ChatPromptTemplate.from_template("""
You are an expert at creating test queries for RAG (Retrieval-Augmented Generation) evaluation.
Given the following batch of document chunks, generate high-quality test queries.

Document chunks:
{documents}

Generate queries in two categories:
1. SPECIFIC queries: Ask about particular facts, details, or specific information mentioned
2. GENERAL queries: Ask about broader concepts, themes, or procedures

For each query, provide:
- The query text
- The type (specific/general)  
- Ground truth: the relevant document content that answers the query

Generate 3-5 queries total, mixing both specific and general types.

Return your response as a JSON array:
[
  {{
    "query": "your query here",
    "type": "general",
    "ground_truth": "the relevant document content"
  }}
]

Only return the JSON array, no additional text.
Be clear about what the queries are asking - refer to document titles or topics, not just "the document".
""")
        
        self.chain = (
            {"documents": RunnablePassthrough()}
            | self.prompt_template
            | self.llm
            | JsonOutputParser()
        )
    
    def generate_queries_for_chunks(self, chunks: List[DocumentChunk]) -> List[TestQuery]:
        """Generate test queries for a batch of document chunks."""
        combined_docs = "\n\n---\n\n".join([
            f"{chunk.title}:\n{chunk.document}" 
            for chunk in chunks
        ])
        
        try:
            result = self.chain.invoke(combined_docs)
            
            if not isinstance(result, list):
                logger.warning(f"Expected list from LLM, got {type(result)}: {result}")
                return []
            
            test_queries = []
            for item in result:
                if isinstance(item, dict):
                    test_query = TestQuery(
                        query=item.get("query", ""),
                        type=item.get("type", "general"),
                        ground_truth=item.get("ground_truth", "")
                    )
                    test_queries.append(test_query)
            
            logger.info(f"Generated {len(test_queries)} test queries for batch")
            return test_queries
            
        except Exception as e:
            logger.error(f"Failed to generate queries: {e}")
            return []


class CSVWriter:
    """Handles writing test queries to CSV file incrementally."""
    
    def __init__(self, output_file: str):
        self.output_file = Path(output_file)
        self.fieldnames = ["query", "type", "ground_truth"]
        self.file_initialized = False
    
    def initialize_file(self) -> None:
        if not self.file_initialized:
            with open(self.output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
                writer.writeheader()
            self.file_initialized = True
    
    def append_queries(self, queries: List[TestQuery]) -> None:
        if not queries:
            return
        if not self.file_initialized:
            self.initialize_file()
        
        with open(self.output_file, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
            for query in queries:
                writer.writerow({
                    "query": query.query,
                    "type": query.type,
                    "ground_truth": query.ground_truth
                })
        logger.info(f"Appended {len(queries)} queries to {self.output_file}")


class JSONWriter:
    """Handles writing test queries to JSON file."""
    
    def __init__(self, json_output_file: str):
        self.json_output_file = Path(json_output_file)
        self.all_queries: List[Dict[str, Any]] = []
    
    def append_queries_to_memory(self, queries: List[TestQuery]) -> None:
        for query in queries:
            if query.query and query.query.strip():
                self.all_queries.append({
                    "query": query.query,
                    "type": query.type,
                    "ground_truth": query.ground_truth,
                    "timestamp": datetime.now().isoformat()
                })
        logger.info(f"Added {len(queries)} queries to memory (total: {len(self.all_queries)})")

    async def write_final_json(self) -> None:
        """Write all queries to final consolidated JSON file."""
        if not self.all_queries:
            logger.warning("No queries to write to JSON file")
            return
        
        query_types = {}
        for query in self.all_queries:
            qt = query.get("type", "unknown")
            query_types[qt] = query_types.get(qt, 0) + 1
        
        consolidated_data = {
            "metadata": {
                "total_queries": len(self.all_queries),
                "generation_timestamp": datetime.now().isoformat(),
                "query_types": query_types,
                "file_format_version": "1.0"
            },
            "summary": {
                "total_queries": len(self.all_queries),
                "specific_queries": query_types.get("specific", 0),
                "general_queries": query_types.get("general", 0),
                "other_queries": sum(c for t, c in query_types.items() if t not in ["specific", "general"])
            },
            "queries": self.all_queries
        }
        
        self.json_output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.json_output_file, 'w', encoding='utf-8') as f:
            json.dump(consolidated_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Wrote {len(self.all_queries)} queries to {self.json_output_file}")


class RAGTestGenerator:
    """Main orchestrator for the RAG test query generation process."""
    
    def __init__(self, config: Config):
        self.config = config
        self.db_manager = DatabaseManager(config)
        self.query_generator = QueryGenerator(config)
        self.csv_writer = CSVWriter(config.output_file)
        self.json_writer = JSONWriter(config.json_output_file)
    
    async def process_documents_in_batches(self, chunks: List[DocumentChunk]) -> int:
        """Process document chunks in batches. Returns total queries generated."""
        self.csv_writer.initialize_file()
        total_queries = 0
        batch_size = self.config.batch_size
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            batch_num = i // batch_size + 1
            logger.info(f"Processing batch {batch_num} ({len(batch)} chunks)")
            
            batch_queries = await asyncio.to_thread(
                self.query_generator.generate_queries_for_chunks, batch
            )
            
            if batch_queries:
                self.csv_writer.append_queries(batch_queries)
                self.json_writer.append_queries_to_memory(batch_queries)
                total_queries += len(batch_queries)
            else:
                logger.warning(f"Batch {batch_num}: No queries generated")
            
            # Write incremental JSON after each batch
            await self.json_writer.write_final_json()
            
            # Small delay to be respectful to the API
            await asyncio.sleep(1)
    
        return total_queries
    
    async def run(self) -> None:
        """Main execution method."""
        logger.info("Starting RAG test query generation process")
        
        try:
            await self.db_manager.connect()
            chunks = await self.db_manager.get_document_chunks(self.config.collection_id)
            
            if not chunks:
                logger.warning(f"No document chunks found for collection_id: {self.config.collection_id}")
                return
            
            total_queries = await self.process_documents_in_batches(chunks)
            
            if total_queries == 0:
                logger.warning("No test queries were generated")
                return
            
            logger.info(f"Completed. Generated {total_queries} test queries.")
            logger.info(f"CSV output: {self.config.output_file}")
            logger.info(f"JSON output: {self.config.json_output_file}")
            
        except Exception as e:
            logger.error(f"Process failed: {e}")
            if self.json_writer.all_queries:
                logger.info("Attempting to write partial results...")
                await self.json_writer.write_final_json()
            raise
        
        finally:
            await self.db_manager.disconnect()


async def main():
    """Main entry point."""
    config = Config()
    
    if not config.collection_id:
        logger.error("COLLECTION_ID environment variable is required. Set it to the UUID of your vector collection.")
        return
    
    generator = RAGTestGenerator(config)
    await generator.run()


if __name__ == "__main__":
    print("RAG Test Query Generator")
    print("=" * 40)
    print("Required environment variables:")
    print("  OPENAI_API_KEY, OPENAI_API_BASE, DB_HOST, DB_PORT,")
    print("  DB_NAME, DB_USER, DB_PASSWORD, COLLECTION_ID")
    print()
    print("See .env.example for a complete template.")
    print()
    asyncio.run(main())
