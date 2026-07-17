"""集成测试 — 端到端编排 + LLM 降级"""
from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.agents.agent_01_orchestrator.orchestrator import orchestrate
from app.schemas.orchestrator import OrchestratorInput
from app.schemas.intent import IntentInput
from app.agents.agent_00_intent_recognizer.intent_recognizer import recognize_intent


def get_token(client):
    login = client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "admin123",
    })
    return login.json()["access_token"]


class TestIntegration:

    @patch("app.agents.agent_01_orchestrator.orchestrator.chat_completion")
    @patch("app.agents.agent_00_intent_recognizer.intent_recognizer.chat_completion")
    def test_full_chat_flow_with_mock_llm(self, mock_llm_intent, mock_llm_orch):
        """Mock LLM，验证 /api/v1/chat 全流程编排完成"""
        mock_llm_intent.return_value = '{"category": "电子产品", "top_n": 3, "action": "推荐爆款"}'
        mock_llm_orch.return_value = "分析完成"

        client = TestClient(app)
        token = get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post("/api/v1/chat", json={
            "user_message": "分析电子产品，推荐3个爆款",
            "session_id": "int_test_1",
            "turn_number": 1,
        }, headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert "intent_result" in data
        assert "orchestrator_result" in data

    def test_chat_flow_no_llm_pure_compute_only(self):
        """不依赖 LLM 的纯计算 Agent（A2/A3/A8）独立调用不中断"""
        client = TestClient(app)
        token = get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post("/api/v1/selection/analyze", json={
            "category": "电子产品", "top_n": 3,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "ranking" in data or "total_products" in data

    def test_chinese_category_works(self):
        """中文类目名能正常路由到数据"""
        client = TestClient(app)
        token = get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post("/api/v1/selection/analyze", json={
            "category": "电子产品", "top_n": 3,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("total_products", 0) > 0

    def test_llm_fallback_does_not_break(self):
        """LLM 返回空字符串时编排不中断"""
        with patch("app.agents.agent_01_orchestrator.orchestrator.chat_completion") as mock_llm:
            mock_llm.return_value = ""

            intent_input = IntentInput(
                user_message="分析电子产品",
                session_id="fallback_test",
                turn_number=1,
            )
            intent_result = recognize_intent(intent_input)

            orch_input = OrchestratorInput(
                intent_result=intent_result.model_dump(),
                session_id="fallback_test",
            )
            result = orchestrate(orch_input)
            report = result.final_report
            assert "summary" in report
