from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, KnowledgeDocument, Project, User, UserChannelBinding
from app.services.knowledge_service import ingest_document


def seed_demo_data(db: Session) -> dict[str, str]:
    user = db.scalar(select(User).where(User.id == "user-demo"))
    if user is None:
        user = User(id="user-demo", name="演示用户", email="demo@example.com", role="project_owner", knowledge_access_policy="all")
        db.add(user)
    else:
        user.knowledge_access_policy = "all"

    for channel in ("openclaw", "feishu", "webchat"):
        binding = db.scalar(
            select(UserChannelBinding).where(
                UserChannelBinding.channel == channel,
                UserChannelBinding.external_user_id == "unknown",
            )
        )
        if binding is None:
            db.add(UserChannelBinding(user_id="user-demo", channel=channel, external_user_id="unknown"))

    customer = db.scalar(select(Customer).where(Customer.id == "customer-demo"))
    if customer is None:
        customer = Customer(id="customer-demo", name="恒润集团", owner_user_id="user-demo")
        customer.aliases = ["恒润"]
        db.add(customer)

    project = db.scalar(select(Project).where(Project.id == "project-demo"))
    if project is None:
        project = Project(
            id="project-demo",
            customer_id="customer-demo",
            name="恒润 PIM 项目",
            stage="需求沟通",
            owner_user_id="user-demo",
        )
        project.aliases = ["恒润项目", "恒润PIM"]
        db.add(project)

    support_customer = db.scalar(select(Customer).where(Customer.id == "customer-ecommerce-demo"))
    if support_customer is None:
        support_customer = Customer(id="customer-ecommerce-demo", name="电商售后演示客户", industry="电商", owner_user_id="user-demo")
        support_customer.aliases = ["电商售后", "售后演示"]
        db.add(support_customer)

    support_case = db.scalar(select(Project).where(Project.id == "case-ecommerce-demo"))
    if support_case is None:
        support_case = Project(
            id="case-ecommerce-demo",
            customer_id="customer-ecommerce-demo",
            name="电商售后常见问题",
            stage="知识运营",
            owner_user_id="user-demo",
        )
        support_case.aliases = ["退款退货", "物流发票", "投诉处理"]
        db.add(support_case)

    db.commit()
    _seed_ecommerce_support_knowledge(db)
    return {
        "user_id": "user-demo",
        "customer_id": "customer-demo",
        "project_id": "project-demo",
        "support_customer_id": "customer-ecommerce-demo",
        "support_case_id": "case-ecommerce-demo",
    }


def _seed_ecommerce_support_knowledge(db: Session) -> None:
    examples = [
        ("订单未发货怎么退款", "订单未发货时，客服先核对订单状态。如未出库，可引导客户在订单页申请退款，系统通常原路退回。"),
        ("物流丢件怎么办", "物流疑似丢件时，客服先记录快递单号并联系快递核实。确认丢件后可为客户补发或退款，并同步处理时效。"),
        ("发票抬头写错了怎么办", "发票抬头错误时，客服需核对订单号、正确抬头和税号。未开票可直接修改，已开票需作废后重开。"),
        ("超过七天还能退货吗", "超过七天通常不支持无理由退货。若商品质量问题，客服应收集照片或视频凭证后按售后政策处理。"),
        ("客户投诉态度强烈怎么处理", "遇到强烈投诉时，客服先致歉并复述问题，明确处理时限；涉及金额或舆情风险时升级主管。"),
    ]
    for question, answer in examples:
        exists = db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.title == question))
        if exists:
            continue
        ingest_document(
            db,
            payload={
                "title": question,
                "summary": answer[:120],
                "content_text": f"问题：{question}\n答案：{answer}",
                "source_type": "ecommerce_demo",
                "customer_id": "customer-ecommerce-demo",
                "project_id": "case-ecommerce-demo",
            },
            user_id="user-demo",
        )
