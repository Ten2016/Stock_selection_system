from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.utils.database import get_db
from app.utils.response import success

router = APIRouter()


@router.get("")
async def get_strategies(db: Session = Depends(get_db)):
    return success(data=[])


@router.post("/select")
async def select_stocks(db: Session = Depends(get_db)):
    return success(data={"strategies": [], "selected_stocks": []})
