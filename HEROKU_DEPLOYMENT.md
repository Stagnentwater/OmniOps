> [!WARNING]
> **DEPRECATED FOR HACKATHON:** The RQ worker now runs embedded inside the FastAPI process (controlled by `EMBED_WORKER=true`). A separate Heroku worker deployment is no longer required. This document is preserved as reference for production deployments that require a standalone worker. See [DEPLOYMENT.md](DEPLOYMENT.md) for the current deployment model.

# OmniOps Heroku Worker Deployment

Because Render no longer provides a free background worker, and traditional Heroku Buildpacks require `requirements.txt` to live in the root directory (breaking our monorepo structure), we use **Heroku's Container Stack (Docker)** to deploy the worker.

This strategy uses the existing `backend/Dockerfile` with zero structural changes to the repository.

## Prerequisites
- A Heroku account (with Student Developer Pack credits applied).
- Heroku CLI installed (`npm install -g heroku`).
- Docker installed locally.

## Deployment Steps

### 1. Create the Heroku App
Log in to Heroku from your terminal and create a new app:
```bash
heroku login
heroku create omniops-worker-app
```

### 2. Set the Stack to Container
Tell Heroku that this app uses Docker rather than standard buildpacks:
```bash
heroku stack:set container -a omniops-worker-app
```
*(This tells Heroku to look for the `heroku.yml` file we added to the repository root).*

### 3. Configure Environment Variables
The worker needs to connect to the exact same Managed Cloud Services that the API uses. Set these securely on Heroku:

```bash
heroku config:set REDIS_URL="<your-upstash-redis-url>" -a omniops-worker-app
heroku config:set DATABASE_URL="<your-neon-postgres-url>" -a omniops-worker-app
heroku config:set QDRANT_URL="<your-qdrant-url>" -a omniops-worker-app
heroku config:set QDRANT_API_KEY="<your-qdrant-api-key>" -a omniops-worker-app
heroku config:set NEO4J_URI="<your-neo4j-aura-uri>" -a omniops-worker-app
heroku config:set NEO4J_USERNAME="neo4j" -a omniops-worker-app
heroku config:set NEO4J_PASSWORD="<your-neo4j-password>" -a omniops-worker-app
heroku config:set OPENROUTER_API_KEY="<your-openrouter-key>" -a omniops-worker-app
```
*(Ensure `REDIS_URL` matches exactly what you gave to Render so the API and Worker share the same queue).*

### 4. Deploy the Worker
Commit all changes and push to the Heroku git remote:
```bash
git push heroku main
```
Heroku will read `heroku.yml`, build the `backend/Dockerfile`, and start the `worker` process.

### 5. Verify the Deployment
Once deployed, scale the worker to 1 dyno (if it didn't start automatically) and check the logs:
```bash
heroku ps:scale worker=1 -a omniops-worker-app
heroku logs --tail -a omniops-worker-app
```
You should see our new startup logs:
```text
INFO:     Initializing OmniOps Worker...
INFO:     Connecting to Redis via REDIS_URL...
INFO:     Successfully connected to Redis!
INFO:     Starting RQ worker on queue: 'default'
```

## Troubleshooting
- **Build Failures:** Ensure you ran `heroku stack:set container`. If it tries to use the Python buildpack, it will fail looking for `requirements.txt`.
- **Jobs stuck in PENDING:** Ensure the `REDIS_URL` on Heroku exactly matches the `REDIS_URL` on Render. 
- **Connection Errors:** The new startup logs will explicitly tell you if Redis fails to connect. For other services (Postgres, Neo4j, Qdrant), verify your Heroku config variables.
