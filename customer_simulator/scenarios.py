# scenarios.py

SCENARIOS = {
    "refund_request": {
        "name": "Refund Request",
        "description": "Customer wants a full refund for a product they bought.",
        "customer_knows": "Order number, purchase date, reason for refund.",
        "expected_resolution": "Refund processed or clear explanation why it cannot be given."
    },
    "delayed_order": {
        "name": "Delayed Order",
        "description": "Customer’s order is late and they want to know the new delivery date.",
        "customer_knows": "Order number, original delivery date.",
        "expected_resolution": "New delivery date or compensation offer."
    },
    "payment_failure": {
        "name": "Payment Failure",
        "description": "Payment failed but money was deducted from the account.",
        "customer_knows": "Transaction ID, amount, date of payment.",
        "expected_resolution": "Money refunded or payment status corrected."
    },
    "account_issue": {
        "name": "Account Locked",
        "description": "Customer cannot log into their account.",
        "customer_knows": "Email address linked to the account.",
        "expected_resolution": "Account unlocked or password reset successfully."
    },
    "cancellation": {
        "name": "Cancellation Request",
        "description": "Customer wants to cancel their subscription or order.",
        "customer_knows": "Subscription ID or order number.",
        "expected_resolution": "Cancellation confirmed and any refund details given."
    }
}