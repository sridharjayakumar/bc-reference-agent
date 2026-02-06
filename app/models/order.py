"""Order data model."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class Order(BaseModel):
    """Order model with validation."""

    id: int
    first_name: str
    last_name: str
    email: EmailStr
    order_id: str = Field(..., min_length=10, max_length=15)
    street: str
    city: str
    state: str
    zipcode: str = Field(..., pattern=r"^\d{5}$")
    delivery_date: str  # MM/DD/YYYY format

    class Config:
        """Pydantic config."""

        frozen = False  # Allow updates
        str_strip_whitespace = True

    def full_name(self) -> str:
        """Get customer's full name."""
        return f"{self.first_name} {self.last_name}"

    def full_address(self) -> str:
        """Get formatted full address."""
        return f"{self.street}, {self.city}, {self.state} {self.zipcode}"

    @classmethod
    def from_row(cls, row: dict) -> "Order":
        """Create Order from a database row dict."""
        return cls(
            id=int(row["id"]),
            first_name=row["first_name"],
            last_name=row["last_name"],
            email=row["email"],
            order_id=row["order_id"],
            street=row["street"],
            city=row["city"],
            state=row["state"],
            zipcode=row["zipcode"],
            delivery_date=row["delivery_date"],
        )


class OrderUpdate(BaseModel):
    """Model for order updates."""

    delivery_date: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipcode: Optional[str] = Field(None, pattern=r"^\d{5}$")

    def to_dict(self) -> dict[str, str]:
        """Convert to dict, excluding None values."""
        return {k: v for k, v in self.model_dump().items() if v is not None}
