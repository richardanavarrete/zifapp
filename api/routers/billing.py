"""
Billing API endpoints.

Handles Stripe checkout, customer portal, webhooks, and subscription status.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from api.config import Settings, get_settings
from api.middleware.auth import verify_api_key
from smallcogs.models.billing import (
    CheckoutRequest,
    CheckoutResponse,
    PlanTier,
    PortalRequest,
    PortalResponse,
    SubscriptionResponse,
    SubscriptionStatus,
)
from smallcogs.services.billing_service import BillingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["Billing"])

# Service instance
_service: Optional[BillingService] = None


def get_billing_service(settings: Settings = Depends(get_settings)) -> BillingService:
    """Get or create billing service singleton."""
    global _service
    if _service is None:
        _service = BillingService(
            stripe_secret_key=settings.stripe_secret_key,
            stripe_webhook_secret=settings.stripe_webhook_secret,
            stripe_price_id_pro=settings.stripe_price_id_pro,
            stripe_price_id_enterprise=settings.stripe_price_id_enterprise,
        )
    return _service


def get_org_id_from_api_key(api_key: str = Depends(verify_api_key)) -> str:
    """
    Extract organization ID from API key.

    In a full implementation, this would look up the org associated with the API key.
    For now, we use a hash of the API key as the org ID.
    """
    import hashlib
    return f"org_{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    request: CheckoutRequest,
    org_id: str = Depends(get_org_id_from_api_key),
    service: BillingService = Depends(get_billing_service),
):
    """
    Create a Stripe Checkout session for subscription.

    Returns a URL to redirect the user to Stripe's hosted checkout page.
    """
    if request.plan_tier == PlanTier.FREE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_TIER", "message": "Cannot checkout for free tier"}},
        )

    try:
        checkout_url, session_id = await service.create_checkout_session(
            org_id=org_id,
            plan_tier=request.plan_tier,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )
        return CheckoutResponse(checkout_url=checkout_url, session_id=session_id)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "CHECKOUT_ERROR", "message": str(e)}},
        )


@router.post("/portal", response_model=PortalResponse)
async def create_portal_session(
    request: PortalRequest,
    org_id: str = Depends(get_org_id_from_api_key),
    service: BillingService = Depends(get_billing_service),
):
    """
    Create a Stripe Customer Portal session.

    Returns a URL to redirect the user to Stripe's customer portal
    where they can manage their subscription, payment methods, and invoices.
    """
    # Ensure org exists
    service.get_or_create_organization(org_id)

    try:
        portal_url = await service.create_portal_session(
            org_id=org_id,
            return_url=request.return_url,
        )
        return PortalResponse(portal_url=portal_url)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "PORTAL_ERROR", "message": str(e)}},
        )


@router.post("/webhook")
async def handle_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    settings: Settings = Depends(get_settings),
    service: BillingService = Depends(get_billing_service),
):
    """
    Handle Stripe webhook events.

    This endpoint receives events from Stripe about subscription changes,
    payment failures, etc. The signature is verified using the webhook secret.
    """
    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "MISSING_SIGNATURE", "message": "Stripe-Signature header required"}},
        )

    # Get raw body for signature verification
    payload = await request.body()

    try:
        event = service.verify_webhook_signature(payload, stripe_signature)
    except ValueError as e:
        logger.warning(f"Webhook signature verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_SIGNATURE", "message": "Invalid webhook signature"}},
        )

    # Process the event
    try:
        service.handle_webhook_event(event)
    except Exception as e:
        logger.error(f"Error processing webhook event: {e}")
        # Still return 200 to acknowledge receipt (Stripe will retry otherwise)

    return {"received": True}


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    org_id: str = Depends(get_org_id_from_api_key),
    service: BillingService = Depends(get_billing_service),
):
    """
    Get current subscription status for the organization.

    Returns the current plan tier, subscription status, and billing period.
    """
    # Ensure org exists with at least a free subscription
    service.get_or_create_organization(org_id)

    subscription = service.get_subscription(org_id)
    if not subscription:
        # This shouldn't happen since get_or_create_organization creates a free sub
        return SubscriptionResponse(
            org_id=org_id,
            plan_tier=PlanTier.FREE,
            status=SubscriptionStatus.ACTIVE,
            current_period_end=None,
            cancel_at_period_end=False,
            stripe_subscription_id=None,
        )

    return SubscriptionResponse(
        org_id=org_id,
        plan_tier=subscription.plan_tier,
        status=subscription.status,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
        stripe_subscription_id=subscription.stripe_subscription_id,
    )
