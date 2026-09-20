"""
Main application entrypoint.

Wires FastAPI routers, middleware, and health check.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    auth_router,
    bookings_router,
    events_router,
    organizer_router,
)

app = FastAPI(
    title="Event Booking System",
    description="High-concurrency Event Booking System API with optimistic/pessimistic locking and Celery background tasks.",
    version="1.0.0",
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root health check endpoint preserved as required
@app.get("/health", tags=["utility"], summary="Health check")
def health_check():
    return {
        "status": "healthy"
    }


# Include API v1 routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(events_router, prefix="/api/v1")
app.include_router(bookings_router, prefix="/api/v1")
app.include_router(organizer_router, prefix="/api/v1")