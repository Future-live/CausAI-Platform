import json
import logging

from fastapi import HTTPException, status
from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.analysis import AnalysisJob
from app.models.user import User
from app.schemas.causal import BackgroundEdge, CausalEdge
from app.schemas.llm import (
    AnalyzeResultRequest,
    AnalyzeResultResponse,
    BackdoorAdjustmentRequest,
    BackdoorAdjustmentResponse,
    OrientedGraphResponse,
)
from app.services.causal import get_job_result

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = (
            OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
            if settings.deepseek_api_key
            else None
        )

    @property
    def configured(self) -> bool:
        return self.client is not None

    def _completion(self, prompt: str, system: str) -> str:
        if not self.client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="语义理解功能未配置 DEEPSEEK_API_KEY",
            )
        try:
            response = self.client.chat.completions.create(
                model=self.settings.deepseek_model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                stream=False,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.exception("LLM request failed")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="大模型服务请求失败") from exc

    @staticmethod
    def _parse_json(content: str) -> dict:
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:-3].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:-3].strip()
        return json.loads(cleaned)

    def orient_edges(self, db: Session, user: User, job_id: str) -> OrientedGraphResponse:
        result = get_job_result(db, user, job_id)
        undirected = [
            edge
            for edge in result.edges
            if edge.endpoint1.upper() == "TAIL" and edge.endpoint2.upper() == "TAIL"
        ]
        directed = [
            BackgroundEdge(source=edge.node1, target=edge.node2)
            for edge in result.edges
            if edge.endpoint1.upper() == "TAIL" and edge.endpoint2.upper() == "ARROW"
        ]
        if not undirected:
            return OrientedGraphResponse(nodes=result.nodes, edges=directed, configured=self.configured)
        if not self.configured:
            return OrientedGraphResponse(nodes=result.nodes, edges=directed, configured=False)

        prompt = f"""
请基于变量名称和因果推断上下文，为以下无向边判断更合理的方向。
变量列表：{result.nodes}
已有有向边：{[edge.model_dump() for edge in directed]}
待定无向边：{[edge.model_dump() for edge in undirected]}

只返回 JSON：{{"edges":[{{"source":"变量A","target":"变量B"}}]}}
"""
        content = self._completion(prompt, "你是严谨的因果推断专家，只输出合法 JSON。")
        try:
            payload = self._parse_json(content)
            oriented = [BackgroundEdge(**edge) for edge in payload.get("edges", [])]
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="大模型返回格式无效") from exc
        return OrientedGraphResponse(nodes=result.nodes, edges=[*directed, *oriented], configured=True)

    def backdoor_adjustment(self, payload: BackdoorAdjustmentRequest) -> BackdoorAdjustmentResponse:
        if not self.configured:
            return BackdoorAdjustmentResponse(adjustment_set=[], configured=False)
        prompt = f"""
变量列表：{payload.nodes}
因果边：{[edge.model_dump() for edge in payload.edges]}
处理变量：{payload.cause_var}
结果变量：{payload.effect_var}

请依据后门准则返回最小调整集。只返回 JSON：
{{"adjustment_set":["变量名"]}}
"""
        content = self._completion(prompt, "你是遵循 Judea Pearl 后门准则的专家，只输出合法 JSON。")
        try:
            result = self._parse_json(content)
            adjustment_set = result.get("adjustment_set", [])
            if not isinstance(adjustment_set, list):
                adjustment_set = []
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="大模型返回格式无效") from exc
        return BackdoorAdjustmentResponse(adjustment_set=[str(item) for item in adjustment_set])

    def analyze_result(self, db: Session, user: User, payload: AnalyzeResultRequest) -> AnalyzeResultResponse:
        if not self.configured:
            return AnalyzeResultResponse(analysis="语义理解功能未配置 DEEPSEEK_API_KEY。", configured=False)
        result = get_job_result(db, user, payload.job_id)
        prompt = payload.prompt or "请分析这些因果关系，并给出业务解释、风险和下一步验证建议。"
        content = self._completion(
            f"{prompt}\n\n节点：{result.nodes}\n边：{[edge.model_dump() for edge in result.edges]}",
            "你是专业的因果推理分析专家，输出中文、结构清晰、避免夸大结论。",
        )
        return AnalyzeResultResponse(analysis=content, configured=True)


def get_llm_service(settings: Settings) -> LLMService:
    return LLMService(settings)
