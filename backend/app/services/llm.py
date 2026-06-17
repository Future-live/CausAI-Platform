import json
import logging
from typing import Any

import networkx as nx
from fastapi import HTTPException, status
from openai import OpenAI
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.models.dataset import DatasetVersion
from app.models.user import User
from app.schemas.causal import BackgroundEdge
from app.schemas.llm import (
    AnalyzeResultRequest,
    AnalyzeResultResponse,
    BackdoorAdjustmentRequest,
    BackdoorAdjustmentResponse,
    EdgeOrientationEvidence,
    GraphValidation,
    LLMProviderConfig,
    OrientedGraphResponse,
    SemanticColumnProfile,
    SemanticProfileResponse,
)
from app.services.causal import get_job_result
from app.services.dataframe import json_safe, read_dataframe

logger = logging.getLogger(__name__)


ROLE_HINTS = {
    "id": "identifier",
    "编号": "identifier",
    "time": "time",
    "date": "time",
    "日期": "time",
    "score": "outcome",
    "成绩": "outcome",
    "result": "outcome",
    "outcome": "outcome",
    "target": "outcome",
    "treatment": "treatment",
    "干预": "treatment",
    "group": "confounder",
    "分组": "confounder",
}


class LLMService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _runtime_config(self, config: LLMProviderConfig | None = None) -> tuple[str, str, str]:
        api_key = (config.api_key if config else None) or self.settings.deepseek_api_key
        base_url = (config.base_url if config else None) or self.settings.deepseek_base_url
        model = (config.model if config else None) or self.settings.deepseek_model
        return api_key or "", base_url, model

    def configured(self, config: LLMProviderConfig | None = None) -> bool:
        api_key, _, _ = self._runtime_config(config)
        return bool(api_key)

    def _client(self, config: LLMProviderConfig | None = None) -> OpenAI | None:
        api_key, base_url, _ = self._runtime_config(config)
        if not api_key:
            return None
        return OpenAI(api_key=api_key, base_url=base_url)

    def _completion(self, prompt: str, system: str, config: LLMProviderConfig | None = None) -> str:
        client = self._client(config)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="语义理解功能未配置 API Key",
            )
        _, _, model = self._runtime_config(config)
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                temperature=0.1,
                stream=False,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.exception("LLM request failed")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="大模型服务请求失败") from exc

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end >= start:
            cleaned = cleaned[start : end + 1]
        return json.loads(cleaned)

    @staticmethod
    def _fallback_role(name: str, semantic_type: str) -> str:
        lowered = name.lower()
        for token, role in ROLE_HINTS.items():
            if token in lowered or token in name:
                return role
        if semantic_type == "datetime":
            return "time"
        if semantic_type == "categorical":
            return "confounder"
        return "feature"

    def _version_for_user(self, db: Session, user: User, version_id: str) -> DatasetVersion:
        version = db.scalar(
            select(DatasetVersion)
            .options(selectinload(DatasetVersion.dataset))
            .where(DatasetVersion.id == version_id)
        )
        if not version or version.dataset.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据版本不存在")
        return version

    def semantic_profile(
        self,
        db: Session,
        user: User,
        version_id: str,
        config: LLMProviderConfig | None = None,
    ) -> SemanticProfileResponse:
        version = self._version_for_user(db, user, version_id)
        df = read_dataframe(version.storage_path)
        base_profiles: list[SemanticColumnProfile] = []
        for column in version.columns_json:
            name = str(column["name"])
            sample_values = [
                str(json_safe(value))
                for value in df[name].dropna().head(6).tolist()
                if json_safe(value) is not None
            ] if name in df.columns else []
            semantic_type = str(column.get("semantic_type") or "")
            analysis_type = str(column.get("analysis_type") or "")
            role = self._fallback_role(name, semantic_type)
            base_profiles.append(
                SemanticColumnProfile(
                    name=name,
                    dtype=str(column.get("dtype") or ""),
                    analysis_type=analysis_type,
                    semantic_type=semantic_type,
                    missing_count=int(column.get("missing_count") or 0),
                    unique_count=int(column.get("unique_count") or 0),
                    sample_values=sample_values,
                    inferred_role=role,
                    description=f"根据字段名、类型和样例值推断为 {role}。",
                    evidence=[
                        f"类型: {semantic_type or analysis_type or 'unknown'}",
                        f"唯一值: {column.get('unique_count', 0)}",
                    ],
                    quality_warnings=["缺失值较多"] if int(column.get("missing_count") or 0) > 0 else [],
                )
            )

        if not self.configured(config):
            return SemanticProfileResponse(
                configured=False,
                summary="当前未配置大模型，已展示基于字段类型和样例值的本地语义画像。",
                columns=base_profiles,
                warnings=["未配置 API Key，LLM 语义增强未启用。"],
            )

        prompt = f"""
请根据字段名、数据类型、样例值和统计信息，为数据集生成字段语义画像。
字段资料：
{json.dumps([profile.model_dump() for profile in base_profiles], ensure_ascii=False)}

只返回 JSON，格式如下：
{{
  "summary": "一句话总结数据集语义",
  "columns": [
    {{
      "name": "字段名",
      "description": "字段业务含义",
      "inferred_role": "treatment|outcome|confounder|mediator|collider|identifier|time|feature|unknown",
      "unit": "单位或 null",
      "evidence": ["判断依据"],
      "quality_warnings": ["风险或空数组"]
    }}
  ],
  "warnings": ["整体风险或空数组"]
}}
"""
        content = self._completion(prompt, "你是数据语义建模和因果分析专家，只输出合法 JSON。", config)
        try:
            payload = self._parse_json(content)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="大模型字段画像返回格式无效") from exc

        llm_columns = {str(item.get("name")): item for item in payload.get("columns", []) if isinstance(item, dict)}
        merged: list[SemanticColumnProfile] = []
        for base in base_profiles:
            item = llm_columns.get(base.name, {})
            try:
                merged.append(
                    base.model_copy(
                        update={
                            "description": str(item.get("description") or base.description),
                            "inferred_role": str(item.get("inferred_role") or base.inferred_role),
                            "unit": item.get("unit") or base.unit,
                            "evidence": [str(value) for value in item.get("evidence", base.evidence) or []],
                            "quality_warnings": [
                                str(value) for value in item.get("quality_warnings", base.quality_warnings) or []
                            ],
                        }
                    )
                )
            except ValidationError:
                merged.append(base)

        return SemanticProfileResponse(
            configured=True,
            summary=str(payload.get("summary") or "字段语义画像已生成。"),
            columns=merged,
            warnings=[str(value) for value in payload.get("warnings", []) if value],
        )

    @staticmethod
    def _validation(nodes: list[str], edges: list[BackgroundEdge]) -> GraphValidation:
        known = set(nodes)
        accepted: list[BackgroundEdge] = []
        unknown: list[BackgroundEdge] = []
        rejected: list[BackgroundEdge] = []
        for edge in edges:
            if edge.source not in known or edge.target not in known:
                unknown.append(edge)
            elif edge.source == edge.target:
                rejected.append(edge)
            else:
                accepted.append(edge)

        graph = nx.DiGraph()
        graph.add_nodes_from(nodes)
        graph.add_edges_from((edge.source, edge.target) for edge in accepted)
        cycles = [list(cycle) for cycle in nx.simple_cycles(graph)]
        warnings: list[str] = []
        if unknown:
            warnings.append("存在不在变量列表中的边，已标记为未知边。")
        if cycles:
            warnings.append("有向图存在环，建议人工复核方向。")
        return GraphValidation(
            is_dag=not cycles,
            cycles=cycles,
            unknown_edges=unknown,
            rejected_edges=rejected,
            warnings=warnings,
        )

    @staticmethod
    def _directed_edges_from_result(result_edges: list[Any]) -> list[BackgroundEdge]:
        return [
            BackgroundEdge(source=edge.node1, target=edge.node2)
            for edge in result_edges
            if edge.endpoint1.upper() == "TAIL" and edge.endpoint2.upper() == "ARROW"
        ]

    def orient_edges(self, db: Session, user: User, job_id: str, config: LLMProviderConfig | None = None) -> OrientedGraphResponse:
        result = get_job_result(db, user, job_id)
        undirected = [
            edge
            for edge in result.edges
            if edge.endpoint1.upper() == "TAIL" and edge.endpoint2.upper() == "TAIL"
        ]
        directed = self._directed_edges_from_result(result.edges)
        if not undirected or not self.configured(config):
            return OrientedGraphResponse(
                nodes=result.nodes,
                edges=directed,
                configured=self.configured(config),
                validation=self._validation(result.nodes, directed),
            )

        prompt = f"""
请基于变量名称、已有方向和因果推断常识，为无向边判断更合理的方向。
变量列表：{result.nodes}
已有有向边：{[edge.model_dump() for edge in directed]}
待定无向边：{[edge.model_dump() for edge in undirected]}

要求：
1. 只允许使用变量列表中的变量。
2. 每条边给出 confidence、rationale、evidence。
3. 如果依据不足，requires_review=true。
4. 只返回 JSON：
{{
  "edges": [
    {{"source":"变量A","target":"变量B","confidence":0.72,"rationale":"...","evidence":["..."],"requires_review":false}}
  ]
}}
"""
        content = self._completion(prompt, "你是严谨的因果推断专家，只输出合法 JSON。", config)
        try:
            payload = self._parse_json(content)
            evidence = [EdgeOrientationEvidence(**edge) for edge in payload.get("edges", [])]
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="大模型返回格式无效") from exc

        oriented = [BackgroundEdge(source=item.source, target=item.target) for item in evidence]
        edges = [*directed, *oriented]
        return OrientedGraphResponse(
            nodes=result.nodes,
            edges=edges,
            configured=True,
            orientation_evidence=evidence,
            validation=self._validation(result.nodes, edges),
        )

    def backdoor_adjustment(self, payload: BackdoorAdjustmentRequest) -> BackdoorAdjustmentResponse:
        validation = self._validation(payload.nodes, payload.edges)
        graph = nx.DiGraph()
        graph.add_nodes_from(payload.nodes)
        graph.add_edges_from((edge.source, edge.target) for edge in payload.edges if edge.source in payload.nodes and edge.target in payload.nodes)
        local_adjustment = sorted(item for item in graph.predecessors(payload.effect_var) if item != payload.cause_var) if payload.effect_var in graph else []

        if not self.configured(payload.llm_config):
            return BackdoorAdjustmentResponse(
                adjustment_set=local_adjustment,
                configured=False,
                rationale="当前未配置大模型，系统使用本地图结构规则：结果变量的直接父节点中排除处理变量。",
                evidence=[f"{payload.effect_var} 的父节点: {', '.join(local_adjustment) or '无'}"],
                validation=validation,
            )

        prompt = f"""
变量列表：{payload.nodes}
因果边：{[edge.model_dump() for edge in payload.edges]}
处理变量：{payload.cause_var}
结果变量：{payload.effect_var}
本地候选调整集：{local_adjustment}
图校验：{validation.model_dump()}

请依据 Pearl 后门准则返回最小调整集。只返回 JSON：
{{
  "adjustment_set":["变量名"],
  "rationale":"选择原因",
  "evidence":["依据"]
}}
"""
        content = self._completion(prompt, "你是遵循 Judea Pearl 后门准则的专家，只输出合法 JSON。", payload.llm_config)
        try:
            result = self._parse_json(content)
            adjustment_set = result.get("adjustment_set", [])
            if not isinstance(adjustment_set, list):
                adjustment_set = []
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="大模型返回格式无效") from exc
        known = set(payload.nodes)
        adjustment = sorted({str(item) for item in adjustment_set if str(item) in known and str(item) not in {payload.cause_var, payload.effect_var}})
        return BackdoorAdjustmentResponse(
            adjustment_set=adjustment,
            configured=True,
            rationale=str(result.get("rationale") or ""),
            evidence=[str(item) for item in result.get("evidence", []) if item],
            validation=validation,
        )

    def analyze_result(self, db: Session, user: User, payload: AnalyzeResultRequest) -> AnalyzeResultResponse:
        result = get_job_result(db, user, payload.job_id)
        if not self.configured(payload.llm_config):
            return AnalyzeResultResponse(
                analysis="语义理解功能未配置 API Key。请在页面的“模型连接”中填写模型 URL、名称和密钥后重试。",
                configured=False,
                warnings=["未配置 API Key。"],
            )
        prompt = payload.prompt or "请分析这些因果关系，并给出业务解释、风险和下一步验证建议。"
        field_context = [profile.model_dump() for profile in payload.field_profiles]
        validation = self._validation(result.nodes, self._directed_edges_from_result(result.edges))
        content = self._completion(
            f"""
{prompt}

节点：{result.nodes}
边：{[edge.model_dump() for edge in result.edges]}
字段语义画像：{json.dumps(field_context, ensure_ascii=False)}
图结构校验：{validation.model_dump()}

请输出中文，结构包含：关键结论、可能混杂因素、不能直接断言的部分、下一步验证建议。
""",
            "你是专业的因果推理分析专家，输出结构清晰，避免把相关性夸大成因果。",
            payload.llm_config,
        )
        return AnalyzeResultResponse(
            analysis=content,
            configured=True,
            evidence=["已结合因果图、字段语义画像和图结构校验生成。"],
            warnings=validation.warnings,
        )


def get_llm_service(settings: Settings) -> LLMService:
    return LLMService(settings)
