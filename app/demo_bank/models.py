"""In-memory data model and fault injection state for Demo Bank."""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class Member(BaseModel):
    member_id: str
    name: str
    savings_balance: float
    currency: str = "USD"
    checking_balance: float = 0.0
    status: str = "Active"

# Initial mock database
MEMBERS_DB: Dict[str, Member] = {
    "12345": Member(
        member_id="12345",
        name="Jane Doe",
        savings_balance=12450.32,
        currency="USD",
        checking_balance=2150.00,
        status="Active"
    ),
    "67890": Member(
        member_id="67890",
        name="John Smith",
        savings_balance=5300.00,
        currency="USD",
        checking_balance=850.50,
        status="Active"
    ),
}

class FaultInjectionState(BaseModel):
    session_timeout: bool = False
    unexpected_dialog: bool = False
    application_error: bool = False
    transient_load_failure: bool = False
    validation_error: bool = False

# Global fault state for simulation
GLOBAL_FAULT_STATE = FaultInjectionState()
