"""同步任务内存状态（单机单用户场景）。"""

from typing import Any, Dict, List

sync_status: Dict[str, Any] = {
    "is_syncing": False,
    "progress": 0,
    "cancelled": False,
    "success_count": 0,
    "failed_count": 0,
    "skipped_count": 0,
    "no_data_count": 0,
    "failed_stocks": [],
    "no_data_stocks": [],
}


def is_cancelled() -> bool:
    return bool(sync_status.get("cancelled"))


def begin_sync() -> None:
    sync_status.update({
        "is_syncing": True,
        "progress": 0,
        "cancelled": False,
        "success_count": 0,
        "failed_count": 0,
        "skipped_count": 0,
        "no_data_count": 0,
        "failed_stocks": [],
        "no_data_stocks": [],
    })


def end_sync() -> None:
    sync_status["is_syncing"] = False


def request_cancel() -> None:
    if sync_status["is_syncing"]:
        sync_status["cancelled"] = True


def update_counts(
    success_count: int,
    skipped_count: int,
    failed_stocks: List[dict],
    no_data_stocks: List[dict],
    progress: int,
) -> None:
    sync_status["success_count"] = success_count
    sync_status["skipped_count"] = skipped_count
    sync_status["failed_count"] = len(failed_stocks)
    sync_status["no_data_count"] = len(no_data_stocks)
    sync_status["failed_stocks"] = failed_stocks
    sync_status["no_data_stocks"] = no_data_stocks
    sync_status["progress"] = progress
