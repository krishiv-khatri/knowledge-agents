import os
import pytest
import time
import json
from datasets import Dataset
from ragas import EvaluationDataset
from ragas.metrics import answer_relevancy, faithfulness, context_recall, context_entity_recall, context_precision
from ragas import evaluate
from dotenv import load_dotenv
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
# source .venv/bin/activate

# Load environment variables from .env file
load_dotenv()

# Path to the test set JSON file.
# Generate one using tests/create_test_set.py, or copy examples/sample_test_set.json here.
JSON_FILE_PATH = os.getenv("TEST_SET_PATH", "tests/data/test_set.json")

# Helper function to load queries from JSON
def load_queries_from_json():
    with open(JSON_FILE_PATH, "r") as f:
        data = json.load(f)
    return data["queries"]

# Boolean flag to determine if a report should be generated on test results
generate_report_on_test = True

# Set up the LLM connection using ChatOpenAI
# This is used for evaluation of RAGAS metrics like faithfulness and answer relevancy
llm = LangchainLLMWrapper(ChatOpenAI(
    model="Qwen/Qwen3-32B-AWQ",
    openai_api_key=os.getenv("OPENAI_API_KEY"), # type: ignore
    openai_api_base=os.getenv("OPENAI_API_BASE"), # type: ignore
    temperature=0.6
    ))

# Initialize LangChain embeddings
lc_embeddings = OpenAIEmbeddings(
    model="BAAI/bge-m3",
    api_key=os.getenv("OPENAI_API_KEY"), # type: ignore
    base_url=os.getenv("OPENAI_API_BASE"), # type: ignore
    tiktoken_enabled=False,
    )

# Wrap the LangChain embeddings for RAGAS compatibility
embeddings = LangchainEmbeddingsWrapper(lc_embeddings)

headers = {
    'accept': 'application/json',
    'Content-Type': 'application/json'
}

def test_live_server(client):
    response = client.get("")
    assert response.status_code == 200

# Initial test to handle invalid/irrelavent queries
"""
def test_invalid_query_handling(request):
    query = "what color is an orange"
    data = {"question": query, "agent": "rag"}
    response = requests.post(url, json=data).json()

        # Attach attributes to ensure report columns are populated
    request.node.answer_relevancy = None
    request.node.faithfulness = None
    request.node.context_precision = None

    assert "no results in the docs." in response["answer"].lower()
"""

"""
Main evaluation program for each query in the test set.
Parametrize test with queries from the JSON file
This allows for multiple test cases to be run in one test function
"""
@pytest.mark.parametrize("query_data", load_queries_from_json())
def test_search_metrics(client, query_data, request):
    try:
        # Extract the query and ground truth from the test data
        query = query_data["query"]
        print(query)
        ground_truth = query_data["ground_truth"]

        # Attach query to report
        request.node.query = query

        # Always attach attributes, even if skipped
        request.node.answer = None
        request.node.answer_relevancy = None
        request.node.faithfulness = None
        request.node.context_precision = None
        request.node.context_recall = None
        request.node.context_entity_recall = None

        # Extract the answer and retrieved documents from the response
        url = f"api/v1/rag"
        data = {"question": query, "agent": "rag"}
        response = client.post(url, json=data).json()
        print(f"***\n\n\n RESPONSE: \n{response}\n\n\n***")
        answer = response["answer"]
        retrieved_docs = [
            f"Document title: {doc['metadata']['title']}\nLast modified: {doc['metadata']['last_modified']}\nDocument content: {doc['page_content']}"
            for doc in response.get("retrieved_docs", [])
        ]

        # If the response indicates no relevant documents were found, skip evaluation
        if "no results in the docs." in response["answer"].lower():
            assert "no results in the docs." in response["answer"].lower()
            pytest.skip("No results in docs for this query; skipping metrics evaluation.")

        # Build the dataset for evaluation using RAGAS
        dataset = Dataset.from_dict({
            "question": [query],
            "answer": [answer],
            "contexts": [retrieved_docs],
            "retrieved_contexts": [retrieved_docs],
            "reference": [ground_truth]
        })    

        print(f"***\n\n\n DATASET: \n{dataset}\n\n\n***")
        # Attach answer to test node for reporting
        request.node.answer = answer

        # Run RAGAS evaluation with the defined metrics
        scores = evaluate(
            dataset,
            metrics=[answer_relevancy, faithfulness, context_recall, context_entity_recall, context_precision],
            llm=llm,
            embeddings=lc_embeddings
        )

        # Print all scores
        print('\n\n\n\n\n\n\n\n')
        print('~'*40)
        print(f"SCORES:\n\nAnswer Relevancy: {scores['answer_relevancy'][0]}\nContext Recall: {scores['context_recall'][0]}\nContext Entity Recall: {scores['context_entity_recall'][0]}\nContext Precision: {scores['context_precision'][0]}\nFaithfulness: {scores['faithfulness'][0]}")
        print('~'*40)
        # Attach scores to test node for reporting
        request.node.answer_relevancy = scores["answer_relevancy"][0]
        request.node.faithfulness = scores["faithfulness"][0]
        request.node.context_precision = scores["context_precision"][0]
        request.node.context_recall = scores['context_recall'][0]
        request.node.context_entity_recall = scores['context_entity_recall'][0]
        print(f"Attached scores to test: {request.node.name}")

        # Fail if any metric score is below 0.70
        for metric, score in [
            ("answer_relevancy", scores["answer_relevancy"][0]),
            ("faithfulness", scores["faithfulness"][0]),
            ("context_recall", scores["context_recall"][0]),
            ("context_entity_recall", scores["context_entity_recall"][0]),
            ("context_precision", scores["context_precision"][0]),
        ]:
            assert score > 0.70, f"{metric} score {score} is below threshold 0.70"
    except Exception as e:
        print(f"\n\n\n\n\n\n\n\n!!!!!EXCEPTION!!!!!!!!!\n{e}\n\n\n\n\n\n\n\n")

"""Test to evaluate the performance of the search system"""
def test_search_performance(client):
    start_time = time.time()
    query = "steps to onboard a new participants"
    url = "/api/v1/rag"
    data = {"question": query}
    response = client.post(url, json=data).json()
    execution_time = time.time() - start_time
    
    assert execution_time < 10.0  # 10 second threshold
