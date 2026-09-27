"""箱变管理业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "transformer"
REQUIRED_FIELDS = ["箱变编号", "箱变型号", "额定容量"]
STATUS_ORDER = ["运行", "轻瓦斯", "重瓦斯", "停机"]
ACTION_RULES = {"停机检修": "停机", "复归信号": "运行", "恢复供电": "运行"}
NEGATIVE_ACTIONS = []

# 生命周期状态机：每个状态只允许列出的动作，可切换动作一律按当前状态重新计算
STATE_ACTIONS = {
    "运行": ["停机检修"],
    "轻瓦斯": ["复归信号", "停机检修"],
    "重瓦斯": ["停机检修"],
    "停机": ["恢复供电"],
}

# 列表、详情、操作弹窗共用的状态展示字段，始终跟着生命周期 status 走
STATUS_FIELD = "箱变状态"

# 停运后不再残留运行温度；恢复供电后回到典型运行值
STOPPED_READING = "—"
RUNNING_READINGS = {"油温": "45℃", "绕组温度": "58℃"}


def available_actions(status: str | None) -> list[str]:
    """按当前状态流转计算可切换动作；不在状态机里的状态不允许任何动作。"""
    return list(STATE_ACTIONS.get(str(status or ""), []))


class TransformerService:
    def _serialize(self, entry: dict[str, Any]) -> dict[str, Any]:
        """统一出口：同步展示字段并按当前状态重算动作，保证各界面读到同一环节。"""
        entry[STATUS_FIELD] = entry.get("status")
        data = dict(entry)
        actions = available_actions(entry.get("status"))
        data["available_actions"] = actions
        data["action_targets"] = {action: ACTION_RULES[action] for action in actions}
        return data

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        model: str | None = None,
        capacity: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("箱变编号", ""))]
        if model:
            rows = [row for row in rows if model in str(row.get("箱变型号", ""))]
        if capacity:
            rows = [row for row in rows if capacity in str(row.get("额定容量", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._serialize(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return self._serialize(entry)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._serialize(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"箱式变压器 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于箱变管理可执行范围"
        current = str(entry.get("status") or "")
        if action not in available_actions(current):
            return None, f"当前状态「{current}」不允许执行「{action}」，请按状态流转操作"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        if action == "停机检修":
            # 进入停机：记下检修日，清掉运行温度，重新进入不再残留旧值
            entry["上次检修日"] = date.today().isoformat()
            entry["油温"] = STOPPED_READING
            entry["绕组温度"] = STOPPED_READING
        elif action == "恢复供电":
            # 恢复运行：温度回到运行工况，而不是沿用停运时的旧读数
            entry.update(RUNNING_READINGS)
        return self._serialize(entry), f"箱式变压器已{action}"
