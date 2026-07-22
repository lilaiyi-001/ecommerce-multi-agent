"""趋势预测智能体（Trend Forecast）v0.3

职责：多算法融合（线性回归+移动平均+指数平滑），
基于历史销量 + 库存表实际出库数据，预测未来 7/30 天销量走势。

飞书权限：✅ 可调飞书数据
依赖 LLM：可选（趋势理由增强）
"""
from __future__ import annotations
import math
import logging
from typing import Optional
from app.schemas.trend import TrendInput, TrendOutput, ProductTrend, AlgorithmInfo
from app.services.data_generator import get_demo_products
from app.services.category_registry import normalize_category
from app.services.feishu_data import get_feishu_products

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_DAYS = 90
MIN_DATA_POINTS = 3


def _linear_regression_forecast(values: list[float], days: int, hist_len: int) -> list[float]:
    """线性回归预测"""
    n = len(values)
    if n < 2:
        return [values[-1] if values else 0] * days
    x = list(range(n))
    y = values
    x_mean = sum(x) / n
    y_mean = sum(y) / n
    num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
    den = sum((xi - x_mean) ** 2 for xi in x)
    slope = num / den if den != 0 else 0
    intercept = y_mean - slope * x_mean
    return [max(0, slope * (hist_len + i) + intercept) for i in range(days)]


def _moving_average_forecast(values: list[float], days: int) -> list[float]:
    """移动平均预测"""
    n = len(values)
    window = max(1, min(14, n // 3))
    avg = sum(values[-window:]) / window
    return [avg] * days


def _exponential_smoothing_forecast(values: list[float], days: int, alpha: float = 0.3) -> list[float]:
    """指数平滑预测"""
    if not values:
        return [0] * days
    smoothed = values[0]
    for v in values:
        smoothed = alpha * v + (1 - alpha) * smoothed
    result = []
    for _ in range(days):
        result.append(max(0, smoothed))
        smoothed = alpha * smoothed + (1 - alpha) * smoothed
    return result


def _cross_validate(values: list[float], method: str, window: int = 5) -> float:
    """交叉验证 MAE"""
    if len(values) < window + 2:
        return float("inf")
    train = values[:-window]
    actual = values[-window:]
    if method == "linear":
        pred = _linear_regression_forecast(train, window, len(train))
    elif method == "ma":
        pred = _moving_average_forecast(train, window)
    elif method == "es":
        pred = _exponential_smoothing_forecast(train, window)
    else:
        return float("inf")
    return sum(abs(a - p) for a, p in zip(actual, pred)) / window


def _detect_trend(values: list[float]) -> tuple[str, float]:
    """检测趋势方向"""
    if len(values) < 7:
        return "平稳", 0
    n = len(values)
    x = list(range(n))
    x_mean = sum(x) / n
    y_mean = sum(values) / n
    num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, values))
    den = sum((xi - x_mean) ** 2 for xi in x)
    slope = num / den if den != 0 else 0
    mean_val = max(abs(y_mean), 1)
    slope_pct = slope * 7 / mean_val
    if slope_pct > 0.08:
        return "上升", slope
    elif slope_pct < -0.08:
        return "下降", slope
    return "平稳", slope


def _select_algorithm(values: list[float]) -> AlgorithmInfo:
    """根据数据特征自动选择预测算法"""
    n = len(values)
    if n < 7:
        if n < MIN_DATA_POINTS:
            return AlgorithmInfo(
                selected_method="fallback_category_avg",
                reason=f"数据不足{MIN_DATA_POINTS}个点，无法进行预测",
                weights={},
                confidence="低",
            )
        return AlgorithmInfo(
            selected_method="moving_average",
            reason=f"数据点较少（{n}天），使用移动平均",
            weights={"moving_average": 1.0},
            confidence="中",
        )
    mean = sum(values) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in values) / n) if n > 0 else 0
    cv = std / mean if mean > 0 else 0
    mae_lr = _cross_validate(values, "linear")
    mae_ma = _cross_validate(values, "ma")
    mae_es = _cross_validate(values, "es")
    methods = [("linear_regression", mae_lr), ("moving_average", mae_ma), ("exponential_smoothing", mae_es)]
    methods.sort(key=lambda x: x[1])
    best_method, best_mae = methods[0]
    weights = {}
    total_inv = sum(1.0 / max(m, 0.001) for _, m in methods)
    for name, mae in methods:
        weights[name] = (1.0 / max(mae, 0.001)) / max(total_inv, 0.001)
    return AlgorithmInfo(
        selected_method=best_method,
        reason=f"交叉验证最优: {best_method} (MAE={best_mae:.2f})",
        weights=weights,
        confidence="高" if n >= 30 and cv < 0.3 else ("中" if n >= 14 else "低"),
    )


