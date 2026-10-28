# Tellbook | تلبوک

A Persian, right-to-left bookstore for sourcing books, selling accessories and fixed bundles, and combining paid purchases into shipments.

Tellbook pairs a React storefront and staff workspace with a Django REST API. It supports publisher catalog imports, manual payment verification, customer shelves, fulfillment tracking, and refunds.

**Status:** under active development, with deployment configuration for private staging. Public launch requires real SMS verification and a completed deployment and security review.

## Features

- Book search with Persian text normalization, publisher editions, price filters, and pagination.
- Accessories and fixed bundles with image galleries and homepage placement.
- Mixed-cart checkout with postal delivery, buyer-arranged courier, or storage on a customer shelf.
- Manual bank-transfer receipts, staff payment review, and protected receipt downloads.
- Individual fulfillment tracking, 30-day storage deadlines, and combined shipping of selected ready items.
- Cancellation previews, return confirmation, and an auditable manual refund workflow.
- Excel imports with reusable column mappings, explicit Rial/Toman units, change previews, and review before application.
- Catalog editing, price-review queues, editorial book posts, and staff activity indicators.

All business prices use **Toman**. Persian numerals and Jalali dates are presentation conventions; API values remain machine-readable.

## Technology

| Layer | Stack |
|---|---|
| Frontend | React 19, Vite 8, React Router, TanStack Query, Axios |
| Interface | Tailwind CSS, Vazirmatn, Lucide icons, RTL layouts |
| API | Python, Django 5.2, Django REST Framework, SimpleJWT |
| Database | PostgreSQL 16 |
| Background jobs | Celery and Redis |
| Spreadsheet processing | pandas, openpyxl, RapidFuzz |
| Deployment | Docker Compose, Gunicorn, Caddy |
| Verification | Django tests, Node tests, Playwright, Oxlint |

## Repository layout

```text
config/              Django settings, routing and Celery configuration
accounts/            Phone authentication and user accounts
catalog/             Books, search, contributors and editorial content
publisher_catalog/   Publishers, editions and staged Excel imports
merchandise/         Accessories, bundles, checkout and fulfillment
requests_orders/     Book requests, quotes, orders and cancellations
payments/            Receipt storage, verification and payment expiry
stock/               Customer shelf items and storage expiry
shipping/            Addresses, delivery fees, shipments and tracking
refunds/             Refund policies and processing records
discounts/           Discount validation and application
notifications/       Outgoing notifications and delivery logs
core/                Shared permissions, settings and admin activity
src/                 React pages, components, layouts and API clients
public/              Static frontend assets
tests/               Cross-module, frontend and browser tests
deploy/              Staging images, proxy configuration and scripts
```

The `stock` module tracks customer-owned ready items and historical fulfillment. New purchases use sourcing/preparation rather than a retail inventory-quantity workflow.

## Local development

### Requirements

- Python 3.14, matching the supplied container images.
- Node.js 24 and npm.
- Docker Engine with Compose v2.
- PostgreSQL client development libraries and a C compiler when installing Python dependencies on the host.

Run commands from the repository root. Create `.env` only on first setup; preserve an existing configuration.

```bash
cp .env.example .env
python3 -m venv venv
venv/bin/pip install -r requirements-dev.txt
npm ci
```

Start the local database and Redis:

```bash
docker compose up -d db redis
```

Export the backend's local connection settings, apply migrations, and start Django:

```bash
export POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433
export DJANGO_DEBUG=1 OTP_DELIVERY_MODE=development
export CELERY_BROKER_URL=redis://127.0.0.1:6379/0
export CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0

venv/bin/python manage.py migrate
venv/bin/python manage.py runserver 127.0.0.1:8080
```

In another terminal:

```bash
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` and `/media` to Django on port 8080. `DEV_API_TARGET` overrides that destination when necessary.

Django host commands read process environment variables; they do not automatically load `.env`. The database credentials must match the values used by Compose. If you change the sample database credentials, export the corresponding `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` for host processes too.

### Background workers

In separate terminals, using the same backend environment:

```bash
venv/bin/celery -A config worker -Q celery,catalog_imports -l info
```

```bash
venv/bin/celery -A config beat -l info
```

The worker consumes both ordinary jobs and catalog imports. Run only one beat scheduler. Payment expiry runs each minute; shelf expiry runs daily at 03:00 Asia/Tehran.

### Development authentication

Login uses a phone number. With development delivery enabled and Django debugging on, the verification code appears in the login interface. Codes expire after five minutes, allow five failed attempts, and are single-use.

This mode does not verify phone ownership and must not be exposed to public customers. Real SMS delivery is not yet integrated. Staff access uses the `creator` role and is enforced by the backend.

## Checks

With the local PostgreSQL service available:

```bash
venv/bin/python manage.py test --settings=config.test_settings --noinput
npm test
npm run lint
npm run build
```

Database tests use a separate `test_tellbook` database. Do not run multiple database suites against that name simultaneously.

Browser journeys are opt-in. With Google Chrome installed:

```bash
RUN_BROWSER_TESTS=1 PLAYWRIGHT_CHANNEL=chrome \
  venv/bin/python manage.py test tests --settings=config.test_settings --noinput
```

Alternatively, install Playwright Chromium with `venv/bin/playwright install chromium` and omit `PLAYWRIGHT_CHANNEL`.

## Private staging

`compose.staging.yml` runs PostgreSQL, Redis, the Django application, a Celery worker, one beat scheduler, and a Caddy HTTPS proxy. Only the proxy publishes ports 80 and 443. Database and uploaded files use persistent volumes.

Configuration starts from `deploy/staging.env.example`, copied locally to `.env.staging`. Supply a domain pointing to the server, unique application/database secrets, an independent proxy secret, and a password hash for the shared staging gate.

The `deploy/staging` helper selects the staging Compose file and environment. Before accepting traffic, build the images, start the database/Redis, apply migrations, collect static files, and start the remaining services. Validate HTTPS, authentication, receipt access, and backup restoration on the actual server before sharing access.

Staging intentionally keeps test login behind a password gate. It is not a public-production authentication configuration. Frontend staging builds use `VITE_API_BASE_URL=/api` and `VITE_AUTH_HEADER=X-Tellbook-Authorization` to keep application tokens separate from the gate's HTTP Basic credentials.

## Data and operations

- Receipt images are served through authorized API endpoints, not public media URLs.
- Back up both PostgreSQL and uploaded files. Container images and Git history do not contain live store data.
- `deploy/backup-staging` creates database and upload archives; stop application writes and background workers for a consistent snapshot, then copy backups to independent private storage.
- Apply database migrations after deploying schema changes. Restarting a container alone does not apply them.
- Keep real environment files, database dumps, uploads, and credentials out of version control.

## Development

Frontend development was AI-assisted.
