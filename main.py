from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

from app.services.firebase.firebase_config import initialize_firebase
from app.features.feed.api.feed_routes import router as feed_router
from app.features.pushNotifications.api.notification_routes import router as notification_router
from app.features.telemetry.api.telemetry_route import router as telemetry_router

# 1. Load local environment configurations from your .env file
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event manager that executes tasks before the server starts accepting
    client traffic and handles clean up during teardown.
    """
    print("Launching server: Executing infrastructure lifecycle hooks...")
    try:
        # Trigger the Firebase Admin initialization handshake
        initialize_firebase()
    except Exception as error:
        print(f"CRITICAL BOOT ERROR: {str(error)}")
        # Exit execution if we don't have a database connection
        raise SystemExit(1)

    yield
    print("Shutting down server: Tearing down connections...")


# 2. Assign the lifespan lifecycle context to the FastAPI app instance
app = FastAPI(
    title="Live Layoff Tracker API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(feed_router)

app.include_router(notification_router)

app.include_router(telemetry_router)


@app.get("/health")
def health_check():
    """ Simple sanity check endpoint to verify backend status. """
    return {"status": "operational"}