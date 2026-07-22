"""补货/清仓建议智能体（Inventory Advice）

职责：基于库存数据和销售趋势，判断商品该补货还是清仓。
纯规则引擎，不依赖 LLM。

飞书权限：不可检索飞书  依赖 LLM：否
"""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)
from app.schemas.inventory import InventoryInput, InventoryOutput



def analyze_inventory(input_data: InventoryInput) -> InventoryOutput:
    """补货/清仓建议主入口（v0.3：注入库存表真实数据）"""
    product = input_data.product
    product_id = input_data.product_id
    if not product or not product_id:
        if not input_data.context:
            input_data.context = {}
        product = {"title": "默认商品", "current_stock": 100, "avg_daily_sales": 10}
        product_id = 0
    title = product.get("title", f"商品{product_id}")
    current_stock = product.get("current_stock", product.get("stock_qty", 100))
    daily_sales = product.get("avg_daily_sales", 10)
    trend = input_data.trend_info.get("demand_trend", "平稳") if isinstance(input_data.trend_info, dict) else "平稳"

    # 原始判断逻辑
    if daily_sales <= 0:
        stockout_days = 999
    else:
        stockout_days = current_stock / daily_sales

    if stockout_days < 7:
        advice = "补货"
        suggested_quantity = max(30, int(daily_sales * 14 - current_stock))
        urgency = "高"
        reason = f"库存仅够{stockout_days:.1f}天，急需补货{suggested_quantity}件"
    elif stockout_days > 90:
        advice = "清仓"
        suggested_quantity = max(10, int(current_stock * 0.3))
        urgency = "中"
        reason = f"库存可维持{stockout_days:.0f}天，积压风险，建议清仓{suggested_quantity}件"
    else:
        advice = "维持"
        suggested_quantity = 0
        urgency = "低"
        reason = f"库存健康，可维持{stockout_days:.0f}天"

    # ---- 交叉数据注入 ----
    restock_qty = suggested_quantity
    stockout_real = stockout_days
    clearance_urg = "正常"
    restock_detail = reason
    try:
        from app.services.cross_table import get_all_cross_views
        cross_views = get_all_cross_views("")
        for cv in cross_views:
            if str(cv.get("product_id", "")) == str(product_id):
                inv = cv.get("inventory")
                if inv:
                    outbound = inv.get("cumulative_outbound", 0)
                    qty = inv.get("stock_qty", 0)
                    warning = inv.get("warning_stock", 0)
                    if outbound > 0:
                        daily = outbound / 30
                        stockout_real = round(qty / daily, 1) if daily > 0 else 999
                        if qty < warning:
                            clearance_urg = "紧急"
                            restock_qty = max(0, int(warning * 1.5 - qty))
                            restock_detail = (
                                f"库存{qty}低于预警线{warning}，"
                                f"日均出库{daily:.1f}件，{stockout_real}天后断货，建议补货{restock_qty}件"
                            )
                        elif stockout_real > 90:
                            clearance_urg = "建议"
                            restock_detail += f"（真实出库速度{daily:.1f}件/天，库存周转{stockout_real}天）"
                break
    except Exception:
        pass

    display = (
        f"\u3010{title[:25]}\u3011\u8865\u8d27/\u6e05\u4ed3\u5efa\u8bae\n"
        f"\u5efa\u8bae\uff1a{advice} | \u7d27\u6025\u5ea6\uff1a{urgency}\n"
        f"\u53ef\u7ef4\u6301\u5929\u6570\uff1a{stockout_days:.0f}\u5929 | \u8d8b\u52bf\uff1a{trend}\n"
        f"\u5efa\u8bae\u64cd\u4f5c\uff1a{reason}"
    )

    return InventoryOutput(
        product_id=product_id,
        advice=advice,
        stockout_days=stockout_days,
        suggested_quantity=suggested_quantity,
        urgency=urgency,
        reason=reason,
        suggested_restock_qty=restock_qty,
        days_until_stockout=stockout_real,
        clearance_urgency=clearance_urg,
        restock_reason=restock_detail,
        for_downstream={
            "advice": advice,
            "suggested_quantity": restock_qty,
            "stockout_days": stockout_real,
            "clearance_urgency": clearance_urg,
        },
        for_display=display,
    )
