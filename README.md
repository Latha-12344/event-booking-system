# Event Booking System

A high-concurrency backend API for managing and booking event tickets, built with **FastAPI**, **PostgreSQL**, **SQLAlchemy 2.0**, **Celery**, **Redis**, and **Resend**.

---

## Architecture Overview

```mermaid
graph TD
    Client[Client / Web / Mobile] -->|HTTP / REST| API[FastAPI Web Service]
    API -->|SELECT FOR UPDATE / SQL| DB[(PostgreSQL Database)]
    API -->|Push Tasks After Commit| Redis[(Redis Broker)]
    Worker[Celery Worker] -->|Pop Tasks| Redis
    Worker -->|Transactional HTML Email| Resend[Resend Email API]
```

### Request Lifecycle
1. **User Authentication**: Client authenticates via `/api/v1/auth/login` and receives a signed JWT access token.
2. **Event Browsing**: Clients query `/api/v1/events/` (cached/indexed on `is_published` and `starts_at`).
3. **Ticket Booking**:
   - Client sends `POST /api/v1/bookings/`.
   - Transaction opens with row-level pessimistic lock (`SELECT ... FOR UPDATE` on `events`).
   - Verifies ticket availability and decrements `available_tickets`.
   - Inserts booking row and **commits transaction**.
   - **Post-Commit Hook**: Enqueues background Celery task `send_booking_confirmation` only after the DB transaction has successfully committed.
4. **Asynchronous Notification**: Celery worker consumes task and delivers HTML confirmation email via Resend API.

---

## Tech Stack

| Component | Technology | Version | Purpose |
|---|---|---|---|
| **Web Framework** | FastAPI | 0.141.1 | High-performance asynchronous REST API framework |
| **ASGI Server** | Uvicorn | 0.53.0 | Production ASGI server |
| **ORM** | SQLAlchemy | 2.0.54 | Modern type-safe 2.x DeclarativeBase ORM |
| **Database** | PostgreSQL | 15+ | Relational data store with ACID transactions and row locking |
| **Migrations** | Alembic | 1.20.0 | Versioned schema migrations |
| **Task Queue** | Celery | 5.6.3 | Distributed asynchronous task execution |
| **Broker / Cache** | Redis | 8.1.0 | Message broker for Celery and result backend |
| **Email Service** | Resend | 2.47.0 | Transactional email delivery service |
| **Load Testing** | Locust | 2.46.6 | Distributed performance and load testing tool |
| **Testing** | Pytest | 9.1.1 | Unit and integration test suite |

---

## Key Design Decisions & Trade-offs

1. **JWT Authentication over Server Sessions**:
   - Stateless HS256 tokens enable horizontal scaling across multiple API replicas without shared session storage.
2. **Pessimistic Row-Level Locking (`SELECT ... FOR UPDATE`)**:
   - Protects against ticket overselling race conditions when multiple customers concurrently book the last remaining tickets.
   - Guarantees strict correctness and ACID compliance.
3. **Guaranteed Transaction Boundary (Commit Before Enqueue)**:
   - Celery `.delay()` calls occur **only after** `db.commit()` succeeds.
   - *Limitation / Trade-off*: There is a theoretical crash window between `db.commit()` and task enqueueing. If the process is killed in that microsecond window, the booking remains durable in the DB but the email is not sent. This trade-off avoids phantom emails for rolled-back transactions without the full overhead of an Outbox pattern.
4. **Multiple Bookings per Customer**:
   - No `UNIQUE(event_id, customer_id)` constraint exists in the database. A customer can book additional tickets at a later date.
   - Event-update notifications deduplicate recipients by `customer_id` so repeat buyers receive exactly one email.
5. **Integer Cents for Monetary Values**:
   - Prices (`price_cents`) and totals (`total_cents`) are stored as integers to eliminate floating-point arithmetic errors.
6. **No `asyncpg` / Synchronous Architecture Baseline**:
   - Uses synchronous SQLAlchemy with a tuned connection pool (`pool_size=20, max_overflow=10`).
   - Async SQLAlchemy is kept as a candidate optimization only if synchronous I/O is proven to be the bottleneck.
