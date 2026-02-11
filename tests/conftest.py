import logging
import pytest
import torch
import gc
from ruamel.yaml import YAML
from main import app, set_global_config
from fastapi.testclient import TestClient
from dotenv import load_dotenv



load_dotenv()

@pytest.fixture(autouse=True)
def clear_gpu_memory():
    yield  # Run test
    torch.cuda.empty_cache()
    # Manually release lingering tensors (critical for small GPUs)
    for obj in gc.get_objects():
        if torch.is_tensor(obj) and obj.is_cuda:
            del obj
    gc.collect()

@pytest.fixture(scope="session")
def client():
    config_path = "conf/config.yml"

    yaml = YAML(typ="safe")
    with open(config_path, "r") as f:
        config = yaml.load(f)

    set_global_config(config)

    logging.info(config)

    # Persistence Service    
    from web.persistence import route as persistence_route

    from web.openai import models as openai_model 

    from web.openai import route as openai_route
    app.include_router(openai_route.router)

    from web.langchain_confluence import route as confluence_route
    app.include_router(confluence_route.router)
    with TestClient(app,  base_url="http://testserver") as client:
        yield client


def pytest_html_results_table_header(cells):
    """Add custom columns to HTML report header"""
    cells.insert(2, '<th class="ragas">Question</th>')
    cells.insert(3, '<th class="ragas">Response</th>')
    cells.insert(4, '<th class="ragas">Answer Relevancy</th>')
    cells.insert(5, '<th class="ragas">Faithfulness</th>')
    cells.insert(6, '<th class="ragas">Context Precision</th>')
    cells.insert(7, '<th class="ragas">Context Recall</th>')
    cells.insert(8, '<th class="ragas">Context Entity Recall</th>')

def pytest_html_results_table_row(report, cells):
    # Get query and answer from report
    query = getattr(report, "query", None)
    answer = getattr(report, "answer", None)
    # Get scores directly from report
    answer_relevancy = getattr(report, "answer_relevancy", None)
    faithfulness = getattr(report, "faithfulness", None)
    context_precision = getattr(report, "context_precision", None)
    context_recall = getattr(report, "context_recall", None)
    context_entity_recall = getattr(report, "context_entity_recall", None)

    cells.insert(2, f"<td>{format_score(query)}</td>")
    cells.insert(3, f"<td>{format_score(answer)}</td>")
    cells.insert(4, f"<td>{format_score(answer_relevancy)}</td>")
    cells.insert(5, f"<td>{format_score(faithfulness)}</td>")
    cells.insert(6, f"<td>{format_score(context_precision)}</td>")
    cells.insert(7, f"<td>{format_score(context_recall)}</td>")
    cells.insert(8, f"<td>{format_score(context_entity_recall)}</td>")

def format_score(score):
    """Format score for display in HTML"""
    if score is None:
        return "-"
    if isinstance(score, float):
        return f"{score:.2f}"
    return str(score)

# Transfer values from test node to report
@pytest.hookimpl(hookwrapper=True)  # <-- THIS IS ESSENTIAL!
def pytest_runtest_makereport(item, call):
    outcome = yield  # Run the test
    report = outcome.get_result()

    # Transfer custom attributes from test node to report
    for name in ["query", "answer", "answer_relevancy", "faithfulness", "context_precision", "context_recall", "context_entity_recall"]:
        value = getattr(item, name, None)
        if value is not None:
            setattr(report, name, value)
