# Examples

This folder contains sample data and configuration examples to help you get started with the system.

## Files

### `sample_test_set.json`

A small example test set demonstrating the format expected by the RAG evaluation tests (`tests/test_rag.py`). Each query includes:

- **query**: The question to ask the RAG system.
- **type**: Either `"specific"` (factual detail) or `"general"` (broader concept).
- **ground_truth**: The expected answer, used as a reference for evaluation metrics.

#### Generating Your Own Test Set

Use `tests/create_test_set.py` to auto-generate test queries from your ingested documents:

```bash
# Make sure OPENAI_API_KEY and OPENAI_API_BASE are set in your .env
python tests/create_test_set.py
```

The script connects to your PostgreSQL vector database, retrieves document chunks, and uses an LLM to generate query/ground-truth pairs. Output is saved to both CSV and JSON formats.

### `sample_agent_config.json`

Example agent configuration for the OpenAI-compatible proxy. Update the `url` field to match your deployment.

## Running Tests with Example Data

1. Copy `sample_test_set.json` to `tests/data/test_set.json` (or point your test config there).
2. Ensure the application is running and connected to your vector database.
3. Run:

```bash
pytest tests/test_rag.py --html=report.html -v
```

## Notes

- Real test data is generated from your own ingested documents and will vary by deployment.
- The sample data above uses generic placeholder content for demonstration purposes.
- See the main [README.md](../README.md) for full setup and usage instructions.