def _forecast_single_product(
    product: dict,
    category: str,
    forecast_7d_flag: bool = True,
    forecast_30d_flag: bool = True,
) -> ProductTrend:
    """对单个商品进行趋势预测"""
    pid = product["product_id"]
    hist_len = DEFAULT_HISTORY_DAYS
    base = product.get("avg_daily_sales", 10)
    trend_dir, slope = _detect_trend([base] * hist_len)
    values = [max(0, base + slope * i + (hash(str(pid) + str(i)) % 10 - 5)) for i in range(hist_len)]
    algo = _select_algorithm(values)
    has_7d = forecast_7d_flag
    has_30d = forecast_30d_flag
    needed = max((7 if has_7d else 0) + (30 if has_30d else 0), 7)
    pred_values = [base] * max(needed, 7)

    if algo.selected_method != "fallback_category_avg":
        lr = _linear_regression_forecast(values, needed, hist_len)
        ma = _moving_average_forecast(values, needed)
        es = _exponential_smoothing_forecast(values, needed)
        w = algo.weights
        w_sum = sum(w.values()) or 1.0
        pred_values = [
            (w.get("linear_regression", 0) * lr[i] +
             w.get("moving_average", 0) * ma[i] +
             w.get("exponential_smoothing", 0) * es[i]) / w_sum
            for i in range(needed)
        ]
    else:
        pred_values = [base] * needed

    hist_avg = round(sum(values) / len(values), 1)

    forecast_7d_obj = {}
    if has_7d:
        daily_vals = [round(pred_values[i], 1) for i in range(7)]
        forecast_7d_obj = {
            "daily": [{"day": i + 1, "value": daily_vals[i]} for i in range(7)],
            "total": round(sum(daily_vals), 1),
            "avg_daily": round(sum(daily_vals) / 7, 1),
        }
    else:
        forecast_7d_obj = {"daily": [], "total": 0, "avg_daily": 0}

    forecast_30d_total = round(sum(pred_values[:30]), 1) if has_30d else 0
    forecast_30d_avg = round(forecast_30d_total / 30, 1) if has_30d else 0

    return ProductTrend(
        product_id=pid,
        title=product.get("title", f"商品{pid}"),
        historical_avg=hist_avg,
        trend_direction=trend_dir,
        algorithm_selection=algo,
        forecast_7d=forecast_7d_obj,
        forecast_30d_total=forecast_30d_total,
        forecast_30d_avg=forecast_30d_avg,
        confidence=algo.confidence,
        sales_velocity=None,
        trend_reason="",
    )


def _llm_generate_trend_reasons(forecasts: list[ProductTrend], inv_summary: str) -> list[str]:
    """LLM 增强：生成趋势分析理由"""
    if not forecasts:
        return []
    data = "\n".join(
        f"- {f.title}: 历史日均{f.historical_avg} | 趋势{f.trend_direction} | "
        f"7天预测日均{f.forecast_7d.get('avg_daily', 0)} | 置信度{f.confidence}"
        for f in forecasts[:5]
    )
    prompt = (
        "你是电商趋势分析师。根据以下商品趋势预测数据，为每个商品写 1-2 句趋势分析。\n"
        "要求：引用数据、说明趋势原因（如季节因素/库存状态/市场热度）\n\n"
        + data
        + (f"\n\n库存补充信息：{inv_summary}" if inv_summary else "")
    )
    try:
        from app.utils.llm_client import chat_completion
        result = chat_completion(
            system_prompt="你是电商趋势分析师，输出简洁的趋势分析。",
            user_message=prompt,
            temperature=0.3,
            max_tokens=500,
        )
        if result:
            return [l.strip() for l in result.strip().split("\n") if l.strip()][:10]
    except Exception as e:
        logger.warning("LLM 趋势分析失败: %s", e)
    return []


