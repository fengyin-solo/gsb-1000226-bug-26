"""箱变管理业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "transformer"
REQUIRED_FIELDS = ["箱变编号", "箱变型号", "额定容量"]
STATUS_FIELD = "箱变状态"
STATUS_ORDER = ["运行", "轻瓦斯", "重瓦斯", "停机", "已归档"]
ACTION_RULES = {"停机检修": "停机", "复归信号": "运行", "恢复供电": "运行", "退役归档": "已归档"}
# 每个生命周期环节允许触发的动作：列表、详情、操作弹窗都按这张表渲染，
# 不在这里的动作一律视为越级流转，直接拦下并说明原因。
TRANSITIONS = {
    "运行": ["停机检修"],
    "轻瓦斯": ["复归信号", "停机检修"],
    "重瓦斯": ["停机检修"],
    "停机": ["恢复供电", "退役归档"],
    "已归档": [],
}
NEGATIVE_ACTIONS = []


class TransformerService:
    def _present(self, entry: dict[str, Any]) -> dict[str, Any]:
        """统一出口：展示状态与可执行动作都由当前生命周期环节实时算出来。"""
        row = dict(entry)
        row[STATUS_FIELD] = row.get("status")
        row["available_actions"] = list(TRANSITIONS.get(str(row.get("status") or ""), []))
        return row

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("箱变编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._present(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return self._present(entry)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry[STATUS_FIELD] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._present(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"箱式变压器 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于箱变管理可执行范围"
        current = str(entry.get("status") or "")
        allowed = TRANSITIONS.get(current, [])
        if action not in allowed:
            expect = "、".join(allowed) if allowed else "无"
            return None, f"当前状态「{current}」不允许{action}，可执行动作：{expect}"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry[STATUS_FIELD] = target
        entry["pending"] = target not in ("停机", "已归档")
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        if action == "停机检修":
            entry["上次检修日"] = date.today().isoformat()
        return self._present(entry), f"箱式变压器已{action}"