7. **Render Free-Tier 30-Day Expiry Notice**:
   - Free PostgreSQL instances on Render expire after 30 days. For persistent deployments, data exports or a paid plan are required.

---

## API Endpoints

Base path: `/api/v1`

### Authentication (`/api/v1/auth`)
- `POST /register`: Register a new user (`role: "customer"` or `"organizer"`).
- `POST /login`: Authenticate and receive a JWT access token.
- `GET /me`: Get authenticated user profile.

### Events (`/api/v1/events`)
- `POST /`: Create an event (Organizer only).
- `GET /`: List published events (Public, paginated, searchable by keyword, location, date).
- `GET /{event_id}`: Retrieve single event details.
- `PUT /{event_id}`: Full update of event details (Organizer owner only; triggers notification).
- `PATCH /{event_id}`: Partial update of event details (Organizer owner only).
- `PATCH /{event_id}/publish`: Toggle publish status (`is_published=true|false`).
- `DELETE /{event_id}`: Delete event (Organizer owner only).

### Bookings (`/api/v1/bookings`)
- `POST /`: Book tickets for an event (Customer only; row-level lock concurrency protected).
- `GET /`: List authenticated customer's bookings.
- `GET /{booking_id}`: View single booking (Customer owner only).
- `DELETE /{booking_id}`: Cancel booking and release tickets back to available pool.

### Organizer Dashboard (`/api/v1/organizer`)
- `GET /events`: List all events created by current organizer (drafts & published).
- `GET /events/{event_id}/bookings`: View all bookings for an event (Organizer owner only).

### Health Check
- `GET /health`: Returns `{"status": "healthy"}`.

Interactive Swagger documentation is available at `http://localhost:8000/docs`.

---

## Setup & Local Development

### 1. Prerequisites
- Python 3.11+
- PostgreSQL server running locally
- Redis server running locally

### 2. Virtual Environment Setup
```powershell
# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env` and configure:
```env
DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/event_booking
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your-secure-64-character-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
RESEND_API_KEY=re_your_api_key
EMAIL_FROM=noreply@yourdomain.com
```

### 4. Run Migrations
```powershell
alembic upgrade head
```

### 5. Start Application Server
```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Start Celery Worker
```powershell
# On Windows (solo execution pool)
celery -A app.tasks.celery_app worker --loglevel=info -P solo

# On Linux / macOS
celery -A app.tasks.celery_app worker --loglevel=info --concurrency 4
```

---

## Running Automated Tests

Run the complete Pytest test suite:
```powershell
pytest -v
```

The test suite covers:
- **Authentication**: Registration, password hashing, JWT claims, unauthorized rejection.
- **Events**: Organizer CRUD, customer restrictions, draft isolation, ticket boundary validation.
- **Bookings**: Concurrency handling, overselling rejection (409 Conflict), cancellation ticket release, multiple booking allowances.
- **Organizer**: Event management and booking visibility isolation.

---

## Load & Performance Testing

The project includes a realistic Locust load testing suite simulating both customer booking traffic and organizer event management.

### Running Locust
```powershell
# Interactive Web UI mode (http://localhost:8089)
locust -f locust/locustfile.py --host=http://localhost:8000

