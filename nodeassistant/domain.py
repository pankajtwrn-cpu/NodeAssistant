"""Closed triage sets and the single category-to-owner rule."""

from dataclasses import dataclass
from enum import StrEnum


class Category(StrEnum):
    SALES = "Sales"
    SUPPORT = "Support"
    BILLING = "Billing"
    TECHNICAL = "Technical"
    OTHER = "Other"


class Priority(StrEnum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    URGENT = "Urgent"


class Owner(StrEnum):
    SALES_TEAM = "Sales Team"
    CLIENT_SUCCESS = "Client Success"
    FINANCE = "Finance"
    ENGINEERING = "Engineering"


_OWNER_BY_CATEGORY = {
    Category.SALES: Owner.SALES_TEAM,
    Category.SUPPORT: Owner.CLIENT_SUCCESS,
    Category.BILLING: Owner.FINANCE,
    Category.TECHNICAL: Owner.ENGINEERING,
    Category.OTHER: Owner.CLIENT_SUCCESS,
}


def owner_for(category: Category) -> Owner:
    """Return the one owner the routing matrix assigns to this category."""
    return _OWNER_BY_CATEGORY[category]


@dataclass(frozen=True)
class TriageResult:
    """A complete triage. Missing prose or a mismatched owner is not success."""

    summary: str
    category: Category
    priority: Priority
    reason: str
    owner: Owner
    draft: str

    def __post_init__(self) -> None:
        for field in ("summary", "reason", "draft"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} is required for a complete triage")
        if not isinstance(self.category, Category):
            raise ValueError("category is required for a complete triage")
        if not isinstance(self.priority, Priority):
            raise ValueError("priority is required for a complete triage")
        if self.owner is not owner_for(self.category):
            raise ValueError("owner does not match the routing matrix")
