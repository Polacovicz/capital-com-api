from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Configuração inicial
API_URL = "https://api-capital.backend-capital.com/api/v1"
EMAIL = "juliocesarklamt@outlook.com"
PASSWORD = "99156617aA**"
API_KEY = "cuSRmE6dgNQnA5tw"

# Função para fazer login
def login():
    url = f"{API_URL}/session"
    headers = {"Content-Type": "application/json", "X-CAP-API-KEY": API_KEY}
    data = {"identifier": EMAIL, "password": PASSWORD, "encryptedPassword": False}
    
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        session_data = response.json()
        return session_data["CST"], session_data["X-SECURITY-TOKEN"]
    return None, None

# Rota para login
@app.route("/login", methods=["POST"])
def api_login():
    cst, security_token = login()
    if cst and security_token:
        return jsonify({"CST": cst, "X-SECURITY-TOKEN": security_token})
    return jsonify({"error": "Falha no login"}), 401

# Rota para abrir uma posição
@app.route("/abrir_posicao", methods=["POST"])
def abrir_posicao():
    data = request.json
    cst = data.get("CST")
    security_token = data.get("X-SECURITY-TOKEN")
    
    url = f"{API_URL}/positions"
    headers = {
        "Content-Type": "application/json",
        "X-SECURITY-TOKEN": security_token,
        "CST": cst,
        "X-CAP-API-KEY": API_KEY
    }
    payload = {
        "epic": "US500",  # Código do S&P 500
        "direction": "BUY",  # Compra
        "size": 1,  # Quantidade de contratos
        "orderType": "MARKET",
        "guaranteedStop": False
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

# Rota para fechar uma posição
@app.route("/fechar_posicao", methods=["POST"])
def fechar_posicao():
    data = request.json
    cst = data.get("CST")
    security_token = data.get("X-SECURITY-TOKEN")
    deal_id = data.get("dealId")
    
    url = f"{API_URL}/positions/otc"
    headers = {
        "Content-Type": "application/json",
        "X-SECURITY-TOKEN": security_token,
        "CST": cst,
        "X-CAP-API-KEY": API_KEY
    }
    payload = {
        "dealId": deal_id,
        "size": 1,  # Fechar toda a posição
        "orderType": "MARKET"
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render usa porta dinâmica
    app.run(host="0.0.0.0", port=port)
