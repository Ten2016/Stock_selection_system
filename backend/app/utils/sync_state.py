"""同步任务内存状态（单机单用户场景）。"""

from typing import Any, Dict, List
from threading import Lock

_state_lock = Lock()

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
    "status": "idle",
    "error_msg": None,
}


def is_cancelled() -> bool:
    return bool(sync_status.get("cancelled"))


def begin_sync() -> bool:
    with _state_lock:
        if sync_status["is_syncing"]:
            return False
        sync_status.update({
            "is_syncing": True,
            "progress": 0,
            "cancelled": False,
            "success_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "no_data_count": 0,
            "failed_stocks": [],
            "no_data_stocks": [],
            "status": "running",
            "error_msg": None,
        })
        return True


def end_sync(error_msg: str = None) -> None:
    with _state_lock:
        status = 'failed' if error_msg else (
            'cancelled' if is_cancelled() else (
                'partial' if sync_status['failed_count'] else 'success'
            )
        )
        sync_status['status'] = status
        sync_status['error_msg'] = error_msg
        if status in ('success', 'partial'):
            sync_status['progress'] = 100
        sync_status["is_syncing"] = False


def request_cancel() -> None:
    with _state_lock:
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
