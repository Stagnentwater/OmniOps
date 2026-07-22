from fastapi import APIRouter, Depends
from pydantic import BaseModel
from database.repositories import MetadataRepository
from dependencies import get_metadata_repo, get_query_orchestrator
from config.settings import get_settings
from graph.neo4j_connection import Neo4jConnectionManager
from graph.neo4j_repository import Neo4jGraphRepository
from vector.qdrant_connection import QdrantConnectionManager
from query.orchestrator import QueryOrchestrator

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])

class KnowledgeStatistics(BaseModel):
    documents: int
    chunks: int
    entities: int
    relationships: int
    graph_nodes: int
    graph_edges: int

@router.get("/statistics", response_model=KnowledgeStatistics)
async def get_statistics(repo: MetadataRepository = Depends(get_metadata_repo)):
    """Fetch aggregated statistics for the knowledge base."""
    settings = get_settings()
    
    # 1. Documents (Postgres)
    documents_count = 0
    conn = repo._connect()
    repo._ensure_tables(conn)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM documents")
            row = cur.fetchone()
            if row:
                documents_count = row[0]
    finally:
        conn.close()

    # 2. Chunks (Qdrant)
    chunks_count = 0
    try:
        q_conn = QdrantConnectionManager(settings.qdrant.host, settings.qdrant.port)
        if q_conn.client.collection_exists("omniops_chunks"):
            collection = q_conn.client.get_collection("omniops_chunks")
            chunks_count = collection.points_count
    except Exception as e:
        print(f"Failed to fetch Qdrant stats: {e}")

    # 3. Graph (Neo4j)
    graph_nodes = 0
    graph_edges = 0
    entities = 0
    relationships = 0
    
    try:
        neo4j_conn = Neo4jConnectionManager(settings.neo4j.uri, settings.neo4j.user, settings.neo4j.password)
        with neo4j_conn.driver.session() as session:
            res_nodes = session.run("MATCH (n) RETURN count(n) as c")
            graph_nodes = res_nodes.single()["c"]
            
            res_edges = session.run("MATCH ()-[r]->() RETURN count(r) as c")
            graph_edges = res_edges.single()["c"]
            
            res_entities = session.run("MATCH (n) WHERE NOT 'Document' IN labels(n) RETURN count(n) as c")
            entities = res_entities.single()["c"]
            
            relationships = graph_edges
    except Exception as e:
        print(f"Failed to fetch Neo4j stats: {e}")

    return KnowledgeStatistics(
        documents=documents_count,
        chunks=chunks_count,
        entities=entities,
        relationships=relationships,
        graph_nodes=graph_nodes,
        graph_edges=graph_edges
    )

@router.get("/graph")
async def get_graph():
    """Fetch the full knowledge graph for visualization."""
    settings = get_settings()
    try:
        neo4j_conn = Neo4jConnectionManager(settings.neo4j.uri, settings.neo4j.user, settings.neo4j.password)
        repo = Neo4jGraphRepository(neo4j_conn)
        return repo.get_full_graph(limit=150)
    except Exception as e:
        print(f"Failed to fetch Neo4j graph: {e}")
        return {"nodes": [], "edges": []}

@router.get("/status")
async def get_system_status(orchestrator: QueryOrchestrator = Depends(get_query_orchestrator)):
    """Fetch the real-time system status and safety risks using the GraphRAG pipeline."""
    try:
        query_text = (
            "Summarize the overall operational status and identify any current safety risks, "
            "critical maintenance issues, or anomalies in the system based on available documents. "
            "Use bullet points for clear readability."
        )
        # We run the query synchronously. It relies on the orchestrator implementation.
        result = orchestrator.answer_query(query_text)
        return {"status": result.answer.answer_text}
    except Exception as e:
        print(f"Failed to generate system status: {e}")
        return {"status": "Unable to assess system status at this time. Please check the logs."}
