# Recommender Service

An asynchronous FastAPI backend that records user events and returns personalized product recommendations. It uses PostgreSQL for users, products, events, and prediction history; Redis for recommendation caching; and Groq for LLM-based candidate reranking.

## Live deployment

- API base URL: [https://recommender-system-api-iqrl.onrender.com](https://recommender-system-api-iqrl.onrender.com)
- Interactive API docs (Swagger UI): [https://recommender-system-api-iqrl.onrender.com/docs](https://recommender-system-api-iqrl.onrender.com/docs)

The API base URL returns `{"detail":"Not Found"}` at `/` because this backend does not define a homepage. Use `/docs` to explore and call the API.

## Features

- `POST /api/v1/events` validates and queues product-view, category-view, and purchase events.
- `GET /api/v1/recommendations/{user_id}` summarizes a user's event history, retrieves active products, reranks candidates, persists prediction results, and caches the response.
- Groq results are checked against candidate product IDs and scores are clamped to `[0, 1]`.
- If Groq is unavailable or returns invalid data, the service logs the failure and uses fallback scores of `0.5`.
- FastAPI lifespan hooks open and close the Redis client.

## Requirements

- Python 3.11 or newer
- Docker Desktop with Docker Compose (recommended for local PostgreSQL and Redis)
- A Groq API key for LLM reranking

## Run locally with Docker Compose

1. Create a local environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Set `GROQ_API_KEY` in `.env`. The example file uses the Compose-only hostnames `db` and `redis`; keep these values when running the application in Docker Compose.

3. Start the API, PostgreSQL, and Redis:

   ```powershell
   docker compose up --build -d
   ```

4. Install the Python dependencies on the host if you want to initialize demo data:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

5. Initialize an empty local database with sample users, products, and interactions:

   ```powershell
   python seed_db.py
   ```

   `seed_db.py` is destructive: it truncates existing application tables before inserting sample data. Use it only with a disposable local database. Do not run it against a production database.

6. Open the API documentation at [http://localhost:8000/docs](http://localhost:8000/docs).

To run Uvicorn directly on the host instead of using the Compose `web` service, change the hostnames in `.env` to `localhost`:

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/recommender_db
REDIS_URL=redis://localhost:6379/0
```

Then run:

```powershell
python -m uvicorn app.main:app --reload
```

## Environment variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `DATABASE_URL` | Yes | — | PostgreSQL SQLAlchemy async URL, using the `postgresql+asyncpg://` scheme. |
| `GROQ_API_KEY` | For LLM reranking | Empty | API key from Groq. Without a valid key, recommendations use fallback scores. |
| `GROQ_MODEL` | No | `openai/gpt-oss-120b` | Model ID passed to the Groq chat completions API. |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection URL. In Docker Compose, use `redis://redis:6379/0`. |
| `CACHE_EXPIRATION_SECONDS` | No | `300` | Recommendation cache TTL in seconds. |
| `APP_ENV` | No | `development` | Environment name; use `production` when deployed. |

For Docker Compose, `.env.example` contains development-only database credentials and container hostnames. Do not use those credentials in a public or production deployment.

## API

### Record an event

`POST /api/v1/events`

```json
{
  "user_id": 1,
  "event_type": "product_view",
  "product_id": 42,
  "value": 12.5
}
```

`event_type` must be `product_view`, `category_view`, or `purchase`. `product_id` and `category` are optional; if the event has a product but no category, the product's category is used when building the user profile. `value` must be nonnegative and represents view duration or purchase amount according to event type. The endpoint returns HTTP `202 Accepted`; event persistence and cache invalidation happen in a background task.

### Get recommendations

`GET /api/v1/recommendations/{user_id}?page=1&limit=10`

- `page` starts at 1.
- `limit` must be between 1 and 50.
- The response includes `prediction_id`, reranking latency, pagination metadata, and recommendation items.

Interactive OpenAPI docs are served at `/docs`.

## Deploy on Render

Create a **Web Service** from this repository and use the repository root as the Root Directory (leave the Root Directory field blank if Render treats that as the root). The repository includes a Dockerfile; select Docker as the runtime/build method. The container binds to Render's `PORT` environment variable and falls back to port `8000` for local use.

Configure these environment variables on the Render web service:

```text
DATABASE_URL=<Render PostgreSQL internal URL using postgresql+asyncpg://>
GROQ_API_KEY=<your Groq API key>
GROQ_MODEL=openai/gpt-oss-120b
REDIS_URL=<URL for a reachable Redis service>
APP_ENV=production
```

Use Render's **internal** PostgreSQL URL for services in the same Render region. If its URL begins with `postgres://` or `postgresql://`, use the same credentials and host but change the scheme to `postgresql+asyncpg://`. Render PostgreSQL does not provide Redis; provision Redis separately and set `REDIS_URL` to its connection URL. Keep credentials in Render's environment settings, not in source control.

**Database schema setup:** this repository currently contains no Alembic revision scripts. Provision the application tables through your database migration process before sending API requests. `seed_db.py` is a destructive local/demo seeder, not a production migration or deployment command.

## Tests

Activate the project environment and run:

```powershell
python -m pytest -q
```

The tests use mocked or in-memory dependencies; they do not require a live Groq API, PostgreSQL server, or Redis server.

## Project layout

```text
app/
  api/          FastAPI routes and request validation
  core/         Pydantic settings
  db/           SQLAlchemy models, sessions, and Redis helpers
  services/     Event processing, user profiles, recommendations, Groq client
tests/          API, pipeline, and Groq client tests
seed_db.py      Destructive local/demo data seeder
Dockerfile      API container
docker-compose.yml  Local API, PostgreSQL, and Redis
```
