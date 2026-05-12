from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_actor
from app.core.auth import require_agent_tool_api_key
from app.db.session import get_db
from app.models import Customer, User
from app.schemas.business import CustomerCreate, CustomerList, CustomerRead
from app.services.permission_service import can_access_customer

router = APIRouter(prefix="/api/customers", tags=["customers"], dependencies=[Depends(require_agent_tool_api_key)])


def _read_customer(customer: Customer) -> CustomerRead:
    return CustomerRead(
        id=customer.id,
        name=customer.name,
        aliases=customer.aliases,
        industry=customer.industry,
        level=customer.level,
        status=customer.status,
        owner_user_id=customer.owner_user_id,
        contact_name=customer.contact_name,
        contact_phone=customer.contact_phone,
        contact_email=customer.contact_email,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )


@router.get("", response_model=CustomerList)
def list_customers(
    query: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_actor),
) -> CustomerList:
    rows = db.scalars(select(Customer).where(Customer.status == "active")).all()
    items = [
        _read_customer(customer)
        for customer in rows
        if can_access_customer(db, user, customer)
        and (not query or query.lower() in customer.name.lower() or any(query.lower() in alias.lower() for alias in customer.aliases))
    ]
    return CustomerList(items=items)


@router.post("", response_model=CustomerRead)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_actor),
) -> CustomerRead:
    customer = Customer(
        name=payload.name,
        industry=payload.industry,
        level=payload.level,
        status=payload.status,
        owner_user_id=payload.owner_user_id or user.id,
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
        contact_email=payload.contact_email,
    )
    customer.aliases = payload.aliases
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return _read_customer(customer)

