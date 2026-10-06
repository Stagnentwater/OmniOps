# Backend Testing

Run the backend's dependency-free unit suite from the `backend/` directory:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

The suite uses in-memory graph, vector, embedding, and LLM test doubles. It does not require PostgreSQL, Neo4j, Qdrant, Redis, OpenRouter, or Ollama to be running.

Run the focused conversation-remembrance tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_generation tests.test_query_orchestrator
```
