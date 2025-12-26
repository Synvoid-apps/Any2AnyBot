import requests
import uuid
from datetime import datetime

ORDERS = {}

def create_payment(uid, plan, amount):
    order_id = str(uuid.uuid4())
    ORDERS[order_id] = {"uid": uid, "plan": plan}

    headers = {
        "x-client-id": os.getenv("CASHFREE_APP_ID"),
        "x-client-secret": os.getenv("CASHFREE_SECRET_KEY"),
        "x-api-version": "2022-09-01",
        "Content-Type": "application/json"
    }
    
    payload = {
        "order_id": order_id,
        "order_amount": amount,
        "order_currency": "INR",
        "customer_details": {
            "customer_id": str(uid),
            "customer_email": "support@askedge.in",
            "customer_phone": "9999999999"
        }
    }
    
    r = requests.post("https://api.cashfree.com/pg/orders",
                      json=payload, headers=headers).json()

    return r["payment_link"], order_id


@bot.callback_query_handler(func=lambda c: c.data == "pay_month")
def pay_month(call):
    uid = call.message.chat.id
    link, oid = create_payment(uid, "monthly", 30)
    bot.send_message(uid,
        f"💳 Monthly VIP — ₹30\n👉 Pay:\n{link}\n\n*After pay, click Confirm!*",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("✔ Confirm Payment", callback_data=f"chk_{oid}")
        )
    )


@bot.callback_query_handler(func=lambda c: c.data == "pay_life")
def pay_life(call):
    uid = call.message.chat.id
    link, oid = create_payment(uid, "lifetime", 59)
    bot.send_message(uid,
        f"💎 Lifetime VIP — ₹59\n👉 Pay:\n{link}\n\n*After pay, click Confirm!*",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("✔ Confirm Payment", callback_data=f"chk_{oid}")
        )
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("chk_"))
def confirm_payment(call):
    oid = call.data[4:]
    uid = call.message.chat.id

    headers = {
        "x-client-id": os.getenv("CASHFREE_APP_ID"),
        "x-client-secret": os.getenv("CASHFREE_SECRET_KEY"),
        "x-api-version": "2022-09-01"
    }
    r = requests.get(f"https://api.cashfree.com/pg/orders/{oid}",
                     headers=headers).json()

    if r.get("order_status") == "PAID":
        plan = ORDERS[oid]["plan"]
        set_vip(uid, True)
        bot.send_message(uid,
            f"🎉 VIP Activated Successfully!\nPlan: *{plan.capitalize()}*\n\n⚡ Managed by AskEdge Labs",
            reply_markup=home_menu()
        )
    else:
        bot.send_message(uid, "❌ Payment not completed yet! Try again after 10 sec.")
