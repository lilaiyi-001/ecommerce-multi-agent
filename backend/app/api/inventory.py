"""补货/清仓建议 API 路由"""
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.inventory import InventoryInput, InventoryOutput
from app.agents.agent_08_inventory_advice.inventory_advice import analyze_inventory
from app.utils.auth import require_auth

router = APIRouter(dependencies=[Depends(require_auth)], prefix="/api/v1/inventory", tags=["补货/清仓"])


@router.post("/analyze", response_model=InventoryOutput)
def post_inventory(input_data: InventoryInput):
    try:
        return analyze_inventory(input_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"补货建议失败: {str(e)}")
