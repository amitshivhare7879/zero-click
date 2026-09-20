from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    store_id: str
    customer_phone: str
    message: str
    image_base64: Optional[str] = None


class AuditStep(BaseModel):
    step_number: int
    title: str
    detail: str
    status: str = "completed"


class ChatResponse(BaseModel):
    reply: str
    order_id: Optional[str] = None
    status: Optional[str] = None
    total: Optional[float] = None
    audit_steps: List[AuditStep] = Field(default_factory=list)
    flags: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_alternatives: List[Dict[str, Any]] = Field(default_factory=list)
    onboarding_step: Optional[str] = None
    customer: Optional[Dict[str, Any]] = None


class QtyUpdate(BaseModel):
    qty: int


class RestockRequest(BaseModel):
    add_qty: int
    new_price: Optional[float] = None


class OCRRequest(BaseModel):
    store_id: str
    customer_phone: str
    image_base64: str


class CustomerLoginRequest(BaseModel):
    store_id: Optional[str] = None
    phone: str
    name: Optional[str] = None
    address: Optional[str] = None


class CustomerUpdateRequest(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    onboarding_step: Optional[str] = None
