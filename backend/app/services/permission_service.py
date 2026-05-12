from sqlalchemy.orm import Session

from app.models import Customer, Project, User


def can_access_customer(db: Session, user: User, customer: Customer) -> bool:
    if user.role == "admin":
        return True
    if customer.owner_user_id == user.id:
        return True
    return any(project.owner_user_id == user.id for project in db.query(Project).filter(Project.customer_id == customer.id).all())


def can_access_project(db: Session, user: User, project: Project) -> bool:
    if user.role == "admin":
        return True
    if project.owner_user_id == user.id:
        return True
    customer = db.get(Customer, project.customer_id)
    return customer is not None and customer.owner_user_id == user.id
