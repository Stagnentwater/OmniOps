# OmniOps Deployment Guide

This document explains how to deploy OmniOps in two scenarios: locally using Docker Compose, and to production using Managed Cloud Services (Render, Vercel, Neon, Neo4j Aura, Qdrant Cloud, Upstash).

## Deployment Model (ET AI Hackathon)

For the hackathon, OmniOps uses a **single-service deployment**: the RQ background worker runs embedded inside the FastAPI process as a daemon thread. This is controlled by the `EMBED_WORKER` environment variable.

| `EMBED_WORKER` | Behavior |
|---|---|
| `true` (default) | The FastAPI process starts an RQ worker in a background thread on startup. No separate worker service is needed. |
| `false` | The FastAPI process does NOT start a worker. You must run `python worker.py` (or a separate worker service) to process ingestion jobs. |

> [!NOTE]
> **Why embedded?** This eliminates the need for a separate worker deployment on Render or Heroku, reducing the hackathon stack to a single web service while preserving the full Redis/RQ architecture.

> [!IMPORTANT]
> **Production Recommendation:** For production workloads with high ingestion volume, set `EMBED_WORKER=false` and deploy a separate worker service. The standalone worker definitions are preserved in `docker-compose.yml` (under the `standalone-worker` profile), `render.yaml`, and `heroku.yml`.

---

## 1. Local Docker Deployment

OmniOps is pre-configured to run out-of-the-box using Docker Compose. This starts all required databases (PostgreSQL, Neo4j, Qdrant, Redis) and the FastAPI application with an embedded worker.

### Steps
1. Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   ```
2. You only need to populate `OPENROUTER_API_KEY` in `.env` for local testing. The rest of the variables will fall back to local Docker hostnames (e.g., `postgres`, `redis`).
3. Start the stack:
   ```bash
   docker compose up -d
   ```
4. Access the API at `http://localhost:8000/docs`.

The API container automatically starts the embedded RQ worker. No separate worker container is needed.

### Using a Standalone Worker (Optional)

To run the worker as a separate container (e.g., for production-like testing):
1. Set `EMBED_WORKER=false` in the API service environment (in `docker-compose.yml`).
2. Start with the `standalone-worker` profile:
   ```bash
   docker compose --profile standalone-worker up -d
   ```

---

## 2. Managed Cloud Deployment

For the ET AI Hackathon (or production deployments), you can deploy OmniOps using a fully managed free-tier stack. 

### Architecture
- **Frontend**: Vercel
- **Backend API (with embedded worker)**: Render
- **PostgreSQL**: Neon
- **Neo4j**: AuraDB Free
- **Qdrant**: Qdrant Cloud
- **Redis**: Upstash Redis

### Required Environment Variables
To deploy on Managed Cloud services, you must provide the following environment variables (which will override local defaults):
* `DATABASE_URL`: Connection string from Neon (e.g., `postgresql://...`). SSL is handled automatically.
* `NEO4J_URI`: Connection string from Aura (e.g., `neo4j+s://...`).
* `NEO4J_USERNAME`: Usually `neo4j`.
* `NEO4J_PASSWORD`: Your Aura password.
* `QDRANT_URL`: The URL to your Qdrant Cloud cluster.
* `QDRANT_API_KEY`: Qdrant Cloud API key.
* `REDIS_URL`: The rediss:// URL from Upstash.
* `OPENROUTER_API_KEY`: Your OpenRouter LLM API key.
* `EMBED_WORKER`: Set to `true` (default) for single-service deployment.

### Render Deployment (Backend API)
We use a `render.yaml` Blueprint file to define the backend topology.

1. Connect your GitHub repository to Render.
2. In Render, select **Blueprints** -> **New Blueprint Instance**.
3. Select this repository. Render will automatically detect the `render.yaml` file.
4. Render will prompt you for the Environment Variables (like `DATABASE_URL`, `NEO4J_URI`, etc.) because they are marked `sync: false` in the blueprint. Fill them in using the values from your Managed Services.
5. Render will provision the `omniops-api` Web Service. The embedded worker starts automatically.

> [!NOTE]
> The `render.yaml` file also contains a deprecated `omniops-worker` service definition. For the hackathon, disable this service in Render — the embedded worker in the API handles job processing. For production, you can re-enable it and set `EMBED_WORKER=false` on the API.

### Vercel Deployment (Frontend)
1. Go to [Vercel](https://vercel.com).
2. Click **Add New** -> **Project**.
3. Import your GitHub repository.
4. Ensure the Framework Preset is set to **Next.js**.
5. Change the Root Directory to `frontend`.
6. Under Environment Variables, add:
   - `NEXT_PUBLIC_API_URL`: The URL of your deployed Render `omniops-api` (e.g., `https://omniops-api.onrender.com`).
7. Click **Deploy**.

---

## Common Troubleshooting

### Connection Failures on Startup
If a managed service fails to connect, the application will no longer crash immediately on startup. Instead, the `/health` endpoint will capture the error.
- Check `https://<your-render-url>/health`.
- The response will show which service (e.g., `neo4j`, `postgres`) failed and provide the underlying connection error string.

### Missing Worker Events
If documents stay in `PENDING` state:
1. Check the API logs for embedded worker output (look for `"Embedded RQ worker started"` at startup).
2. If `EMBED_WORKER=false`, verify a standalone worker is running and connected to the same Redis instance.
3. Verify the `REDIS_URL` matches between the API and any standalone worker.
4. Check worker logs for parsing errors.

### Local Storage Warning
For the hackathon, we are preserving the `STORAGE_BACKEND=local` setting. Because Render containers are ephemeral, files uploaded will disappear after a container restart (approx 15 mins of inactivity). Metadata and Graph data **will persist** because they live in managed databases, but downloading the original file may fail after a restart. This is expected and acceptable for a 5-document demo.

---

## Re-separating the Worker for Production

The embedded worker is a hackathon convenience. To restore the production two-service architecture:

1. Set `EMBED_WORKER=false` on the API service.
2. Deploy the standalone worker using one of:
   - **Docker Compose**: `docker compose --profile standalone-worker up -d`
   - **Render**: Enable the `omniops-worker` service in your Render dashboard.
   - **Heroku**: See [HEROKU_DEPLOYMENT.md](HEROKU_DEPLOYMENT.md) for the Heroku Container Stack setup.
3. Ensure both services share the same `REDIS_URL`.
