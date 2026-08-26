from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.permissions import CurrentActor
from app.db import get_session
from app.schemas.customer import (
    Attachment,
    ContactMethod,
    ContactMethodCreate,
    Customer,
    CustomerCreate,
    CustomerHistory,
    CustomerUpdate,
)
from app.services.customer_service import CustomerService

router = APIRouter(tags=["customers"])


@router.get("/customers", response_model=list[Customer], operation_id="listCustomers")
async def list_customers(
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = CustomerService(session, actor.scope)
    return await service.search(actor, q, limit=limit, offset=offset)


@router.post(
    "/customers", response_model=Customer, status_code=status.HTTP_201_CREATED, operation_id="createCustomer"
)
async def create_customer(
    data: CustomerCreate,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = CustomerService(session, actor.scope)
    return await service.create(actor, data)


@router.get("/customers/{id}", response_model=Customer, operation_id="getCustomer")
async def get_customer(
    id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = CustomerService(session, actor.scope)
    return await service.get(actor, id)


@router.patch("/customers/{id}", response_model=Customer, operation_id="updateCustomer")
async def update_customer(
    id: UUID,
    data: CustomerUpdate,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = CustomerService(session, actor.scope)
    return await service.update(actor, id, data)


@router.post("/customers/{id}/deactivate", response_model=Customer, operation_id="deactivateCustomer")
async def deactivate_customer(
    id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = CustomerService(session, actor.scope)
    return await service.deactivate(actor, id)


@router.get("/customers/{id}/history", response_model=CustomerHistory, operation_id="getCustomerHistory")
async def get_customer_history(
    id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = CustomerService(session, actor.scope)
    return await service.get_history(actor, id)


@router.get(
    "/customers/{id}/contact-methods", response_model=list[ContactMethod], operation_id="listContactMethods"
)
async def list_contact_methods(
    id: UUID,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = CustomerService(session, actor.scope)
    return await service.list_contact_methods(actor, id)


@router.post(
    "/customers/{id}/contact-methods",
    response_model=ContactMethod,
    status_code=status.HTTP_201_CREATED,
    operation_id="addContactMethod",
)
async def add_contact_method(
    id: UUID,
    data: ContactMethodCreate,
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = CustomerService(session, actor.scope)
    return await service.add_contact_method(actor, id, data)


@router.post(
    "/customers/{id}/attachments",
    response_model=Attachment,
    status_code=status.HTTP_201_CREATED,
    operation_id="uploadCustomerAttachment",
)
async def upload_customer_attachment(
    id: UUID,
    file: UploadFile = File(...),
    actor: CurrentActor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    service = CustomerService(session, actor.scope)
    return await service.add_attachment(actor, id, file)
