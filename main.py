from flask import Flask, render_template, request, jsonify
import requests
import time
import hashlib

app = Flask(__name__)

# CLICK Pass credentials (move to .env for production)
CLICK_MERCHANT_ID = 15907
CLICK_SERVICE_ID = 83959
CLICK_MERCHANT_USER_ID = 65019
CLICK_SECRET_KEY = 'En80cfmebut4axEJ'

CLICK_API = "https://api.click.uz/v2/merchant"

# Telegram credentials
TELEGRAM_BOT_TOKEN = "8429261662:AAEHM6epwtqQPbvs-Ci9akw1CqGuBKKQA0k"
TELEGRAM_CHAT_ID = "-4879332986"

@app.route("/test-telegram", methods=["GET"])
def test_telegram():
    """Test Telegram connection"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return jsonify({
            "status": "error", 
            "message": "Telegram credentials not configured"
        })
    
    test_message = "🧪 Test message from Click Pass Scanner"
    success = send_telegram_message(test_message)
    
    return jsonify({
        "status": "success" if success else "error",
        "message": "Message sent successfully" if success else "Failed to send message - check logs",
        "bot_token_configured": bool(TELEGRAM_BOT_TOKEN),
        "chat_id_configured": bool(TELEGRAM_CHAT_ID)
    })

def send_telegram_message(message):
    """Send a message to Telegram group"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials not configured")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        if not result.get('ok', False):
            print(f"Telegram API error: {result.get('description', 'Unknown error')}")
            return False
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to send Telegram message: HTTP {getattr(e.response, 'status_code', 'unknown')} error")
        return False
    except ValueError:
        print("Failed to parse Telegram API response")
        return False

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/pay", methods=["POST"])
def pay():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"status": "error", "message": "No JSON received"}), 400

    otp_data = data.get("token")
    if not otp_data:
        return jsonify({"status": "error", "message": "Token is required"}), 400

    try:
        amount = float(data.get("amount", 0))
        if amount <= 0:
            return jsonify({"status": "error", "message": "Amount must be positive"}), 400
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Invalid amount format"}), 400

    description = data.get("description", "")
    transaction_id = str(int(time.time()))

    # Auth header
    timestamp = str(int(time.time()))
    digest = hashlib.sha1((timestamp + CLICK_SECRET_KEY).encode()).hexdigest()
    auth_header = f"{CLICK_MERCHANT_USER_ID}:{digest}:{timestamp}"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Auth": auth_header
    }

    payload = {
        "service_id": CLICK_SERVICE_ID,
        "otp_data": otp_data,
        "amount": amount,
        "cashbox_code": "KASSA-1",
        "transaction_id": transaction_id
    }

    # 1. Send payment
    try:
        r = requests.post(f"{CLICK_API}/click_pass/payment", json=payload, headers=headers, timeout=10)
        r.raise_for_status()
        res = r.json()
    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "step": "payment", "message": str(e)})

    if res.get("error_code") != 0:
        return jsonify({"status": "error", "step": "payment", "response": res})

    # 2. Confirm payment if required
    if res.get("confirm_mode") == 1:
        confirm_payload = {
            "service_id": CLICK_SERVICE_ID,
            "payment_id": res.get("payment_id")
        }
        try:
            r2 = requests.post(f"{CLICK_API}/click_pass/confirm", json=confirm_payload, headers=headers, timeout=10)
            r2.raise_for_status()
            confirm_res = r2.json()
            if confirm_res.get("error_code") != 0:
                return jsonify({"status": "error", "step": "confirm", "response": confirm_res})
        except requests.exceptions.RequestException as e:
            return jsonify({"status": "error", "step": "confirm", "message": str(e)})

    # 3. Send Telegram notification
    success_message = f"""
🎉 <b>Payment Successful!</b>

💰 <b>Amount:</b> {amount:,.0f} UZS
🆔 <b>Transaction ID:</b> {transaction_id}
🏪 <b>Merchant:</b> CLICK Payment
⏰ <b>Time:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}

✅ Payment has been processed successfully!
    """
    send_telegram_message(success_message.strip())

    return jsonify({"status": "success", "response": res})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