# Automated Headless Benchmark
python run_benchmark.py
```

### Performance Results

The benchmark records request count, RPS, p50, p95, p99, error rate, HTTP 409s, HTTP 500s, and timeouts in `locust/results/`. A 409 is deliberately recorded as a visible contention failure rather than hidden as a successful request.

#### Initial Performance

The following booking-focused results are actual local runs on 2026-09-20 using the same four tiers: 10, 25, 50, and 100 concurrent users; 15 seconds per tier; 1,000 tickets reset before each tier; pre-issued customer JWTs; PostgreSQL and Redis unchanged. Organizer users were disabled for this isolated booking measurement. Raw artifacts are `locust/results/initial_performance_*` and `locust/results/optimized_performance_*`.

| Users | Booking requests | Successful | 409 conflicts | 500s | Timeouts | Booking RPS | p50 / p95 / p99 | Genuine error rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 266 | 266 | 0 | 0 | 0 | 18.8336 | 15 / 32 / 82 ms | 0% |
| 25 | 702 | 702 | 0 | 0 | 0 | 49.8501 | 13 / 37 / 58 ms | 0% |
| 50 | 1,315 | 1,000 | 315 | 0 | 0 | 93.4378 | 23 / 110 / 150 ms | 0% |
| 100 | 2,000 | 1,000 | 1,000 | 0 | 0 | 142.1043 | 160 / 420 / 640 ms | 0% |

#### Initial Breaking Point

At 50 users the event capacity was exhausted and 315 expected 409 responses appeared; this is a business outcome, not an application failure. The first actual booking performance degradation was 100 users: p99 reached 640 ms, above the 500 ms experiment threshold, while genuine 500s and timeouts remained zero. The run therefore demonstrates both visible expected conflicts and real latency degradation.

#### Bottleneck

The booking endpoint serializes competing requests on the same event row with `SELECT ... FOR UPDATE`. The measured latency increase under contention, with zero 500s and timeouts, identifies the serialized event-row transaction/round-trip path rather than asynchronous email, bcrypt, or the public read endpoints as the booking bottleneck. PostgreSQL row-locking is required for correctness and was preserved.

#### Optimization

The successful booking path performed `db.commit()` followed by `db.refresh(booking)`, adding a second database query after the transaction. The optimization removed that refresh and retained SQLAlchemy's loaded INSERT-returned values by disabling expiration for this session after the commit. The Celery dispatch still occurs only after commit. Password hashing, row locking, and synchronous SQLAlchemy were unchanged.

#### Final Performance

The optimized run used the exact same tiers, duration, capacity reset, host, database, Redis, and token strategy.

| Users | Booking requests | Successful | 409 conflicts | 500s | Timeouts | Booking RPS | p50 / p95 / p99 | Genuine error rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 282 | 282 | 0 | 0 | 0 | 20.0253 | 14 / 31 / 140 ms | 0% |
| 25 | 695 | 695 | 0 | 0 | 0 | 49.3448 | 12 / 40 / 74 ms | 0% |
| 50 | 1,418 | 1,000 | 418 | 0 | 0 | 100.9760 | 12 / 40 / 69 ms | 0% |
| 100 | 2,319 | 1,000 | 1,319 | 0 | 0 | 165.1190 | 33 / 240 / 310 ms | 0% |

#### Before vs After

| Concurrent users | Initial booking RPS | Optimized booking RPS | Initial p50 / p95 / p99 | Optimized p50 / p95 / p99 | Initial genuine error rate | Optimized genuine error rate | Initial breaking point | Optimized breaking point |
|---:|---:|---:|---:|---:|---:|---:|---|---|
| 10 | 18.8336 | 20.0253 | 15 / 32 / 82 ms | 14 / 31 / 140 ms | 0% | 0% | Not reached | Not reached |
| 25 | 49.8501 | 49.3448 | 13 / 37 / 58 ms | 12 / 40 / 74 ms | 0% | 0% | Not reached | Not reached |
| 50 | 93.4378 | 100.9760 | 23 / 110 / 150 ms | 12 / 40 / 69 ms | 0% | 0% | Capacity 409s only | Capacity 409s only |
| 100 | 142.1043 | 165.1190 | 160 / 420 / 640 ms | 33 / 240 / 310 ms | 0% | 0% | 100 users | Not reached through 100 users |

---

## Deployment (Render.com)

The project includes a ready-to-deploy `render.yaml` specification configured for Render's infrastructure.

1. Push code to GitHub repository.
2. Link repository to Render as a **Blueprint**.
3. Render automatically provisions:
   - Web Service (`uvicorn app.main:app`)
   - Background Worker (`celery -A app.tasks.celery_app worker`)
   - PostgreSQL Database (30-day free tier)
   - Redis Instance

Deployment has not been performed or verified from this workspace. No deployed URL is claimed. The Render blueprint defines the API web service, Celery worker, PostgreSQL, Redis, and required environment variables, but a live deployment requires the repository and Render account access.