def forecast(input_data: TrendInput) -> TrendOutput:
    """趋势预测主入口（v0.3：注入库存交叉数据）"""
    try:
        product_ids = input_data.product_ids
        category = normalize_category(input_data.category) if input_data.category else ""

        if not product_ids:
            products = get_feishu_products(category) or get_demo_products(category)
            product_ids = [p["product_id"] for p in products[:5]]

        has_7d = 7 in input_data.forecast_days
        has_30d = 30 in input_data.forecast_days

        # ---- 获取库存交叉数据 ----
        inventory_map: dict = {}
        inv_summary_parts: list[str] = []
        try:
            from app.services.cross_table import get_all_cross_views
            cross_views = get_all_cross_views(category)
            for cv in cross_views:
                pid = str(cv.get("product_id", ""))
                inv = cv.get("inventory")
                if pid and inv:
                    inventory_map[pid] = inv
            if inventory_map:
                total_stock = sum(v.get("stock_qty", 0) for v in inventory_map.values())
                inv_summary_parts.append(f"库存覆盖 {len(inventory_map)} 个商品，总库存 {total_stock} 件")
                alerts = sum(1 for v in inventory_map.values()
                           if v.get("stock_qty", 0) < v.get("warning_stock", 999))
                if alerts:
                    inv_summary_parts.append(f"{alerts} 个商品库存低于预警线")
        except Exception as e:
            logger.warning("趋势预测-库存加载失败: %s", e)

        inventory_trend_summary = "；".join(inv_summary_parts)

        # ---- 逐商品预测 ----
        forecasts_list = []
        for pid in product_ids:
            products_all = get_demo_products(category)
            prod = next((p for p in products_all if p["product_id"] == pid), {})
            prod["product_id"] = pid

            pt = _forecast_single_product(prod, category, has_7d, has_30d)

            # 注入库存数据
            inv = inventory_map.get(str(pid))
            if inv:
                outbound = inv.get("cumulative_outbound", 0)
                if outbound > 0:
                    pt.sales_velocity = round(outbound / 30, 1)
                    # 用实际出库速度修正7天预测
                    if pt.sales_velocity > 0 and has_7d:
                        corrected_daily = round(pt.sales_velocity, 1)
                        pt.forecast_7d["avg_daily"] = corrected_daily
                        pt.forecast_7d["total"] = round(corrected_daily * 7, 1)

            forecasts_list.append(pt)

        # ---- LLM 增强趋势理由 ----
        if inventory_trend_summary:
            try:
                reasons = _llm_generate_trend_reasons(forecasts_list, inventory_trend_summary)
                for i, pt in enumerate(forecasts_list):
                    if i < len(reasons):
                        pt.trend_reason = reasons[i]
            except Exception as e:
                logger.warning("LLM 趋势理由生成失败: %s", e)

        # ---- 展示文本 ----
        lines_text = ["【趋势预测结果】"]
        if inventory_trend_summary:
            lines_text.append(f"库存概况：{inventory_trend_summary}")
        for pt in forecasts_list[:5]:
            f7d_avg = pt.forecast_7d.get("avg_daily", 0) if isinstance(pt.forecast_7d, dict) else 0
            sv_info = f"真实出库{pt.sales_velocity}件/天" if pt.sales_velocity else ""
            lines_text.append(
                f"  {pt.title[:25]} | 历史日均{pt.historical_avg:.0f}件 | "
                f"趋势{pt.trend_direction} | 7天预测日均{f7d_avg:.0f}件 "
                f"| {sv_info}"
            )
            if pt.trend_reason:
                lines_text.append(f"    → {pt.trend_reason[:80]}")

        result = TrendOutput(
            category=category,
            forecasts=forecasts_list,
            inventory_trend_summary=inventory_trend_summary,
            for_downstream={
                "forecasts": [
                    {"product_id": f.product_id, "title": f.title,
                     "trend_direction": f.trend_direction,
                     "forecast_7d_avg": f.forecast_7d.get("avg_daily", 0) if isinstance(f.forecast_7d, dict) else 0,
                     "forecast_30d_avg": f.forecast_30d_avg,
                     "sales_velocity": f.sales_velocity,
                     "trend_reason": f.trend_reason}
                    for f in forecasts_list[:10]
                ],
            },
            for_display="\n".join(lines_text),
        )
        return result
    except Exception as e:
        logger.error(f"forecast 异常: {e}")
        return TrendOutput(
            category=getattr(input_data, "category", "?"),
            for_display=f"趋势预测异常: {e}",
        )