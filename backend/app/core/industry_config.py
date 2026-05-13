from dataclasses import dataclass


@dataclass(frozen=True)
class IndustryConfig:
    key: str
    title: str
    description: str
    labels: dict[str, str]
    table_labels: dict[str, str]
    related_labels: dict[str, str]
    knowledge_tags: tuple[str, ...]
    tool_description: str
    example_prompts: tuple[str, ...]


ENTERPRISE_CONFIG = IndustryConfig(
    key="enterprise",
    title="数据库记录看板",
    description="查看企业 AI 助手已经记录到业务数据库里的客户、项目、知识库和审计信息。",
    labels={
        "customer": "客户",
        "project": "项目",
        "knowledge_document": "知识文档",
        "knowledge_chunk": "知识切片",
        "audit_log": "审计日志",
    },
    table_labels={},
    related_labels={
        "documents": "知识文档",
        "chunks": "知识切片",
        "similar_cases": "相关项目",
        "audit_logs": "审计日志",
    },
    knowledge_tags=("客户资料", "项目资料", "会议纪要", "需求范围", "风险任务"),
    tool_description="记录和查询企业客户、项目、知识库和审计信息。",
    example_prompts=("记录客户资料", "查询项目进展", "根据知识库回答问题"),
)

SUPPORT_CONFIG = IndustryConfig(
    key="support",
    title="客服知识库看板",
    description="查看客服坐席知识助手记录的客户/账号、问题工单、知识文章、答案片段和查询记录。",
    labels={
        "customer": "客户/用户/账号",
        "project": "问题/工单",
        "knowledge_document": "知识文章",
        "knowledge_chunk": "答案片段",
        "audit_log": "查询/写入/回复建议记录",
    },
    table_labels={
        "customers": "客户/用户/账号",
        "projects": "问题/工单",
        "project_events": "处理进展",
        "project_tasks": "待处理任务",
        "project_risks": "升级风险",
        "knowledge_documents": "知识文章",
        "knowledge_chunks": "答案片段",
        "audit_logs": "查询/写入/回复建议记录",
        "support_unanswered_questions": "无答案问题",
        "confirmation_actions": "待确认写入",
    },
    related_labels={
        "documents": "相关知识文章",
        "chunks": "相关答案片段",
        "similar_cases": "历史相似问题",
        "audit_logs": "最近查询/写入记录",
    },
    knowledge_tags=("账号问题", "售后政策", "订单物流", "退款退货", "投诉升级", "标准话术"),
    tool_description="面向客服坐席记录客服知识、查询标准答案、生成建议回复并查看历史相似问题。",
    example_prompts=("记录这条客服知识", "客户登录失败怎么回复", "查询历史相似问题"),
)

INDUSTRY_CONFIGS = {
    ENTERPRISE_CONFIG.key: ENTERPRISE_CONFIG,
    SUPPORT_CONFIG.key: SUPPORT_CONFIG,
}


def get_industry_config(industry_key: str | None = None) -> IndustryConfig:
    normalized_key = (industry_key or ENTERPRISE_CONFIG.key).strip().lower()
    return INDUSTRY_CONFIGS.get(normalized_key, ENTERPRISE_CONFIG)


def serialize_industry_config(config: IndustryConfig) -> dict:
    return {
        "key": config.key,
        "title": config.title,
        "description": config.description,
        "labels": config.labels,
        "knowledge_tags": list(config.knowledge_tags),
        "tool_description": config.tool_description,
        "example_prompts": list(config.example_prompts),
    }
