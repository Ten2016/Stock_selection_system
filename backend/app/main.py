from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.utils.database import init_db

from app.api import backtest, stocks, strategies, sync


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

# 单机单用户，前端经 Vite 代理同源访问；不使用 Cookie 鉴权，故关闭 credentials
# （allow_origins=["*"] 与 allow_credentials=True 组合会被浏览器判为非法）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(stocks.router, prefix=f"{settings.API_V1_PREFIX}/stocks", tags=["stocks"])
app.include_router(strategies.router, prefix=f"{settings.API_V1_PREFIX}/strategies", tags=["strategies"])
app.include_router(sync.router, prefix=f"{settings.API_V1_PREFIX}/sync", tags=["sync"])
app.include_router(backtest.router, prefix=f"{settings.API_V1_PREFIX}/backtest", tags=["backtest"])


@app.get("/")
async def root():
    return {"message": f"{settings.PROJECT_NAME} API", "version": settings.VERSION}
