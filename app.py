from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# URLs da API para conta DEMO e REAL
API_URLS = {
    "demo": "https://demo-api-capital.backend-capital.com/api/v1",
    "real": "https://api-capital.backend-capital.com/api/v1"
}

# Configuração inicial (variáveis de ambiente)
EMAIL = os.getenv("EMAIL", "seu-email@exemplo.com")
PASSWORD = os.getenv("PASSWORD", "sua-senha-segura")
API_KEYS = {
    "demo": os.getenv("DEMO_API_KEY", "sua-demo-api-key"),
    "real": os.getenv("REAL_API_KEY", "sua-real-api-key")
}

# Variáveis globais para tokens e URL
CST = None
SECURITY_TOKEN = None
API_URL = None
API_KEY = None

def select_account(account_type):
    global API_URL, API_KEY
    if account_type not in ["demo", "real"]:
        print("Invalid account type. Choose 'demo' or 'real'.")
        return False
    API_URL = API_URLS[account_type]
    API_KEY = API_KEYS[account_type]
    print(f"Operating on {account_type.upper()} account.")
    return True

def login():
    global CST, SECURITY_TOKEN
    if not API_URL or not API_KEY:
        print("Account not selected. Use select_account('demo') or select_account('real').")
        return None, None
    url = f"{API_URL}/session"
    headers = {"Content-Type": "application/json", "X-CAP-API-KEY": API_KEY}
    data = {"identifier": EMAIL, "password": PASSWORD, "encryptedPassword": False}
    try:
        response = requests.post(url, json=data, headers=headers)
        print("Status Code:", response.status_code)
        print("Response Headers:", response.headers)
        print("API Response:", response.text)
        if response.status_code != 200:
            return None, None
        CST = response.headers.get("CST", None)
        SECURITY_TOKEN = response.headers.get("X-SECURITY-TOKEN", None)
        if not CST or not SECURITY_TOKEN:
            print("Could not retrieve tokens CST and X-SECURITY-TOKEN.")
            return None, None
        print(f"Active session at {API_URL}! CST: {CST}, X-SECURITY-TOKEN: {SECURITY_TOKEN}")
        return CST, SECURITY_TOKEN
    except Exception as e:
        print("Login error:", str(e))
        return None, None

# Endpoint para login manual
@app.route("/login", methods=["POST"])
def api_login():
    account_type = request.json.get("type", "demo")
    if select_account(account_type):
        cst, security_token = login()
        if cst and security_token:
            return jsonify({"CST": cst, "X-SECURITY-TOKEN": security_token})
    return jsonify({"error": "Login failed"}), 401

# Endpoint para abrir uma posição
@app.route("/open_position", methods=["POST"])
def open_position():
    data = request.json
    account_type = data.get("type", "demo")
    epic = data.get("epic", "BTCUSD")
    size = data.get("size", 1)
    direction = data.get("direction", "BUY")  # Aceita "BUY" ou "SELL"
    stop_loss = data.get("stopLoss", None)
    take_profit = data.get("takeProfit", None)

    if not select_account(account_type):
        return jsonify({"error": "Invalid account"}), 400

    cst, security_token = login()
    if not cst or not security_token:
        return jsonify({"error": "Authentication required"}), 401

    url = f"{API_URL}/positions"
    headers = {
        "Content-Type": "application/json",
        "X-SECURITY-TOKEN": security_token,
        "CST": cst,
        "X-CAP-API-KEY": API_KEY
    }
    # Conforme a documentação, a payload inclui apenas os campos necessários
    payload = {
        "epic": epic,
        "direction": direction,
        "size": size,
        "guaranteedStop": False
    }
    if stop_loss:
        payload["stopLevel"] = stop_loss
    if take_profit:
        payload["profitLevel"] = take_profit

    response = requests.post(url, json=payload, headers=headers)
    return jsonify(response.json())

# Endpoint para fechar uma posição
@app.route("/close_position", methods=["POST"])
def close_position():
    data = request.json
    account_type = data.get("type", "demo")
    deal_id = data.get("dealId")

    if not select_account(account_type):
        return jsonify({"error": "Invalid account"}), 400

    cst, security_token = login()
    if not cst or not security_token:
        return jsonify({"error": "Authentication required"}), 401

    url = f"{API_URL}/positions/{deal_id}"
    headers = {
        "Content-Type": "application/json",
        "X-SECURITY-TOKEN": security_token,
        "CST": cst,
        "X-CAP-API-KEY": API_KEY
    }
    response = requests.delete(url, headers=headers)
    return jsonify(response.json())

# Endpoint para enviar ping e manter a sessão ativa
@app.route("/ping", methods=["GET"])
def api_ping():
    account_type = request.args.get("type", "demo")
    if not select_account(account_type):
        return jsonify({"error": "Invalid account"}), 400

    cst, security_token = login()
    if not cst or not security_token:
        return jsonify({"error": "Authentication required"}), 401

    url = f"{API_URL}/ping"
    headers = {
        "Content-Type": "application/json",
        "X-SECURITY-TOKEN": security_token,
        "CST": cst,
        "X-CAP-API-KEY": API_KEY
    }
    response = requests.get(url, headers=headers)
    return jsonify(response.json())

# Endpoint para obter informações da conta
@app.route("/account", methods=["GET"])
def get_account():
    account_type = request.args.get("type", "demo")
    if not select_account(account_type):
        return jsonify({"error": "Invalid account"}), 400

    cst, security_token = login()
    if not cst or not security_token:
        return jsonify({"error": "Authentication required"}), 401

    url = f"{API_URL}/accounts"
    headers = {
        "Content-Type": "application/json",
        "X-SECURITY-TOKEN": security_token,
        "CST": cst,
        "X-CAP-API-KEY": API_KEY
    }
    response = requests.get(url, headers=headers)
    return jsonify(response.json())

# Endpoint para listar todas as posições abertas
@app.route("/positions", methods=["GET"])
def get_positions():
    account_type = request.args.get("type", "demo")
    if not select_account(account_type):
        return jsonify({"error": "Invalid account"}), 400

    cst, security_token = login()
    if not cst or not security_token:
        return jsonify({"error": "Authentication required"}), 401

    url = f"{API_URL}/positions"
    headers = {
        "Content-Type": "application/json",
        "X-SECURITY-TOKEN": security_token,
        "CST": cst,
        "X-CAP-API-KEY": API_KEY
    }
    response = requests.get(url, headers=headers)
    return jsonify(response.json())

# Endpoint para confirmar o status de um trade via dealReference
@app.route("/confirm/<deal_reference>", methods=["GET"])
def confirm_trade(deal_reference):
    account_type = request.args.get("type", "demo")
    if not select_account(account_type):
        return jsonify({"error": "Invalid account"}), 400

    cst, security_token = login()
    if not cst or not security_token:
        return jsonify({"error": "Authentication required"}), 401

    url = f"{API_URL}/confirms/{deal_reference}"
    headers = {
        "Content-Type": "application/json",
        "X-SECURITY-TOKEN": security_token,
        "CST": cst,
        "X-CAP-API-KEY": API_KEY
    }
    response = requests.get(url, headers=headers)
    return jsonify(response.json())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
