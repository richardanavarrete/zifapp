"""
Billing Models

Models for Stripe billing and subscription management.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PlanTier(str, Enum):
    """Subscription plan tiers."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """Subscription status values (aligned with Stripe)."""
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    TRIALING = "trialing"
    UNPAID = "unpaid"
    PAUSED = "paused"


class Organization(BaseModel):
    """Organization/tenant model."""
    id: str = Field(..., description="Unique organization ID")
    name: str = Field(..., description="Organization name")
    stripe_customer_id: Optional[str] = Field(None, description="Stripe Customer ID")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Subscription(BaseModel):
    """Subscription model linked to an organization."""
    id: str = Field(..., description="Unique subscription ID")
    org_id: str = Field(..., description="Organization ID")
    stripe_subscription_id: Optional[str] = Field(None, description="Stripe Subscription ID")
    plan_tier: PlanTier = Field(default=PlanTier.FREE, description="Current plan tier")
    status: SubscriptionStatus = Field(default=SubscriptionStatus.ACTIVE, description="Subscription status")
    current_period_start: Optional[datetime] = Field(None, description="Current billing period start")
    current_period_end: Optional[datetime] = Field(None, description="Current billing period end")
    cancel_at_period_end: bool = Field(default=False, description="Whether subscription cancels at period end")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CheckoutRequest(BaseModel):
    """Request to create a Stripe Checkout session."""
    plan_tier: PlanTier = Field(..., description="Plan tier to subscribe to")
    success_url: str = Field(..., description="URL to redirect to on success")
    cancel_url: str = Field(..., description="URL to redirect to on cancel")


class CheckoutResponse(BaseModel):
    """Response from creating a Stripe Checkout session."""
    checkout_url: str = Field(..., description="Stripe Checkout URL to redirect user to")
    session_id: str = Field(..., description="Stripe Checkout Session ID")


class PortalRequest(BaseModel):
    """Request to create a Stripe Customer Portal session."""
    return_url: str = Field(..., description="URL to redirect to when user leaves portal")


class PortalResponse(BaseModel):
    """Response from creating a Stripe Customer Portal session."""
    portal_url: str = Field(..., description="Stripe Customer Portal URL to redirect user to")


class SubscriptionResponse(BaseModel):
    """Response for current subscription status."""
    org_id: str = Field(..., description="Organization ID")
    plan_tier: PlanTier = Field(..., description="Current plan tier")
    status: SubscriptionStatus = Field(..., description="Subscription status")
    current_period_end: Optional[datetime] = Field(None, description="Current billing period end")
    cancel_at_period_end: bool = Field(default=False, description="Whether subscription cancels at period end")
    stripe_subscription_id: Optional[str] = Field(None, description="Stripe Subscription ID")


PLAN_PRICES = {
    PlanTier.FREE: 0,
    PlanTier.PRO: 4900,  # $49.00 in cents
    PlanTier.ENTERPRISE: 19900,  # $199.00 in cents
}
