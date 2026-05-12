import re
from datetime import date, datetime, timedelta

from app.schemas.agent_tools import ExtractedProjectUpdate, NextActionDraft


def _next_weekday(base: date, weekday: int) -> date:
    days = (weekday - base.weekday()) % 7
    if days == 0:
        days = 7
    return base + timedelta(days=days)


def _parse_due_date(text: str, message_time: datetime) -> date | None:
    if "下周一" in text:
        return _next_weekday(message_time.date(), 0)
    if "下周二" in text:
        return _next_weekday(message_time.date(), 1)
    if "下周三" in text:
        return _next_weekday(message_time.date(), 2)
    if "下周四" in text:
        return _next_weekday(message_time.date(), 3)
    if "下周五" in text:
        return _next_weekday(message_time.date(), 4)
    if "明天" in text:
        return message_time.date() + timedelta(days=1)
    match = re.search(r"(20\d{2})[-年](\d{1,2})[-月](\d{1,2})", text)
    if match:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return None


def extract_project_update(text: str, message_time: datetime) -> ExtractedProjectUpdate:
    customer_match = re.search(r"(?:今天|昨日|昨天|记录一下：|记录一下)?([\u4e00-\u9fa5A-Za-z0-9]+)项目", text)
    raw_customer_name = customer_match.group(1) if customer_match else None
    if raw_customer_name:
        for prefix in ("记录一下：今天", "记录一下:", "记录一下：", "今天", "昨日", "昨天"):
            raw_customer_name = raw_customer_name.removeprefix(prefix)
    project_name = f"{raw_customer_name}项目" if raw_customer_name else None
    customer_name = raw_customer_name

    due_date = _parse_due_date(text, message_time)
    next_actions: list[NextActionDraft] = []
    if "导入模板" in text:
        next_actions.append(NextActionDraft(title="准备商品主数据导入模板", due_date=due_date))

    summary = text.strip("。")
    if "客户确认" in text:
        summary = text.split("客户确认", 1)[1].strip("。")

    missing_fields = []
    if not project_name:
        missing_fields.append("project_id")
    if next_actions and not next_actions[0].owner_hint:
        missing_fields.append("task_owner_user_id")

    return ExtractedProjectUpdate(
        customer_name=customer_name,
        project_name=project_name,
        title="项目进展更新",
        summary=summary,
        detail=text,
        event_time=message_time,
        next_actions=next_actions,
        risks=[],
        missing_fields=missing_fields,
        confidence=0.86 if project_name else 0.55,
    )
