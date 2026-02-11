from typing import Dict
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from web.dependencies import register_system_initial_hook
from web.langchain_sharepoint.client import SharepointApiClient
from web.langchain_sharepoint.dependencies import set_global_ingest_service, set_global_sharepoint_client, set_global_vector_store, logger
from web.langchain_sharepoint.ingest_service import IngestService
from web.langchain_confluence.repo import PGVectorRepo
from web.langchain_sharepoint.schemas import IngestConfigCollection
from web.persistence.dependencies import require_sql_engine_async_url, require_sql_engine_raw_uri
from office365.runtime.auth.user_credential import UserCredential
from office365.runtime.auth.client_credential import ClientCredential

async def init_hook(config: Dict):
    """
    Initialize hook for sharepoint langchain plugin. (Part of langchain)

    1) The backed vector store will be initialized
    2) The sharepoint API client will be initialized
    3) The ingest service will be initialized
    
    Since
    ------
    0.0.3
    """
    logger.info(f"{'INIT START':15} Langchain sharepoint hook")

    config_embedding: Dict = config.get("embeddings")
    embeddings = OpenAIEmbeddings(
        model=config_embedding.get("model"), 
        base_url=config_embedding.get("base_url"), 
        api_key=config_embedding.get("api_key"), 
        tiktoken_enabled=False,
        tiktoken_model_name=config_embedding.get("model"),
        encoding_format="float")  # Explicitly set to float

    config_sharepoint: Dict = config.get("sharepoint")
    input_collection_name = config_sharepoint.get("vectorstore_collection_name")
    async_db_connection_url = require_sql_engine_async_url()
    async_db_connection_raw_url = require_sql_engine_raw_uri()

    logger.info(f"{'INIT':15} Vector store URI: {async_db_connection_url}")
    logger.info(f"{'INIT':15} Vector store Collection: {input_collection_name}")
    
    vector_store = PGVector(
        embeddings=embeddings,
        # PG database related configuration START
        connection=async_db_connection_url,
        async_mode=True,
        # Note: The async PGVector does not work when 'create_extension' is set to True
        create_extension=False,
        collection_name=input_collection_name
        # PG database related configuration END
    )
    set_global_vector_store(vector_store)

    logger.info(f"{'INIT':15} Sharepoint API Client: <base_url: {config_sharepoint['url']}, client_id: ***, client_secret: ***>")
    
    method = config_sharepoint.get('credential_method', 'user')
    if method == 'user':
        sharepoint_client = SharepointApiClient(config_sharepoint['url'], UserCredential(config_sharepoint['email'], config_sharepoint['password']))
    else:
        sharepoint_client = SharepointApiClient(config_sharepoint['url'], ClientCredential(config_sharepoint['client_id'], config_sharepoint['client_secret']))

    sharepoint_client.logger = logger
    set_global_sharepoint_client(sharepoint_client)

    ingest_cfgs = IngestConfigCollection(config_sharepoint['ingest'])
    authentication_result = await sharepoint_client.test_oauth()
    logger.info(f"{'INIT':15} Sharepoint test authentication <result: {authentication_result}>")
    # Initialize Ingest service
    logger.info(f"{'INIT':15} Sharepoint Ingest Service")
    ingest_service = IngestService(sharepoint_client, PGVectorRepo(vector_store, async_db_connection_raw_url), logger)
    for ingest_cfg in ingest_cfgs.root:
        #print(ingest_cfg)
        ingest_service.add_ingest_cfg(ingest_cfg)
    set_global_ingest_service(ingest_service)

    logger.info(f"{'INIT':15} Sharepoint Ingest Service DONE")
    logger.info(f"{'INIT END':15} Langchain sharepoint hook")
   
register_system_initial_hook(init_hook)
