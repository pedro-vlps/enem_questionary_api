# ENEM Questionary · API

Backend for an ENEM study platform that combines multiple-choice exercises, explanations for each answer, and supporting materials. The MVP supports AI-generated questions and a reusable question bank, with an environment setting to control generation costs.

Built by [Pedro](https://github.com/pedro-vlps). Companion repository: [React frontend](https://github.com/pedro-vlps/enem_questionary_front).

## Product overview

Students preparing for Brazil's ENEM exam need varied exercises and feedback that explains their mistakes. ENEM Questionary organizes practice by knowledge area and topic and provides contextual questions with five alternatives, an answer key, and explanations.

AI generation incurs a cost on each request. The API can also serve exercises entirely from PostgreSQL, making it possible to demonstrate the MVP and reuse existing content. Each response identifies how the question was obtained so the interface can display its source.

## MVP capabilities

- Topic and subtopic catalogs for Languages, Mathematics, Natural Sciences, and Human Sciences.
- AI question generation with JSON validation and retries for invalid content.
- Persistence of questions, alternatives, explanations, and supporting materials.
- Random retrieval by topic when AI generation is disabled.
- Manual question creation and reusable support materials through a many-to-many association.
- Text, tables, charts, diagrams, and images, with optional S3 storage.
- Account registration, JWT login, and password recovery with optional SMTP delivery.

## Architecture and engineering decisions

| Layer | Technology and responsibility |
| --- | --- |
| HTTP and contracts | FastAPI and Pydantic for routes, validation, and OpenAPI documentation |
| Application | Controllers and services; a shared generation flow for all four areas |
| Persistence | SQLAlchemy asynchronous sessions and PostgreSQL |
| Content generation | OpenAI for text and images |
| File storage | Optional S3 integration |
| Authentication | JWT, PBKDF2 password hashing, and Fernet field encryption |
| Runtime | Python 3.13+, Poetry, Docker, and Railway configuration |

```text
React → FastAPI routes → Controllers → Services → PostgreSQL
                                           ├── OpenAI (generation enabled)
                                           └── S3 (storage enabled)
```

The generation service selects the operating mode before building prompts or initializing an OpenAI client. Database retrieval loads existing support materials without generating assets or saving another question. Generic routes use the [CRUD generation library](https://github.com/pedro-vlps/api_crud_generate_libary).

## Generation and cost control

Set this variable in the API environment and restart the application:

```dotenv
QUESTION_GENERATION_ENABLED=false
```

| Value | Question endpoint behavior |
| --- | --- |
| `false` (default) | Retrieve a random stored question for the requested topic without calling OpenAI |
| `true` | Generate a new question with AI, persist it, and return it |

Responses include `question_source: "database"` or `question_source: "api"`. This describes the current request: a previously generated question served from storage has source `database`.

For `/with-support-materials`, a stored question must already be linked to **all** selected materials. If no compatible question exists, the API returns HTTP `404` without falling back to paid generation. Populate the bank through `POST /questions` or save questions while generation is enabled.

Image generation during manual creation has a separate setting, `QUESTION_ASSETS_ENABLE_IMAGE_GENERATION`. For a demo without paid generation, keep both flags `false` and use text, structured data, or existing images.

## Local setup

Requirements: Python 3.13+, Poetry, and PostgreSQL, or Docker Compose for the database.

```powershell
git clone https://github.com/pedro-vlps/enem_questionary_api.git
cd enem_questionary_api
Copy-Item .env.example .env
poetry install --no-root
```

Fill in `.env`; numeric and boolean settings cannot remain empty. Configure:

- `APP_ENV=development`, PostgreSQL credentials, and `POSTGRES_PORT=5432`.
- `ALGORITHM=HS256`, a private `JWT_SECRET_KEY`, and an integer `JWT_EXPIRATION_MINUTES`.
- A Fernet key generated with `poetry run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
- Password recovery and SMTP settings. To disable local email delivery, use `SMTP_ENABLED=false`, `SMTP_USE_TLS=false`, `SMTP_USE_SSL=false`, `SMTP_PORT=587`, and `PASSWORD_RESET_INCLUDE_TOKEN_IN_RESPONSE=false`; set an integer `PASSWORD_RESET_TOKEN_EXPIRATION_MINUTES`.
- The current Settings model also declares Stripe fields; real payment credentials are unnecessary for question flows without payments.
- `OPENAI_API_KEY` may remain empty in database mode with image generation disabled. For AI generation, provide a valid key and configure `OPENAI_TEXT_MODEL` and `OPENAI_IMAGE_MODEL`.

To start the database with the current Compose file:

```powershell
New-Item -ItemType Directory -Force src/databases/.cache
docker compose up -d db
Get-Content src/databases/scripts/1.0_generate_db.sql | docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
poetry run uvicorn src.__main__:app --reload --port 8000
```

The SQL script initializes a new database. Older databases that predate the many-to-many association also need `src/databases/scripts/migrations/1.1_question_assets_many_to_many.sql`. The application does not run these scripts automatically.

Use `POSTGRES_HOST=localhost` when running the API outside Docker, or `POSTGRES_HOST=db` when starting both services with `docker compose up --build`. The current Compose file stores data in `src/databases/.cache`. Changing `.env` credentials does not update an existing database. Configure `FRONTEND_ORIGINS` when using a different frontend origin.

Interactive documentation: [localhost:8000/docs](http://localhost:8000/docs). Health check: [localhost:8000/healthy](http://localhost:8000/healthy).

## Main endpoints

Question endpoints require `Authorization: Bearer <token>` obtained through `POST /login`.

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/register`, `/login`, `/forgot-password` | Account access and recovery |
| `GET` | `/ai/{area}/topics` | Topic and subtopic catalog |
| `POST` | `/ai/{area}` | Obtain a question according to the configured mode |
| `POST` | `/ai/{area}/with-support-materials` | Obtain a question using selected materials |
| `POST` | `/questions` | Create a question manually |
| `GET` / `POST` | `/support-materials` | Browse or create support materials |

`{area}` is `math`, `languages`, `natural-sciences`, or `human-sciences`. A basic request accepts `{"topic": "<catalog topic>"}`; material-based requests also require `support_material_ids`, a list of UUIDs. The current generation contract selects a subtopic internally; database retrieval filters by topic.

## Verification and roadmap

```powershell
poetry run python -m unittest discover -s tests -v
```

Regression tests use mocks without paid AI calls or an active database. They cover generation controls, response sources, existing support materials, and missing questions.

This project is an MVP. Planned improvements include PostgreSQL integration tests, subtopic filtering in the API contract, study history, and a policy to avoid repeated questions. Exercises follow ENEM-style prompts rather than an official exam question bank.

Development, commit approval, versioning, and verification rules are documented in [AGENTS.md](AGENTS.md).
