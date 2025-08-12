from flask import Flask, render_template, request, jsonify
import requests
import time
import hashlib

app = Flask(__name__)

# CLICK Pass credentials (move to .env for production)
CLICK_MERCHANT_ID = 29185
CLICK_SERVICE_ID = 75200
CLICK_MERCHANT_USER_ID = 57196
CLICK_SECRET_KEY = 'TgCA32QnlcKhtmmOTA'

CLICK_API = "https://api.click.uz/v2/merchant"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/pay", methods=["POST"])
def pay():
    data = request.json
    otp_data = data.get("token")  # QR content
    amount = float(data.get("amount"))  # Amount in UZS
    transaction_id = str(int(time.time()))

    # 1. Auth header
    timestamp = str(int(time.time()))
    digest = hashlib.sha1((timestamp + CLICK_SECRET_KEY).encode()).hexdigest()
    auth_header = f"{CLICK_MERCHANT_USER_ID}:{digest}:{timestamp}"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Auth": auth_header
    }

    # 2. Make payment request
    payload = {
        "service_id": CLICK_SERVICE_ID,
        "otp_data": otp_data,
        "amount": amount,
        "cashbox_code": "KASSA-1",
        "transaction_id": transaction_id
    }

    try:
        r = requests.post(f"{CLICK_API}/click_pass/payment", json=payload, headers=headers, timeout=10)
        r.raise_for_status()
        res = r.json()
    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "step": "payment", "message": str(e)})

    if res.get("error_code") != 0:
        return jsonify({"status": "error", "step": "payment", "response": res})

    # 3. Confirm payment if needed
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

    return jsonify({"status": "success", "response": res})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

