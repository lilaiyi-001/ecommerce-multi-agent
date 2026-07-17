"""智能体注册中心 — 在应用启动时注册所有已实现的智能体"""
from __future__ import annotations
import logging
from app.agents.agent_01_orchestrator.orchestrator import register_agent

logger = logging.getLogger(__name__)


def register_all_agents():
    """注册所有已实现的智能体"""

    # Agent 2: 选品分析
    from app.agents.agent_02_product_selection.product_selection import analyze_products
    from app.schemas.selection import SelectionInput

    def handle_product_selection(input_data: dict) -> dict:
        sel_input = SelectionInput(**input_data)
        result = analyze_products(sel_input)
        return result.model_dump()

    register_agent("product_selection", handle_product_selection)

    logger.info("所有智能体注册完成")

    # Agent 3: 趋势预测
    from app.agents.agent_03_trend_forecast.trend_forecast import forecast
    from app.schemas.trend import TrendInput

    def handle_trend_forecast(input_data: dict) -> dict:
        trend_input = TrendInput(**input_data)
        result = forecast(trend_input)
        return result.model_dump()

    register_agent("trend_forecast", handle_trend_forecast)

    # Agent 5: 用户画像
    from app.agents.agent_05_user_profile.user_profile import analyze_profile
    from app.schemas.profile import ProfileInput

    def handle_user_profile(input_data: dict) -> dict:
        return analyze_profile(ProfileInput(**input_data)).model_dump()

    register_agent("user_profile", handle_user_profile)

    # Agent 4: 竞品分析
    from app.agents.agent_04_competitor_analysis.competitor_analysis import analyze_competitor
    from app.schemas.competitor import CompetitorInput

    def handle_competitor(input_data: dict) -> dict:
        return analyze_competitor(CompetitorInput(**input_data)).model_dump()

    register_agent("competitor_analysis", handle_competitor)

    # Agent 6: 定价策略
    from app.agents.agent_06_pricing_strategy.pricing_strategy import analyze_pricing
    from app.schemas.pricing import PricingInput

    def handle_pricing(input_data: dict) -> dict:
        return analyze_pricing(PricingInput(**input_data)).model_dump()

    register_agent("pricing_strategy", handle_pricing)

    # Agent 7: 营销文案
    from app.agents.agent_07_marketing_copy.marketing_copy import generate_copy
    from app.schemas.copy import CopyInput

    def handle_copy(input_data: dict) -> dict:
        return generate_copy(CopyInput(**input_data)).model_dump()

    register_agent("marketing_copy", handle_copy)

    # Agent 8: 补货/清仓
    from app.agents.agent_08_inventory_advice.inventory_advice import analyze_inventory
    from app.schemas.inventory import InventoryInput

    def handle_inventory(input_data: dict) -> dict:
        return analyze_inventory(InventoryInput(**input_data)).model_dump()

    register_agent("inventory_advice", handle_inventory)

    # Agent 9: 活动策划
    from app.agents.agent_09_promotion_plan.promotion_plan import create_plan
    from app.schemas.promotion import PromotionPlanInput

    def handle_promotion(input_data: dict) -> dict:
        return create_plan(PromotionPlanInput(**input_data)).model_dump()

    register_agent("promotion_plan", handle_promotion)
