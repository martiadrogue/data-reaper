# Data Reaper

Loads [Night Crawler](https://github.com/martiadrogue/night-crawler)'s
validated CSVs into MongoDB. It uses one collection per kind of data,
`dataset_places` and `dataset_events`, with a typed field for every CSV
column. Celery Beat picks up new files every minute and a Celery worker
imports each one. Rows are upserted by website + item id, so re-crawls
update records instead of duplicating them. A Reflex UI shows the imports
and lets you browse the data. The stack is the same as Night Crawler's:
FastAPI, Reflex, MongoDB, and RabbitMQ, all in Docker, with Night
Crawler's Keycloak for accounts.

## Requirements

You need Docker and Docker Compose, and
[Night Crawler](https://github.com/martiadrogue/night-crawler)'s stack
running first (`make up` in its checkout). It owns Keycloak and the
external `identity` Docker network this stack's API and UI join to reach
it; the importer runs no Keycloak of its own.

## Setup

Copy the example environment file and fill in your own values:

```bash
cp .env_example .env
```

No admin is seeded here: Night Crawler's Keycloak realm import creates
the first one, and admins manage accounts through `/api/users`.
Logging in, signing up, and brute-force protection are Keycloak's.

Copy `KC_IMPORTER_API_SECRET` and `KC_IMPORTER_UI_SECRET` from
`../night-crawler/.env`: they are the secrets of the `importer-api` and
`importer-ui` clients in Night Crawler's Keycloak realm, so they must
match.

API requests are authenticated with Keycloak's access tokens. The
defaults fit Night Crawler's stack, so leave these unset unless its
Keycloak lives elsewhere:

| Key | Default | What it sets |
|---|---|---|
| `OIDC_ISSUER` | `http://localhost:8180/realms/night-crawler` | The `iss` a token must carry: the browser-facing realm URL. |
| `OIDC_JWKS_URL` | `http://keycloak:8080/realms/night-crawler/protocol/openid-connect/certs` | Where the API fetches the signing keys, over the `identity` network. |
| `OIDC_AUDIENCE` | `importer-api` | The `aud` a token must include: the API's client id. |
| `KEYCLOAK_URL` | `http://keycloak:8080` | Keycloak's base URL, for the Admin REST API behind `/api/users`. |
| `KEYCLOAK_REALM` | `night-crawler` | The realm whose accounts `/api/users` manages. |
| `KEYCLOAK_ADMIN_CLIENT_ID` | `importer-api` | The service account the API manages accounts as; Compose sets its secret, `KEYCLOAK_ADMIN_CLIENT_SECRET`, from `KC_IMPORTER_API_SECRET`. |

Then say where the CSVs are:

| Key | Default | What it sets |
|---|---|---|
| `CSV_SOURCE_DIR` | `./var/csv/validated` | Host folder of validated CSVs, mounted read-only. Point it at a Night Crawler checkout (`../night-crawler/var/csv/validated`) to import its runs as they land. |
| `IMPORT_BATCH_SIZE` | `500` | Rows upserted per MongoDB transaction (1 to 5000). |

Only files named `<crawler_id>_<execution_id>_<started>.csv`, as Night
Crawler writes them, are imported. Any other `.csv` shows up as a failed
import that explains why.

## Run

```bash
make build   # build the images and start everything
make up      # start the stack (images already built)
make down    # stop it
```

The ports differ from Night Crawler's, so both stacks can run at once:

| What | URL |
|---|---|
| Web UI | http://localhost:3100 |
| API | http://localhost:8100 (docs at `/docs`) |
| RabbitMQ UI | http://localhost:15673 |

Log in with the admin Night Crawler's Keycloak realm seeds
(`KC_SEED_ADMIN_EMAIL` in `../night-crawler/.env`). Within a minute every file in the folder is
queued and imported: the **Imports** page shows each one's status and
what its rows did. Admins can **Scan for new files** instead of waiting,
and **Retry** an import that failed. **Places** and **Events** list the
records, with search by name or address and a filter by source.

From the API, with a Keycloak access token. The UI's client allows no
password grant, so copy one from a logged-in browser: the
`nci_access_token` cookie on `localhost:3100`. It lasts 5 minutes.

```bash
TOKEN='<the nci_access_token cookie>'

curl -s -X POST localhost:8100/api/dataset-imports/scan -H "Authorization: Bearer $TOKEN"
curl -s localhost:8100/api/dataset-imports -H "Authorization: Bearer $TOKEN" | jq .status_counts
curl -s "localhost:8100/api/places?text=grill&source=thefork.es" -H "Authorization: Bearer $TOKEN" | jq '.items[].name'
curl -s localhost:8100/api/datasets -H "Authorization: Bearer $TOKEN" | jq '.[] | {name, record_count}'
```

The [Bruno](https://www.usebruno.com/) collection in `bruno/` has the
same requests.

## How the data is stored

| Collection | One document per | Fields |
|---|---|---|
| `dataset_places` | place, per website | The places columns: `item_id`, `name`, `address`, `location` (`{latitude, longitude}`), `categories`, `rating`, `review_count`, `price_range`, `website`, `phone`, `opening_hours`, `source_url` |
| `dataset_events` | event, per website | The events columns: `item_id`, `name`, `start_date`, `end_date`, `timezone`, `is_all_day` (from `all_day`), `venue`, `address`, `categories`, `organizers`, `cost`, `price_min`, `price_max`, `image_url`, `source_url` |
| `dataset_imports` | CSV file | Its status, detected dataset, and counters (inserted, updated, unchanged, rejected) |

Every record also has `source` (the website: `thefork.es`,
`maps.google.com`, …) and `item_id`, its natural key. It also has
`content_hash`, `created_at`, `updated_at` (moves only when the content
changes), `last_seen_at`, and the crawler, run, and import that last saw
it. The strategies (dedup, change detection, order safety, retries) and
the known limitations are in
[docs/BUSINESS_RULES.md](docs/BUSINESS_RULES.md#6-strategies-limitations--trade-offs).

## Monitoring

```bash
make up-observability
```

starts Prometheus, Loki, Tempo, Grafana Alloy, and Grafana next to the
stack. Grafana is at http://localhost:3130 (`GRAFANA_ADMIN_USER` /
`GRAFANA_ADMIN_PASSWORD`, `admin` / `admin` when unset), with the
**Data Reaper overview** dashboard: imports per dataset, rows
by outcome, durations, queue depth, and one import's logs and trace by
`import_id`. A plain `make up` turns telemetry off again. Details in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#observability).

## Useful commands

```bash
make test           # backend tests, with coverage
make test-frontend  # frontend tests
make format         # black, then ruff --fix
make lint           # ruff
make complexity     # radon: cyclomatic complexity and maintainability
make logs celery_worker
make restart-db     # drop the database (records and imports) and recreate it
```

## More

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): services, layers, the import pipeline, observability
- [docs/DOMAIN_MODEL.md](docs/DOMAIN_MODEL.md): entities, column mapping, upsert rules, invariants
- [docs/BUSINESS_RULES.md](docs/BUSINESS_RULES.md): requirements, strategies, limitations
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md): the rules all code follows
- [frontend/docs/ARCHITECTURE.md](frontend/docs/ARCHITECTURE.md): the Reflex UI
