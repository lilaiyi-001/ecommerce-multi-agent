"""补货/清仓建议智能体（Inventory Advice）

职责：基于库存数据和销售趋势，判断商品该补货还是清仓。
纯规则引擎，不依赖 LLM。

飞书权限：不可检索飞书  依赖 LLM：否
"""
from __future__ import annotations
from app.schemas.inventory import InventoryInput, InventoryOutput


def analyze_inventory(input_data: InventoryInput) -> InventoryOutput:
    """补货/清仓建议主入口"""
    try:
        product = input_data.product
        trend_info = input_data.trend_info

        # product_id=0（未指定）时自动选择类目下第一个商品
        if input_data.product_id == 0 and not product.get("current_stock") and not product.get("avg_daily_sales"):
            from app.services.data_generator import get_demo_products
            cat = product.get("category", input_data.context.get("category", "electronics")) if product else "electronics"
            if hasattr(input_data, "context") and input_data.context and input_data.context.get("category"):
                cat = input_data.context["category"]
            fallback = get_demo_products(cat)
            if fallback:
                input_data.product_id = fallback[0]["product_id"]
                product = fallback[0]

        title = product.get("title", f"商品{input_data.product_id}")
        stock = product.get("current_stock", 0)
        daily_sales = product.get("avg_daily_sales", 0)
        trend = trend_info.get("demand_trend", "平稳")

        # 边界情况
        # 无商品数据
        if stock <= 0 and daily_sales <= 0:
            return InventoryOutput(
                product_id=input_data.product_id, advice="维持",
                stockout_days=0, urgency="低",
                reason=f"「{title}」缺少库存和销售数据，无法分析",
                for_display=f"【{title}】缺少商品数据信息，无法进行补货/清仓分析。",
            )

        # 有销售但无库存
        if stock <= 0 and daily_sales > 0:
            return InventoryOutput(
                product_id=input_data.product_id, advice="补货",
                stockout_days=0, urgency="高",
                reason=f"「{title}」库存为0但日均销售{daily_sales:.0f}件，需立即补货",
                suggested_quantity=max(1, round(daily_sales * 30)),
                for_display=f"【{title}】库存已耗尽！日均销售{daily_sales:.0f}件，建议立即补货{max(1, round(daily_sales * 30))}件。",
            )

        # 有库存但无销售
        if daily_sales <= 0:
            return InventoryOutput(
                product_id=input_data.product_id, advice="维持",
                stockout_days=float("inf") if stock > 0 else 0, urgency="低",
                reason=f"「{title}」暂无销售数据，建议维持当前库存",
                for_display=f"【{title}】暂无销售数据，库存{stock}件，建议维持现状。",
            )

        # 核心规则
        stockout_days = stock / daily_sales
        trend_factor = {"上升": 0.8, "平稳": 1.0, "下降": 1.2}.get(trend, 1.0)
        adjusted_days = stockout_days * trend_factor

        if adjusted_days < 15:
            advice, urgency = "补货", "高"
            suggested = max(1, round(daily_sales * 30))
            reason = f"库存仅可维持{stockout_days:.0f}天（趋势{trend}），需立即补货{suggested}件"
        elif adjusted_days < 30:
            advice, urgency = "补货", "中"
            suggested = max(1, round(daily_sales * 30))
            reason = f"库存可维持{stockout_days:.0f}天，建议补货{suggested}件以维持正常周转"
        elif adjusted_days < 90:
            advice, urgency = "维持", "低"
            suggested = 0
            reason = f"库存可维持{stockout_days:.0f}天，库存水平健康，维持现状"
        elif adjusted_days < 180:
            advice, urgency = "清仓", "中"
            suggested = max(1, round(stock * 0.3))
            reason = f"库存可维持{stockout_days:.0f}天，库存压力较大，建议促销清仓{suggested}件"
        else:
            advice, urgency = "清仓", "高"
            suggested = max(1, round(stock * 0.5))
            reason = f"库存可维持{stockout_days:.0f}天，库存严重积压，需立即清仓{suggested}件"

        if advice == "清仓" and stock > 1000:
            reason += "，建议考虑降价促销或捆绑销售"

        display = (
            f"【{title}】补货/清仓建议\n"
            f"建议：{advice}（{urgency}优先级）\n"
            f"库存：{stock}件 | 日均销售：{daily_sales:.0f}件\n"
            f"可维持天数：{stockout_days:.0f}天 | 趋势：{trend}\n"
            f"建议操作：{reason}"
        )

        return InventoryOutput(
            product_id=input_data.product_id,
            advice=advice,
            stockout_days=round(stockout_days, 1),
            suggested_quantity=suggested,
            urgency=urgency,
            reason=reason,
            for_downstream={
                "advice": advice,
                "suggested_quantity": suggested,
                "urgency": urgency,
            },
            for_display=display,
        )


    except Exception as e:
        logger.error(f"analyze_inventory 异常: {{e}}")
        return InventoryOutput(category=getattr(input_data, 'category', '?'), recommendations=[], for_display=f'补货/清仓分析异常: {{e}}')
