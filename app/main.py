from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.middleware import track_ai_client_usage
from app.routers import publications, kpt, trust, relations, publishers, integrity, auth, ai_clients


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="KAKAPO",
    description="Scientific reliability infrastructure. Certify, link and score scientific publications via KPT and Trust Engine.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.middleware("http")(track_ai_client_usage)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(publications.router)
app.include_router(kpt.router)
app.include_router(trust.router)
app.include_router(relations.router)
app.include_router(publishers.router)
app.include_router(integrity.router)
app.include_router(auth.router)
app.include_router(ai_clients.router)


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "kakapo", "version": "1.0.0"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}

from app.routers import reviews
app.include_router(reviews.router)

from app.routers import contact
app.include_router(contact.router)
