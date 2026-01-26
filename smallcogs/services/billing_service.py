"""
Billing Service

Handles Stripe integration for subscriptions and billing.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Optional

import stripe

from smallcogs.models.billing import (
    Organization,
    PlanTier,
    Subscription,
    SubscriptionStatus,
)

logger = logging.getLogger(__name__)


class BillingService:
    """Service for managing Stripe billing and subscriptions."""

    def __init__(
        self,
        stripe_secret_key: Optional[str] = None,
        stripe_webhook_secret: Optional[str] = None,
        stripe_price_id_pro: Optional[str] = None,
        stripe_price_id_enterprise: Optional[str] = None,
    ):
        """Initialize billing service with Stripe credentials."""
        self.stripe_secret_key = stripe_secret_key
        self.stripe_webhook_secret = stripe_webhook_secret
        self.stripe_price_id_pro = stripe_price_id_pro
        self.stripe_price_id_enterprise = stripe_price_id_enterprise

        # Configure Stripe
        if stripe_secret_key:
            stripe.api_key = stripe_secret_key

        # In-memory storage (replace with database in production)
        self._organizations: Dict[str, Organization] = {}
        self._subscriptions: Dict[str, Subscription] = {}
        self._org_subscriptions: Dict[str, str] = {}  # org_id -> subscription_id
        self._stripe_customer_to_org: Dict[str, str] = {}  # stripe_customer_id -> org_id

    def _get_price_id_for_tier(self, tier: PlanTier) -> Optional[str]:
        """Get Stripe Price ID for a plan tier."""
        if tier == PlanTier.PRO:
            return self.stripe_price_id_pro
        elif tier == PlanTier.ENTERPRISE:
            return self.stripe_price_id_enterprise
        return None  # Free tier has no price

    def get_or_create_organization(self, org_id: str, name: str = "Default Org") -> Organization:
        """Get or create an organization."""
        if org_id not in self._organizations:
            org = Organization(id=org_id, name=name)
            self._organizations[org_id] = org
            # Create a free subscription for new orgs
            self._create_free_subscription(org_id)
        return self._organizations[org_id]

    def _create_free_subscription(self, org_id: str) -> Subscription:
        """Create a free tier subscription for an organization."""
        sub_id = f"sub_{uuid.uuid4().hex[:16]}"
        subscription = Subscription(
            id=sub_id,
            org_id=org_id,
            plan_tier=PlanTier.FREE,
            status=SubscriptionStatus.ACTIVE,
        )
        self._subscriptions[sub_id] = subscription
        self._org_subscriptions[org_id] = sub_id
        return subscription

    def get_organization(self, org_id: str) -> Optional[Organization]:
        """Get an organization by ID."""
        return self._organizations.get(org_id)

    def get_subscription(self, org_id: str) -> Optional[Subscription]:
        """Get subscription for an organization."""
        sub_id = self._org_subscriptions.get(org_id)
        if sub_id:
            return self._subscriptions.get(sub_id)
        return None

    def get_org_by_stripe_customer(self, stripe_customer_id: str) -> Optional[Organization]:
        """Get organization by Stripe customer ID."""
        org_id = self._stripe_customer_to_org.get(stripe_customer_id)
        if org_id:
            return self._organizations.get(org_id)
        return None

    async def create_checkout_session(
        self,
        org_id: str,
        plan_tier: PlanTier,
        success_url: str,
        cancel_url: str,
    ) -> tuple[str, str]:
        """
        Create a Stripe Checkout session for subscription.

        Returns: (checkout_url, session_id)
        """
        if not self.stripe_secret_key:
            raise ValueError("Stripe is not configured")

        if plan_tier == PlanTier.FREE:
            raise ValueError("Cannot checkout for free tier")

        price_id = self._get_price_id_for_tier(plan_tier)
        if not price_id:
            raise ValueError(f"No price configured for tier: {plan_tier}")

        org = self.get_or_create_organization(org_id)

        # Create or get Stripe customer
        if not org.stripe_customer_id:
            customer = stripe.Customer.create(
                metadata={"org_id": org_id},
            )
            org.stripe_customer_id = customer.id
            org.updated_at = datetime.utcnow()
            self._stripe_customer_to_org[customer.id] = org_id
            logger.info(f"Created Stripe customer {customer.id} for org {org_id}")

        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=org.stripe_customer_id,
            mode="subscription",
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "org_id": org_id,
                "plan_tier": plan_tier.value,
            },
        )

        logger.info(f"Created checkout session {session.id} for org {org_id}, tier {plan_tier}")
        return session.url, session.id

    async def create_portal_session(self, org_id: str, return_url: str) -> str:
        """
        Create a Stripe Customer Portal session.

        Returns: portal_url
        """
        if not self.stripe_secret_key:
            raise ValueError("Stripe is not configured")

        org = self.get_organization(org_id)
        if not org:
            raise ValueError(f"Organization not found: {org_id}")

        if not org.stripe_customer_id:
            raise ValueError("Organization has no Stripe customer")

        session = stripe.billing_portal.Session.create(
            customer=org.stripe_customer_id,
            return_url=return_url,
        )

        logger.info(f"Created portal session for org {org_id}")
        return session.url

    def verify_webhook_signature(self, payload: bytes, signature: str) -> dict:
        """
        Verify Stripe webhook signature and return the event.

        Raises: ValueError if signature is invalid
        """
        if not self.stripe_webhook_secret:
            raise ValueError("Webhook secret is not configured")

        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.stripe_webhook_secret
            )
            return event
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Webhook signature verification failed: {e}")
            raise ValueError("Invalid webhook signature")

    def handle_webhook_event(self, event: dict) -> None:
        """Handle a Stripe webhook event."""
        event_type = event.get("type", "")
        data = event.get("data", {}).get("object", {})

        logger.info(f"Processing webhook event: {event_type}")

        if event_type == "customer.subscription.created":
            self._handle_subscription_created(data)
        elif event_type == "customer.subscription.updated":
            self._handle_subscription_updated(data)
        elif event_type == "customer.subscription.deleted":
            self._handle_subscription_deleted(data)
        elif event_type == "invoice.payment_failed":
            self._handle_payment_failed(data)
        elif event_type == "checkout.session.completed":
            self._handle_checkout_completed(data)
        else:
            logger.info(f"Unhandled webhook event type: {event_type}")

    def _handle_checkout_completed(self, session: dict) -> None:
        """Handle checkout.session.completed event."""
        metadata = session.get("metadata", {})
        org_id = metadata.get("org_id")
        if not org_id:
            logger.warning("Checkout session has no org_id in metadata")
            return

        customer_id = session.get("customer")
        if customer_id:
            org = self.get_organization(org_id)
            if org and not org.stripe_customer_id:
                org.stripe_customer_id = customer_id
                org.updated_at = datetime.utcnow()
                self._stripe_customer_to_org[customer_id] = org_id
                logger.info(f"Updated org {org_id} with Stripe customer {customer_id}")

    def _handle_subscription_created(self, subscription_data: dict) -> None:
        """Handle subscription created event."""
        stripe_sub_id = subscription_data.get("id")
        customer_id = subscription_data.get("customer")
        status = subscription_data.get("status", "active")

        org = self.get_org_by_stripe_customer(customer_id)
        if not org:
            logger.warning(f"No org found for Stripe customer {customer_id}")
            return

        # Determine plan tier from price
        items = subscription_data.get("items", {}).get("data", [])
        plan_tier = PlanTier.FREE
        if items:
            price_id = items[0].get("price", {}).get("id")
            if price_id == self.stripe_price_id_pro:
                plan_tier = PlanTier.PRO
            elif price_id == self.stripe_price_id_enterprise:
                plan_tier = PlanTier.ENTERPRISE

        # Update or create subscription
        sub = self.get_subscription(org.id)
        if sub:
            sub.stripe_subscription_id = stripe_sub_id
            sub.plan_tier = plan_tier
            sub.status = SubscriptionStatus(status) if status in SubscriptionStatus.__members__.values() else SubscriptionStatus.ACTIVE
            sub.current_period_start = datetime.fromtimestamp(subscription_data.get("current_period_start", 0))
            sub.current_period_end = datetime.fromtimestamp(subscription_data.get("current_period_end", 0))
            sub.cancel_at_period_end = subscription_data.get("cancel_at_period_end", False)
            sub.updated_at = datetime.utcnow()

        logger.info(f"Subscription created for org {org.id}: {plan_tier.value}")

    def _handle_subscription_updated(self, subscription_data: dict) -> None:
        """Handle subscription updated event."""
        stripe_sub_id = subscription_data.get("id")
        customer_id = subscription_data.get("customer")
        status = subscription_data.get("status", "active")

        org = self.get_org_by_stripe_customer(customer_id)
        if not org:
            logger.warning(f"No org found for Stripe customer {customer_id}")
            return

        # Determine plan tier from price
        items = subscription_data.get("items", {}).get("data", [])
        plan_tier = PlanTier.FREE
        if items:
            price_id = items[0].get("price", {}).get("id")
            if price_id == self.stripe_price_id_pro:
                plan_tier = PlanTier.PRO
            elif price_id == self.stripe_price_id_enterprise:
                plan_tier = PlanTier.ENTERPRISE

        sub = self.get_subscription(org.id)
        if sub:
            sub.stripe_subscription_id = stripe_sub_id
            sub.plan_tier = plan_tier
            try:
                sub.status = SubscriptionStatus(status)
            except ValueError:
                sub.status = SubscriptionStatus.ACTIVE
            sub.current_period_start = datetime.fromtimestamp(subscription_data.get("current_period_start", 0))
            sub.current_period_end = datetime.fromtimestamp(subscription_data.get("current_period_end", 0))
            sub.cancel_at_period_end = subscription_data.get("cancel_at_period_end", False)
            sub.updated_at = datetime.utcnow()

        logger.info(f"Subscription updated for org {org.id}: {plan_tier.value}, status={status}")

    def _handle_subscription_deleted(self, subscription_data: dict) -> None:
        """Handle subscription deleted (canceled) event."""
        customer_id = subscription_data.get("customer")

        org = self.get_org_by_stripe_customer(customer_id)
        if not org:
            logger.warning(f"No org found for Stripe customer {customer_id}")
            return

        # Downgrade to free tier
        sub = self.get_subscription(org.id)
        if sub:
            sub.stripe_subscription_id = None
            sub.plan_tier = PlanTier.FREE
            sub.status = SubscriptionStatus.CANCELED
            sub.cancel_at_period_end = False
            sub.updated_at = datetime.utcnow()

        logger.info(f"Subscription canceled for org {org.id}, downgraded to free")

    def _handle_payment_failed(self, invoice_data: dict) -> None:
        """Handle payment failed event."""
        customer_id = invoice_data.get("customer")
        subscription_id = invoice_data.get("subscription")

        org = self.get_org_by_stripe_customer(customer_id)
        if not org:
            logger.warning(f"No org found for Stripe customer {customer_id}")
            return

        sub = self.get_subscription(org.id)
        if sub and sub.stripe_subscription_id == subscription_id:
            sub.status = SubscriptionStatus.PAST_DUE
            sub.updated_at = datetime.utcnow()

        logger.warning(f"Payment failed for org {org.id}")
