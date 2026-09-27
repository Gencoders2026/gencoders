"""
Contextual customer replies for the Customer Simulator Agent (Task 3).

The customer's next message must depend on what the support agent
actually replied, not only on the customer's emotional band. This table
maps

    scenario -> what the agent did -> [(tone, customer message), ...]

where `tone` is the emotional band the line is written for
(`calm`, `concerned`, `frustrated`, `angry`, `furious`) or `"any"` for a
line that fits every tone. The simulator keeps only the variants matching
the current band, so a furious customer never answers politely.

Agent reply kinds (produced by `CustomerSimulator._agent_reply_kind`):

* `asks_for_info`     - the agent asked the customer for details
* `asks_confirmation` - the agent asked the customer to confirm something
* `gives_timeline`    - the agent made a concrete commitment
* `apology_only`      - the agent apologised without taking any action
* `vague`             - the agent stalled, deflected or quoted policy
* `offers_help`       - a generic, non-committal reply
"""

CONTEXTUAL_REPLIES = {

    # ==========================================================
    # REFUND REQUEST
    # ==========================================================

    "refund_request": {

        "asks_for_info": [
            ("any", "Sure, my order number is 44821-A and the payment was made on 12 March."),
            ("any", "Of course. The transaction reference is TXN-99274 and it was a card payment."),
            ("any", "No problem, my order number is 44821-B. The email on the account is ravi@example.com."),
            ("any", "Certainly - order 55120, paid by card ending 4417."),
        ],

        "asks_confirmation": [
            ("calm", "Yes, that is correct. Please go ahead and process it."),
            ("concerned", "Yes, that is the order. I hope it can be processed soon."),
            ("frustrated", "Yes, confirmed. Can you process the refund now please?"),
            ("angry", "Yes. I confirmed it already - now please actually do it."),
            ("furious", "I have confirmed it three times now. PROCESS THE REFUND."),
        ],

        "gives_timeline": [
            ("calm", "Thank you for letting me know. I will keep an eye on it."),
            ("concerned", "Alright, I understand. Please keep me posted if anything changes."),
            ("frustrated", "Okay, but that is longer than I was told before. Please make sure it happens."),
            ("angry", "A week is too long. I expected this to be handled much faster."),
            ("furious", "Five to ten business days is unacceptable. I have been waiting far longer than that."),
        ],

        "apology_only": [
            ("calm", "Thank you for the apology. Could you actually process the refund now?"),
            ("concerned", "I appreciate the apology, but I still need the refund to be completed."),
            ("frustrated", "Sorry is not a refund. Please process it and confirm to me."),
            ("angry", "An apology does not fix this. I want the refund processed today."),
            ("furious", "Do not apologise to me. PROCESS THE REFUND or give me a manager."),
        ],

        "vague": [
            ("calm", "I understand it may take a little time. Could you tell me the exact steps?"),
            ("concerned", "Okay, but I would really like a definite answer rather than 'soon'."),
            ("frustrated", "I have heard 'let me check' before. Give me a real timeline."),
            ("angry", "Stop saying you will check. Tell me exactly when the refund happens."),
            ("furious", "Checking is not an answer. ESCALATE THIS TO A MANAGER NOW."),
        ],

        "offers_help": [
            ("calm", "Thanks for your help. What exactly do you need from me to move this forward?"),
            ("concerned", "Okay. Is there anything you need from my side to speed this up?"),
            ("frustrated", "Fine. What is the next step, and who is handling it?"),
            ("angry", "Then actually do it. I am tired of asking for updates."),
            ("furious", "Doing nothing is not helping me. Get this escalated right now."),
        ],

    # ==========================================================
    # DELAYED ORDER
    # ==========================================================
    },
    "delayed_order": {

        "asks_for_info": [
            ("any", "My order number is 784213. It was supposed to arrive three days ago."),
            ("any", "Sure - tracking number 0034 8891 2210, and the courier never updated it."),
            ("any", "Of course. The order reference is DEL-55219, shipped on the 3rd."),
            ("any", "It's order 90147. The delivery page has not changed since I placed it."),
        ],

        "asks_confirmation": [
            ("calm", "Yes, that is correct. Please proceed with the next step."),
            ("concerned", "Yes, that is the right order. Please let me know what happens now."),
            ("frustrated", "Yes, confirmed. Can you give me the new delivery date now?"),
            ("angry", "Yes, I confirmed it. Now give me an actual delivery date."),
            ("furious", "CONFIRMED. Stop asking me things and fix the delivery."),
        ],

        "gives_timeline": [
            ("calm", "Thank you for the update. I appreciate you checking for me."),
            ("concerned", "I hope they keep to that date this time. Please confirm if it slips."),
            ("frustrated", "That is already later than the original estimate. Please make sure it holds."),
            ("angry", "Two more days? This order is already a week late. That is not good enough."),
            ("furious", "You keep moving the date. I refuse to accept another vague delay."),
        ],

        "apology_only": [
            ("calm", "Thank you for apologising. Could you actually check the delivery status for me?"),
            ("concerned", "I appreciate the apology, but I still need a real update on the delivery."),
            ("frustrated", "Sorry does not deliver my order. Please give me a tracking update."),
            ("angry", "Stop apologising and start tracking it. Where is my order?"),
            ("furious", "I DO NOT WANT AN APOLOGY. I WANT MY ORDER. ESCALATE THIS NOW."),
        ],

        "vague": [
            ("calm", "I understand there can be delays. Could you share the current tracking status?"),
            ("concerned", "Okay, but 'soon' is not very helpful. What does the courier say?"),
            ("frustrated", "I am tired of waiting without a clear answer. Give me a date."),
            ("angry", "Checking again does not help me. When exactly will it arrive?"),
            ("furious", "STOP WITH THE VAGUE ANSWERS. ESCALATE TO A SUPERVISOR NOW."),
        ],

        "offers_help": [
            ("calm", "Thanks. What is the next step on your side to speed this up?"),
            ("concerned", "Okay. Is there anything I can do to get a faster delivery?"),
            ("frustrated", "Fine. Who is handling this and when will they update me?"),
            ("angry", "Then handle it. I need a delivery update, not an offer of help."),
            ("furious", "Your help is not helping. Get me someone who can fix this."),
        ],
    },
    "payment_failure": {

        "asks_for_info": [
            ("any", "Sure, my card ends in 8823 and the payment was for 149 dollars."),
            ("any", "Of course. The transaction attempt was at 14:05 today, card ending 2210."),
            ("any", "No problem - account is ravi@example.com and the order total was 249 dollars."),
            ("any", "Certainly. Payment reference PAY-7741, and it keeps failing at the confirmation step."),
        ],

        "asks_confirmation": [
            ("calm", "Yes, that is correct. Please continue with the payment."),
            ("concerned", "Yes, that is the card I used. Please let me know if it works now."),
            ("frustrated", "Yes, confirmed. Can you complete the payment for me now?"),
            ("angry", "I already confirmed it. Just fix the payment."),
            ("furious", "STOP ASKING ME TO CONFIRM. FIX THE PAYMENT OR ESCALATE IT."),
        ],

        "gives_timeline": [
            ("calm", "Thank you, I will try paying again in a little while."),
            ("concerned", "Okay, I hope it goes through this time. Please confirm once it does."),
            ("frustrated", "Please make sure it actually works, not just that it is queued."),
            ("angry", "A few hours is not good enough. I need this settled now."),
            ("furious", "I HAVE BEEN TRYING FOR DAYS. FIX IT OR GET ME A MANAGER."),
        ],

        "apology_only": [
            ("calm", "Thank you for the apology. Could you try the payment again for me?"),
            ("concerned", "I appreciate it, but I still cannot complete the payment."),
            ("frustrated", "Sorry does not charge my card. Please fix the payment error."),
            ("angry", "An apology is not a solution. Get the payment working."),
            ("furious", "DO NOT APOLOGISE TO ME. FIX THE PAYMENT OR ESCALATE IT NOW."),
        ],

        "vague": [
            ("calm", "I understand these things happen. Could you tell me the exact error?"),
            ("concerned", "Okay, but what exactly is failing? I need something concrete."),
            ("frustrated", "I am tired of hearing you will check. Tell me what is wrong."),
            ("angry", "Stop guessing. Give me the real reason the payment fails."),
            ("furious", "ENOUGH. ESCALATE THIS PAYMENT ISSUE TO A SUPERVISOR NOW."),
        ],

        "offers_help": [
            ("calm", "Thanks. What steps should I take to complete the payment?"),
            ("concerned", "Okay. Is there another payment method I can use?"),
            ("frustrated", "Fine. What exactly do you need from me to unblock the payment?"),
            ("angry", "Then do something concrete instead of offering help."),
            ("furious", "Offering to help is not helping. ESCALATE THIS NOW."),
        ],
    },
    "account_issue": {

        "asks_for_info": [
            ("any", "My username is ravi.k and the email on the account is ravi@example.com."),
            ("any", "Of course - the account is under Priya Sharma, last four of the number 4471."),
            ("any", "Sure, it is priya.sharma@example.com. I am already logged in on my phone."),
            ("any", "My account id is ACC-33910 and I last used it yesterday."),
        ],

        "asks_confirmation": [
            ("calm", "Yes, that is the account. Thank you for checking."),
            ("concerned", "Yes, that is correct. I hope you can restore access soon."),
            ("frustrated", "Yes, confirmed. Please unlock it now, please."),
            ("angry", "I already confirmed my details. Restore my access."),
            ("furious", "I HAVE CONFIRMED EVERYTHING. UNLOCK MY ACCOUNT NOW."),
        ],

        "gives_timeline": [
            ("calm", "Thank you. I will try the reset link once more."),
            ("concerned", "Alright. Please let me know if the reset email does not arrive."),
            ("frustrated", "Please make sure the reset email actually reaches me this time."),
            ("angry", "That is too slow. I am locked out of my own account right now."),
            ("furious", "I AM LOCKED OUT. FIX IT NOW OR ESCALATE TO A MANAGER."),
        ],

        "apology_only": [
            ("calm", "Thank you for apologising. Could you send the password reset email?"),
            ("concerned", "I appreciate the apology, but I still cannot log in."),
            ("frustrated", "Sorry does not unlock my account. Please send the reset link."),
            ("angry", "Stop apologising and send me the reset link."),
            ("furious", "I DO NOT WANT AN APOLOGY. RESTORE MY ACCESS NOW."),
        ],

        "vague": [
            ("calm", "I understand. Could you tell me exactly which step to try?"),
            ("concerned", "Okay, but I need a specific instruction to get back in."),
            ("frustrated", "I am tired of generic answers. What should I actually do?"),
            ("angry", "Stop saying you will look into it and tell me the fix."),
            ("furious", "THIS IS URGENT. ESCALATE MY ACCOUNT LOCK TO A SUPERVISOR."),
        ],

        "offers_help": [
            ("calm", "Thanks for your help. What is the next step for me?"),
            ("concerned", "Okay. Do I need to verify my identity to get back in?"),
            ("frustrated", "Fine. How long until I can log in again?"),
            ("angry", "Then actually restore my access instead of offering help."),
            ("furious", "Stop offering help and FIX MY ACCOUNT."),
        ],
    },
    "cancellation": {

        "asks_for_info": [
            ("any", "My subscription id is SUB-66210 and it renews on the 28th."),
            ("any", "Of course, the plan is the Standard monthly one under ravi@example.com."),
            ("any", "Sure - account number 55478, and I have not used it this month."),
            ("any", "The subscription is under Priya Sharma, plan id PLAN-3391."),
        ],

        "asks_confirmation": [
            ("calm", "Yes, please cancel it. Thank you for confirming."),
            ("concerned", "Yes, that is the right subscription. Please cancel it before it renews."),
            ("frustrated", "Yes, confirmed. Please cancel it now and confirm to me."),
            ("angry", "I already confirmed. Cancel the subscription."),
            ("furious", "STOP ASKING. JUST CANCEL IT NOW."),
        ],

        "gives_timeline": [
            ("calm", "Thank you for confirming. I will make a note of the cancellation date."),
            ("concerned", "Okay. Please make sure I am not charged again before then."),
            ("frustrated", "Please make sure the cancellation is actually processed by then."),
            ("angry", "That is after my renewal date. Cancel it before I am charged."),
            ("furious", "I AM ALREADY BEING CHARGED AGAIN. FIX THE CANCELLATION NOW."),
        ],

        "apology_only": [
            ("calm", "Thank you for the apology. Could you go ahead and cancel it?"),
            ("concerned", "I appreciate it, but I still need the cancellation completed."),
            ("frustrated", "Sorry is not a cancellation. Please cancel my subscription."),
            ("angry", "Stop apologising and cancel the subscription."),
            ("furious", "CANCEL IT OR GET ME A MANAGER. I AM NOT ASKING NICELY."),
        ],

        "vague": [
            ("calm", "I understand there may be a process. Could you explain the steps?"),
            ("concerned", "Okay, but I need to be sure I will not be charged again."),
            ("frustrated", "I am tired of waiting. Just confirm the cancellation."),
            ("angry", "Stop explaining policy and cancel my subscription."),
            ("furious", "I HAVE ASKED TWICE. CANCEL IT OR ESCALATE TO A MANAGER NOW."),
        ],

        "offers_help": [
            ("calm", "Thanks. What do you need from me to complete the cancellation?"),
            ("concerned", "Okay. Will I get a confirmation email once it is done?"),
            ("frustrated", "Fine. When exactly will the cancellation be completed?"),
            ("angry", "Then do it instead of offering me help."),
            ("furious", "STOP TALKING AND CANCEL MY SUBSCRIPTION NOW."),
        ],
    }
}
