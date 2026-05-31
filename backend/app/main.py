import os
from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.utils.database import init_db

from app.api import stocks, strategies, sync


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(stocks.router, prefix=f"{settings.API_V1_PREFIX}/stocks", tags=["stocks"])
app.include_router(strategies.router, prefix=f"{settings.API_V1_PREFIX}/strategies", tags=["strategies"])
app.include_router(sync.router, prefix=f"{settings.API_V1_PREFIX}/sync", tags=["sync"])


@app.get("/")
async def root():
    return {"message": f"{settings.PROJECT_NAME} API", "version": settings.VERSION}
