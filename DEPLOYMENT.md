# OmniOps Deployment Guide

This document explains how to deploy OmniOps in two scenarios: locally using Docker Compose, and to production using Managed Cloud Services (Render, Vercel, Neon, Neo4j Aura, Qdrant Cloud, Upstash).

## 1. Local Docker Deployment

OmniOps is pre-configured to run out-of-the-box using Docker Compose. This starts all required databases (PostgreSQL, Neo4j, Qdrant, Redis), the FastAPI application, and the RQ Worker.

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

---

## 2. Managed Cloud Deployment

For the ET AI Hackathon (or production deployments), you can deploy OmniOps using a fully managed free-tier stack. 

### Architecture
- **Frontend**: Vercel
- **Backend API & Worker**: Render
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

### Render Deployment (Backend & Worker)
We use a `render.yaml` Blueprint file to deploy the backend.

1. Connect your GitHub repository to Render.
2. In Render, select **Blueprints** -> **New Blueprint Instance**.
3. Select this repository. Render will automatically detect the `render.yaml` file.
4. Render will prompt you for the Environment Variables (like `DATABASE_URL`, `NEO4J_URI`, etc.) because they are marked `sync: false` in the blueprint. Fill them in using the values from your Managed Services.
5. Render will provision two services:
   - `omniops-api` (Web Service, exposes `/health`)
   - `omniops-worker` (Background Worker, processes ingestion queues)

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
1. Verify `omniops-worker` is running in Render.
2. Verify the `REDIS_URL` in both `omniops-api` and `omniops-worker` match exactly.
3. Check the worker logs in Render for parsing errors.

### Local Storage Warning
For the hackathon, we are preserving the `STORAGE_BACKEND=local` setting. Because Render containers are ephemeral, files uploaded will disappear after a container restart (approx 15 mins of inactivity). Metadata and Graph data **will persist** because they live in managed databases, but downloading the original file may fail after a restart. This is expected and acceptable for a 5-document demo.
