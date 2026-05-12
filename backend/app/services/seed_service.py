from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, Project, User, UserChannelBinding


def seed_demo_data(db: Session) -> dict[str, str]:
    user = db.scalar(select(User).where(User.id == "user-demo"))
    if user is None:
        user = User(id="user-demo", name="演示用户", email="demo@example.com", role="project_owner")
        db.add(user)

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

    db.commit()
    return {
        "user_id": "user-demo",
        "customer_id": "customer-demo",
        "project_id": "project-demo",
    }
