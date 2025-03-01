from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Configuração inicial
API_URL = "https://api-capital.backend-capital.com/api/v1"
EMAIL = os.getenv("EMAIL", "seu-email@exemplo.com")  # Pegando do ambiente
PASSWORD = os.getenv("PASSWORD", "sua-senha-segura")  # Pegando do ambiente
API_KEY = os.getenv("API_KEY", "sua-api-key")  # Pegando do ambiente

# Função para fazer login
def login():
    url = f"{API_URL}/session"
    headers = {"Content-Type": "application/json", "X-CAP-API-KEY": API_KEY}
    data = {"identifier": EMAIL, "password": PASSWORD, "encryptedPassword": False}

    try:
        print("Tentando login na API da Capital.com...")
        print(f"URL: {url}")
        print(f"Headers: {headers}")
        print(f"Payload: {data}")

        response = requests.post(url, json=data, headers=headers)

        print("Status Code:", response.status_code)
        print("Resposta da API:", response.text)  # Debug: imprime a resposta completa

        session_data = response.json()

        if "CST" not in session_data or "X-SECURITY-TOKEN" not in session_data:
            print("Erro: A resposta da API não contém CST ou X-SECURITY-TOKEN")
            return None, None  # Retorna erro sem quebrar o código

        return session_data["CST"], session_data["X-SECURITY-TOKEN"]

    except Exception as e:
        print("Erro ao tentar login:", str(e))
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
