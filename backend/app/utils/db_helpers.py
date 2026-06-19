from sqlalchemy.orm import Query


def apply_pagination(query: Query, skip: int = 0, limit: int = 50):
    if skip > 0:
        query = query.offset(skip)
    if limit is not None:
        query = query.limit(limit)
    return query


def safe_like(value: str) -> str:
    return value.replace('%', '\\%').replace('_', '\\_')
