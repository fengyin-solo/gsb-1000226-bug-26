"""箱变管理接口：维护箱式变压器，覆盖停机检修、复归信号、恢复供电等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.transformer import TransformerService

router = APIRouter(prefix="/api/transformer", tags=["箱变管理"])

service = TransformerService()

LIST_FIELDS = ["箱变编号", "箱变型号", "额定容量", "所属电站", "油温", "绕组温度", "上次检修日", "箱变状态"]
STATUSES = ["运行", "轻瓦斯", "重瓦斯", "停机"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按箱变编号检索"),
    status: str | None = Query(default=None, description="运行、轻瓦斯、重瓦斯、停机"),
    model: str | None = Query(default=None, alias="箱变型号", description="按箱变型号检索"),
    capacity: str | None = Query(default=None, alias="额定容量", description="按额定容量检索"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按箱变编号、型号、容量与状态过滤箱变管理列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        keyword=keyword, status=status, model=model, capacity=capacity, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出箱变管理清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "transformer", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条箱式变压器明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"箱式变压器 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条箱式变压器，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="箱式变压器已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条箱式变压器执行停机检修、复归信号、恢复供电；不符合当前状态流转的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
