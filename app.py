from flask import Flask, request, jsonify
import requests
import os
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field

app = Flask(__name__)

# Configurações
@dataclass
class Config:
    API_URLS: Dict[str, str] = field(default_factory=lambda: {
        "demo": "https://demo-api-capital.backend-capital.com/api/v1",
        "real": "https://api-capital.backend-capital.com/api/v1"
    })
    EMAIL: str = os.getenv("EMAIL", "seu-email@exemplo.com")
    PASSWORD: str = os.getenv("PASSWORD", "sua-senha-segura")
    API_KEYS: Dict[str, str] = field(default_factory=lambda: {
        "demo": os.getenv("DEMO_API_KEY", "sua-demo-api-key"),
        "real": os.getenv("REAL_API_KEY", "sua-real-api-key")
    })

# Instância global de Config
config = Config()

class CapitalClient:
    def __init__(self):
        self.api_url: Optional[str] = None
        self.api_key: Optional[str] = None
        self.cst: Optional[str] = None
        self.security_token: Optional[str] = None
        self.account_type: Optional[str] = None

    def select_account(self, account_type: str) -> bool:
        if account_type not in ["demo", "real"]:
            return False
        self.account_type = account_type
        self.api_url = config.API_URLS[account_type]
        self.api_key = config.API_KEYS[account_type]
        return True

    def login(self) -> Tuple[Optional[str], Optional[str]]:
        if not self.api_url or not self.api_key:
            return None, None
        url = f"{self.api_url}/session"
        headers = {"Content-Type": "application/json", "X-CAP-API-KEY": self.api_key}
        data = {"identifier": config.EMAIL, "password": config.PASSWORD, "encryptedPassword": False}
        try:
            response = requests.post(url, json=data, headers=headers)
            if response.status_code != 200:
                return None, None
            self.cst = response.headers.get("CST")
            self.security_token = response.headers.get("X-SECURITY-TOKEN")
            return self.cst, self.security_token
        except requests.RequestException as e:
            print(f"Login error: {e}")
            return None, None

    def get_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-SECURITY-TOKEN": self.security_token,
            "CST": self.cst,
            "X-CAP-API-KEY": self.api_key
        }

    def api_request(self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict:
        if not self.cst or not self.security_token:
            self.login()
            if not self.cst or not self.security_token:
                return {"error": "Authentication required"}
        url = f"{self.api_url}/{endpoint}"
        headers = self.get_headers()
        try:
            response = requests.request(method, url, json=data, params=params, headers=headers)
            response.raise_for_status()
            return response.json() if response.content else {"status": "SUCCESS"}
        except requests.RequestException as e:
            return {"error": str(e), "status_code": e.response.status_code if e.response else None}

# Instância do cliente
client = CapitalClient()

# Função auxiliar para validação de conta e autenticação
def validate_and_auth(account_type: str) -> Tuple[bool, Dict, int]:
    if not client.select_account(account_type):
        return False, {"error": "Invalid account type"}, 400
    if not client.cst or not client.security_token:
        cst, token = client.login()
        if not cst or not token:
            return False, {"error": "Authentication failed"}, 401
    return True, {}, 200

# General Endpoints
@app.route("/time", methods=["GET"])
def get_server_time():
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    result = client.api_request("GET", "time")
    return jsonify(result), 400 if "error" in result else 200

@app.route("/ping", methods=["GET"])
def api_ping():
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    result = client.api_request("GET", "ping")
    return jsonify(result), 400 if "error" in result else 200

# Session Endpoints
@app.route("/session/encryption_key", methods=["GET"])
def get_encryption_key():
    account_type = request.args.get("type", "demo")
    if not client.select_account(account_type):
        return jsonify({"error": "Invalid account type"}), 400
    url = f"{client.api_url}/session/encryptionKey"
    headers = {"X-CAP-API-KEY": client.api_key}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 400

@app.route("/session", methods=["GET"])
def get_session_details():
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    result = client.api_request("GET", "session")
    return jsonify(result), 400 if "error" in result else 200

@app.route("/session", methods=["POST"])
def create_session():
    account_type = request.json.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    cst, token = client.login()
    if not cst or not token:
        return jsonify({"error": "Failed to create session"}), 400
    return jsonify({"CST": cst, "X-SECURITY-TOKEN": token}), 200

@app.route("/login", methods=["GET"])
def get_login_status():
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    return jsonify({"CST": client.cst, "X-SECURITY-TOKEN": client.security_token}), 200

@app.route("/login", methods=["POST"])
def api_login():
    account_type = request.json.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    return jsonify({"CST": client.cst, "X-SECURITY-TOKEN": client.security_token}), 200

@app.route("/session/switch", methods=["PUT"])
def switch_account():
    account_type = request.json.get("type", "demo")
    account_id = request.json.get("accountId")
    if not account_id:
        return jsonify({"error": "accountId is required"}), 400
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    payload = {"accountId": account_id}
    result = client.api_request("PUT", "session", data=payload)
    return jsonify(result), 400 if "error" in result else 200

@app.route("/session", methods=["DELETE"])
def logout():
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    result = client.api_request("DELETE", "session")
    client.cst = None
    client.security_token = None
    return jsonify(result), 400 if "error" in result else 200

# Accounts Endpoints
@app.route("/accounts", methods=["GET"])
def get_accounts():
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    result = client.api_request("GET", "accounts")
    return jsonify(result), 400 if "error" in result else 200

@app.route("/accounts/preferences", methods=["GET"])
def get_account_preferences():
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    result = client.api_request("GET", "accounts/preferences")
    return jsonify(result), 400 if "error" in result else 200

@app.route("/accounts/preferences", methods=["PUT"])
def update_account_preferences():
    account_type = request.json.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    payload = {
        "leverages": request.json.get("leverages"),
        "hedgingMode": request.json.get("hedgingMode")
    }
    result = client.api_request("PUT", "accounts/preferences", data=payload)
    return jsonify(result), 400 if "error" in result else 200

@app.route("/accounts/history/activity", methods=["GET"])
def get_account_activity():
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    params = {
        "from": request.args.get("from"),
        "to": request.args.get("to"),
        "lastPeriod": request.args.get("lastPeriod"),
        "detailed": request.args.get("detailed"),
        "dealId": request.args.get("dealId"),
        "filter": request.args.get("filter")
    }
    result = client.api_request("GET", "history/activity", params=params)
    return jsonify(result), 400 if "error" in result else 200

@app.route("/accounts/history/transactions", methods=["GET"])
def get_transactions():
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    params = {
        "from": request.args.get("from"),
        "to": request.args.get("to"),
        "lastPeriod": request.args.get("lastPeriod"),
        "type": request.args.get("type")
    }
    result = client.api_request("GET", "history/transactions", params=params)
    return jsonify(result), 400 if "error" in result else 200

@app.route("/accounts/topup", methods=["POST"])
def topup_demo_account():
    account_type = request.json.get("type", "demo")
    amount = request.json.get("amount")
    if not amount:
        return jsonify({"error": "amount is required"}), 400
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    payload = {"amount": amount}
    result = client.api_request("POST", "accounts/topUp", data=payload)
    return jsonify(result), 400 if "error" in result else 200

# Trading Endpoints
@app.route("/confirm/<deal_reference>", methods=["GET"])
def confirm_trade(deal_reference):
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    result = client.api_request("GET", f"confirms/{deal_reference}")
    return jsonify(result), 400 if "error" in result else 200

# Trading > Positions
@app.route("/positions", methods=["GET"])
def get_positions():
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    result = client.api_request("GET", "positions")
    return jsonify(result), 400 if "error" in result else 200

@app.route("/open_position", methods=["POST"])
def open_position():
    account_type = request.json.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    payload = {
        "epic": request.json.get("epic"),
        "direction": request.json.get("direction"),
        "size": request.json.get("size"),
        "guaranteedStop": request.json.get("guaranteedStop", False),
        "trailingStop": request.json.get("trailingStop", False),
        "stopLevel": request.json.get("stopLevel"),
        "stopDistance": request.json.get("stopDistance"),
        "stopAmount": request.json.get("stopAmount"),
        "profitLevel": request.json.get("profitLevel"),
        "profitDistance": request.json.get("profitDistance"),
        "profitAmount": request.json.get("profitAmount")
    }
    if not all([payload["epic"], payload["direction"], payload["size"]]):
        return jsonify({"error": "epic, direction, and size are required"}), 400
    result = client.api_request("POST", "positions", data=payload)
    return jsonify(result), 400 if "error" in result else 200

@app.route("/positions/<deal_id>", methods=["GET"])
def get_single_position(deal_id):
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    result = client.api_request("GET", f"positions/{deal_id}")
    return jsonify(result), 400 if "error" in result else 200

@app.route("/positions/<deal_id>", methods=["PUT"])
def update_position(deal_id):
    account_type = request.json.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    payload = {
        "guaranteedStop": request.json.get("guaranteedStop"),
        "trailingStop": request.json.get("trailingStop"),
        "stopLevel": request.json.get("stopLevel"),
        "stopDistance": request.json.get("stopDistance"),
        "stopAmount": request.json.get("stopAmount"),
        "profitLevel": request.json.get("profitLevel"),
        "profitDistance": request.json.get("profitDistance"),
        "profitAmount": request.json.get("profitAmount")
    }
    result = client.api_request("PUT", f"positions/{deal_id}", data=payload)
    return jsonify(result), 400 if "error" in result else 200

@app.route("/close_position", methods=["DELETE"])
def close_position():
    account_type = request.args.get("type", "demo")
    deal_id = request.args.get("dealId")
    if not deal_id:
        return jsonify({"error": "dealId is required"}), 400
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    result = client.api_request("DELETE", f"positions/{deal_id}")
    return jsonify(result), 400 if "error" in result else 200

# Trading > Orders
@app.route("/workingorders", methods=["GET"])
def get_working_orders():
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    result = client.api_request("GET", "workingorders")
    return jsonify(result), 400 if "error" in result else 200

@app.route("/workingorders", methods=["POST"])
def create_working_order():
    account_type = request.json.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    payload = {
        "direction": request.json.get("direction"),
        "epic": request.json.get("epic"),
        "size": request.json.get("size"),
        "level": request.json.get("level"),
        "type": request.json.get("type"),
        "goodTillDate": request.json.get("goodTillDate"),
        "guaranteedStop": request.json.get("guaranteedStop", False),
        "trailingStop": request.json.get("trailingStop", False),
        "stopLevel": request.json.get("stopLevel"),
        "stopDistance": request.json.get("stopDistance"),
        "stopAmount": request.json.get("stopAmount"),
        "profitLevel": request.json.get("profitLevel"),
        "profitDistance": request.json.get("profitDistance"),
        "profitAmount": request.json.get("profitAmount")
    }
    if not all([payload["direction"], payload["epic"], payload["size"], payload["level"], payload["type"]]):
        return jsonify({"error": "direction, epic, size, level, and type are required"}), 400
    result = client.api_request("POST", "workingorders", data=payload)
    return jsonify(result), 400 if "error" in result else 200

@app.route("/workingorders/<deal_id>", methods=["PUT"])
def update_working_order(deal_id):
    account_type = request.json.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    payload = {
        "level": request.json.get("level"),
        "goodTillDate": request.json.get("goodTillDate"),
        "guaranteedStop": request.json.get("guaranteedStop"),
        "trailingStop": request.json.get("trailingStop"),
        "stopLevel": request.json.get("stopLevel"),
        "stopDistance": request.json.get("stopDistance"),
        "stopAmount": request.json.get("stopAmount"),
        "profitLevel": request.json.get("profitLevel"),
        "profitDistance": request.json.get("profitDistance"),
        "profitAmount": request.json.get("profitAmount")
    }
    result = client.api_request("PUT", f"workingorders/{deal_id}", data=payload)
    return jsonify(result), 400 if "error" in result else 200

@app.route("/workingorders/<deal_id>", methods=["DELETE"])
def delete_working_order(deal_id):
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    result = client.api_request("DELETE", f"workingorders/{deal_id}")
    return jsonify(result), 400 if "error" in result else 200

# Markets Info > Markets
@app.route("/marketnavigation", methods=["GET"])
def get_market_categories():
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    result = client.api_request("GET", "marketnavigation")
    return jsonify(result), 400 if "error" in result else 200

@app.route("/marketnavigation/<node_id>", methods=["GET"])
def get_category_subnodes(node_id):
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    params = {"limit": request.args.get("limit")}
    result = client.api_request("GET", f"marketnavigation/{node_id}", params=params)
    return jsonify(result), 400 if "error" in result else 200

@app.route("/markets", methods=["GET"])
def get_markets_details():
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    params = {
        "searchTerm": request.args.get("searchTerm"),
        "epics": request.args.get("epics")
    }
    result = client.api_request("GET", "markets", params=params)
    return jsonify(result), 400 if "error" in result else 200

@app.route("/markets/<epic>", methods=["GET"])
def get_single_market(epic):
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    result = client.api_request("GET", f"markets/{epic}")
    return jsonify(result), 400 if "error" in result else 200

# Markets Info > Prices
@app.route("/prices/<epic>", methods=["GET"])
def get_historical_prices(epic):
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    params = {
        "resolution": request.args.get("resolution"),
        "max": request.args.get("max"),
        "from": request.args.get("from"),
        "to": request.args.get("to")
    }
    result = client.api_request("GET", f"prices/{epic}", params=params)
    return jsonify(result), 400 if "error" in result else 200

# Markets Info > Client Sentiment
@app.route("/clientsentiment", methods=["GET"])
def get_client_sentiment():
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    params = {"marketIds": request.args.get("marketIds")}
    result = client.api_request("GET", "clientsentiment", params=params)
    return jsonify(result), 400 if "error" in result else 200

@app.route("/clientsentiment/<market_id>", methods=["GET"])
def get_single_sentiment(market_id):
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    result = client.api_request("GET", f"clientsentiment/{market_id}")
    return jsonify(result), 400 if "error" in result else 200

# Watchlists
@app.route("/watchlists", methods=["GET"])
def get_watchlists():
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    result = client.api_request("GET", "watchlists")
    return jsonify(result), 400 if "error" in result else 200

@app.route("/watchlists", methods=["POST"])
def create_watchlist():
    account_type = request.json.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    payload = {
        "name": request.json.get("name"),
        "epics": request.json.get("epics")
    }
    if not payload["name"]:
        return jsonify({"error": "name is required"}), 400
    result = client.api_request("POST", "watchlists", data=payload)
    return jsonify(result), 400 if "error" in result else 200

@app.route("/watchlists/<watchlist_id>", methods=["GET"])
def get_single_watchlist(watchlist_id):
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    result = client.api_request("GET", f"watchlists/{watchlist_id}")
    return jsonify(result), 400 if "error" in result else 200

@app.route("/watchlists/<watchlist_id>", methods=["PUT"])
def add_to_watchlist(watchlist_id):
    account_type = request.json.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    payload = {"epic": request.json.get("epic")}
    if not payload["epic"]:
        return jsonify({"error": "epic is required"}), 400
    result = client.api_request("PUT", f"watchlists/{watchlist_id}", data=payload)
    return jsonify(result), 400 if "error" in result else 200

@app.route("/watchlists/<watchlist_id>", methods=["DELETE"])
def delete_watchlist(watchlist_id):
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    result = client.api_request("DELETE", f"watchlists/{watchlist_id}")
    return jsonify(result), 400 if "error" in result else 200

@app.route("/watchlists/<watchlist_id>/<epic>", methods=["DELETE"])
def remove_from_watchlist(watchlist_id, epic):
    account_type = request.args.get("type", "demo")
    success, error, status = validate_and_auth(account_type)
    if not success:
        return jsonify(error), status
    result = client.api_request("DELETE", f"watchlists/{watchlist_id}/{epic}")
    return jsonify(result), 400 if "error" in result else 200

# Adicionando um handler básico para a raiz (opcional, para evitar 404)
@app.route("/", methods=["GET"])
def root():
    return jsonify({"message": "Welcome to the Capital.com API Client", "status": "running"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
