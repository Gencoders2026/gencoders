"""
Customer Scenarios for the Simulator Agent.
"""

from typing import Dict, Any

SCENARIOS: Dict[str, Dict[str, Any]] = {
    "refund_request": {
        "name": "Refund Request",
        "description": "Customer wants a full or partial refund for a product/service.",
        "context": (
            "Customer ordered a product online that arrived damaged / not as described / "
            "or they simply changed their mind within the return window. They have the order number "
            "and want the money back to the original payment method."
        ),
        "key_facts": {
            "order_id": "ORD-78421",
            "product": "Wireless Noise-Cancelling Headphones",
            "purchase_date": "12 days ago",
            "amount": "$149.99",
            "reason": "Item arrived with a crack in the left ear cup",
            "return_window": "30 days"
        },
        "customer_goal": "Receive a full refund to original payment method within 5-7 business days.",
        "common_objections": [
            "We can only offer store credit",
            "You need to ship it back first",
            "The return window has passed (it hasn't)",
            "We need photos of the damage"
        ],
        "success_criteria": "Agent confirms refund will be processed and gives timeline.",
        "severity_hints": ["refund", "money back", "return", "damaged", "order"]
    },
    "delayed_order": {
        "name": "Delayed Order",
        "description": "Customer’s order has not arrived by the promised delivery date.",
        "context": (
            "Customer ordered an item that was supposed to arrive 4 days ago. Tracking shows "
            "it is still in transit or has not updated. They need it for an event / work / gift."
        ),
        "key_facts": {
            "order_id": "ORD-39215",
            "product": "Office Desk Chair (Ergonomic)",
            "promised_delivery": "4 days ago",
            "current_status": "In transit – last update 3 days ago",
            "tracking_number": "1Z999AA10123456784",
            "urgency": "Needed for remote work setup this week"
        },
        "customer_goal": "Get a firm new delivery date or a replacement / refund if further delayed.",
        "common_objections": [
            "Shipping carrier delays are outside our control",
            "Please wait another 2-3 days",
            "We can only offer a discount on next order"
        ],
        "success_criteria": "Agent provides updated ETA or escalates to shipping partner / offers compensation.",
        "severity_hints": ["late", "delayed", "not arrived", "tracking", "delivery"]
    },
    "payment_failure": {
        "name": "Payment Failure",
        "description": "Customer’s payment was declined or charged incorrectly.",
        "context": (
            "Customer tried to pay for a subscription renewal or a new order. The card was charged "
            "but the order/subscription was not activated, or the charge failed repeatedly."
        ),
        "key_facts": {
            "account_email": "customer@email.com",
            "last_attempt": "Today, 2 hours ago",
            "amount": "$29.99 / month",
            "card_last4": "4242",
            "error_seen": "Payment declined – insufficient funds (but customer says funds are available)",
            "subscription": "Premium Plan"
        },
        "customer_goal": "Successful payment and immediate activation of the service / order.",
        "common_objections": [
            "Please try a different card",
            "It can take 24-48 hours to reflect",
            "Contact your bank"
        ],
        "success_criteria": "Agent verifies payment status, retries or corrects the charge, confirms activation.",
        "severity_hints": ["payment", "charged", "declined", "card", "subscription"]
    },
    "account_issue": {
        "name": "Account Issue",
        "description": "Customer cannot log in, access features, or sees incorrect account data.",
        "context": (
            "Customer is locked out of their account after a password reset, or their profile "
            "shows the wrong subscription tier / missing order history."
        ),
        "key_facts": {
            "account_email": "user.support@example.com",
            "issue": "Password reset link expired / account locked after 3 failed attempts",
            "last_successful_login": "5 days ago",
            "device": "iPhone 15, Safari",
            "subscription_shown": "Free (should be Premium)"
        },
        "customer_goal": "Regain full access to the correct account and subscription benefits.",
        "common_objections": [
            "Please try resetting again",
            "Clear your cache",
            "We need identity verification"
        ],
        "success_criteria": "Agent unlocks account or corrects subscription and confirms login works.",
        "severity_hints": ["login", "password", "locked", "account", "access"]
    },
    "cancellation": {
        "name": "Cancellation Request",
        "description": "Customer wants to cancel a subscription or ongoing service.",
        "context": (
            "Customer is unhappy with the product or no longer needs it. They want to cancel "
            "immediately and stop future charges. They may ask about refund of remaining period."
        ),
        "key_facts": {
            "subscription": "Annual Premium – $199/year",
            "start_date": "3 months ago",
            "next_billing": "in 9 months",
            "reason": "Not using the features enough / found a cheaper alternative",
            "auto_renew": True
        },
        "customer_goal": "Confirm cancellation, stop auto-renew, and understand any refund policy.",
        "common_objections": [
            "We can offer a discount to stay",
            "Cancellation takes effect at end of billing period",
            "No partial refunds on annual plans"
        ],
        "success_criteria": "Agent confirms cancellation date, stops charges, and explains refund (if any).",
        "severity_hints": ["cancel", "unsubscribe", "stop billing", "end subscription"]
    },
}

def get_scenario(name: str) -> Dict[str, Any]:
    key = name.lower().strip()
    if key not in SCENARIOS:
        available = ", ".join(SCENARIOS.keys())
        raise KeyError(f"Unknown scenario '{name}'. Available: {available}")
    return SCENARIOS[key]

def list_scenarios() -> list:
    return list(SCENARIOS.keys())