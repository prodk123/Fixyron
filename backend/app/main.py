from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging
from app.api.routes import health, repositories, qa, diagnosis, repair, publication

setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.API_V1_STR, tags=["health"])
app.include_router(repositories.router, prefix=settings.API_V1_STR + "/repositories", tags=["repositories"])
app.include_router(qa.router, prefix=settings.API_V1_STR + "/qa", tags=["qa"])
app.include_router(diagnosis.router, prefix=settings.API_V1_STR + "/diagnosis", tags=["diagnosis"])
app.include_router(repair.router, prefix=settings.API_V1_STR + "/repair", tags=["repair"])
app.include_router(publication.router, prefix=settings.API_V1_STR + "/repair", tags=["publication"])
