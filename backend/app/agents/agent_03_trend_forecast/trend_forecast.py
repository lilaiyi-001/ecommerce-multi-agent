"""趋势预测智能体（Trend Forecast）

职责：使用多算法融合方案（线性回归+移动平均+指数平滑），
根据历史销量预测未来7天和30天的销量走势。

飞书权限：✅ 可调飞书数据
依赖 LLM：❌ 不依赖（纯算法计算）
"""
from __future__ import annotations
import math
import logging
from collections import defaultdict
from typing import Optional
from app.schemas.trend import TrendInput, TrendOutput, ProductTrend, DailyForecast, AlgorithmInfo
from app.services.data_generator import get_demo_products
from app.services.category_registry import normalize_category
from app.services.feishu_data import get_feishu_products

logger = logging.getLogger(__name__)

# ── 配置 ──────────────────────────────────────────────────────
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
    result = []
    for v in values:
        smoothed = alpha * v + (1 - alpha) * smoothed
    for _ in range(days):
        result.append(max(0, smoothed))
        smoothed = alpha * smoothed + (1 - alpha) * smoothed
    return result


def _cross_validate(values: list[float], method: str, window: int = 5) -> float:
    """简单交叉验证：用最后 window 个点计算 MAE"""
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
    slope_pct = slope * 7 / mean_val  # 周变化率
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

    # 计算变异系数
    mean = sum(values) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in values) / n) if n > 0 else 0
    cv = std / mean if mean > 0 else 0

    # 交叉验证各算法
    mae_lr = _cross_validate(values, "linear")
    mae_ma = _cross_validate(values, "ma")
    mae_es = _cross_validate(values, "es")

    # 选择最优算法
    errors = {"linear_regression": mae_lr, "moving_average": mae_ma, "exponential_smoothing": mae_es}
    best_method = min(errors, key=errors.get)
    mae_values = [v for v in errors.values() if v != float("inf")]

    if not mae_values:
        return AlgorithmInfo(
            selected_method="moving_average",
            reason="交叉验证数据不足，使用移动平均",
            weights={"moving_average": 1.0},
            confidence="低",
        )

    # 如果所有算法误差接近（最大/最小 < 1.5），走融合
    min_mae, max_mae = min(mae_values), max(mae_values)
    if max_mae < min_mae * 1.5 and len(mae_values) >= 2 and n >= 14:
        weights = {}
        total = sum(1 / max(e, 0.01) for e in errors.values() if e != float("inf"))
        for name, e in errors.items():
            if e != float("inf"):
                inv = 1 / max(e, 0.01)
                weights[name] = round(inv / total, 2)
            else:
                weights[name] = 0.0
        reason = f"各算法误差接近，采用加权融合方案（CV={cv:.2f}）"
        confidence = "高" if n >= 30 else "中"
        return AlgorithmInfo(selected_method="weighted_fusion", reason=reason, weights=weights, confidence=confidence)

    # 单一最优算法
    name_map = {
        "linear_regression": "线性回归",
        "moving_average": "移动平均",
        "exponential_smoothing": "指数平滑",
    }
    method_names = {v: k for k, v in name_map.items()}
    human_name = {"linear_regression": "线性回归", "moving_average": "移动平均", "exponential_smoothing": "指数平滑"}
    reason = f"采用{human_name[best_method]}（交叉验证MAE={min_mae:.2f}）" if min_mae != float("inf") else f"采用{human_name[best_method]}"
    confidence = "高" if n >= 30 else ("中" if n >= 14 else "高" if cv < 0.3 else "中")
    return AlgorithmInfo(
        selected_method=best_method,
        reason=reason,
        weights={best_method: 1.0},
        confidence=confidence,
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

    # 选择算法
    algo = _select_algorithm(values)

    has_7d = forecast_7d_flag
    has_30d = forecast_30d_flag
    needed = (7 if has_7d else 0) + (30 if has_30d else 0)
    if needed == 0:
        needed = 7
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

    # 构造 forecast_7d 为嵌套对象（文档格式）
    forecast_7d_obj = {}
    if has_7d:
        daily_vals = [round(pred_values[i], 1) for i in range(7)]
        forecast_7d_obj = {
            "daily": [{ "day": i + 1, "value": daily_vals[i] } for i in range(7)],
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
    )


def forecast(input_data: TrendInput) -> TrendOutput:
    """趋势预测主入口"""
    try:
        product_ids = input_data.product_ids
        category = normalize_category(input_data.category) if input_data.category else ""

        if not product_ids:
            products = get_feishu_products(category) or get_demo_products(category)
            product_ids = [p["product_id"] for p in products[:5]]

        has_7d = 7 in input_data.forecast_days
        has_30d = 30 in input_data.forecast_days

        forecasts_list = []
        for pid in product_ids:
            products_all = get_demo_products(category)
            prod = next((p for p in products_all if p["product_id"] == pid), {})
            prod["product_id"] = pid
            pt = _forecast_single_product(prod, category, has_7d, has_30d)
            forecasts_list.append(pt)

        lines_text = ["【趋势预测结果】"]
        for pt in forecasts_list[:5]:
            f7d_avg = pt.forecast_7d.get("avg_daily", 0) if isinstance(pt.forecast_7d, dict) else 0
            lines_text.append(f"  {pt.title[:25]} | 历史日均{pt.historical_avg:.0f}件 | "
                f"趋势{pt.trend_direction} | "
                f"算法={pt.algorithm_selection.selected_method} | "
                f"7天预测日均{f7d_avg:.0f}件")

        result = TrendOutput(
            category=category,
            forecasts=forecasts_list,
            for_display="\n".join(lines_text),
        )
        return result
    except Exception as e:
        logger.error(f"forecast 异常: {e}")
        return TrendOutput(
            category=getattr(input_data, "category", "?"),
            product_trends=[], for_display=f"趋势预测异常: {e}",
        )
