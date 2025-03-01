from flask import Flask, request, jsonify
import requests
import os
import time

app = Flask(__name__)

# URLs da API para conta DEMO e REAL
API_URLS = {
    "demo": "https://demo-api-capital.backend-capital.com/api/v1",
    "real": "https://api-capital.backend-capital.com/api/v1"
}

# Configuração inicial (pegando variáveis de ambiente)
EMAIL = os.getenv("EMAIL", "seu-email@exemplo.com")
PASSWORD = os.getenv("PASSWORD", "sua-senha-segura")
API_KEYS = {
    "demo": os.getenv("DEMO_API_KEY", "sua-demo-api-key"),
    "real": os.getenv("REAL_API_KEY", "sua-real-api-key")
}

# Variáveis globais para armazenar tokens e tipo de conta
CST = None
SECURITY_TOKEN = None
API_URL = None
API_KEY = None

# Função para selecionar conta demo ou real
def selecionar_conta(tipo):
    global API_URL, API_KEY
    if tipo not in ["demo", "real"]:
        print("Tipo de conta inválido. Escolha 'demo' ou 'real'.")
        return False
    API_URL = API_URLS[tipo]
    API_KEY = API_KEYS[tipo]
    print(f"✅ Operando na conta: {tipo.upper()}")
    return True

# Função para fazer login
def login():
    global CST, SECURITY_TOKEN
    if not API_URL or not API_KEY:
        print("⚠️ Conta não selecionada. Use selecionar_conta('demo') ou selecionar_conta('real')")
        return None, None

    url = f"{API_URL}/session"
    headers = {"Content-Type": "application/json", "X-CAP-API-KEY": API_KEY}
    data = {"identifier": EMAIL, "password": PASSWORD, "encryptedPassword": False}

    try:
        response = requests.post(url, json=data, headers=headers)
        print("Status Code:", response.status_code)
        print("Headers da Resposta:", response.headers)
        print("Resposta da API:", response.text)

        if response.status_code != 200:
            return None, None

        CST = response.headers.get("CST", None)
        SECURITY_TOKEN = response.headers.get("X-SECURITY-TOKEN", None)

        if not CST or not SECURITY_TOKEN:
            print("Erro: Não foi possível capturar os tokens CST e X-SECURITY-TOKEN")
            return None, None

        print(f"🔥 Sessão ativa na {API_URL}! CST: {CST}, X-SECURITY-TOKEN: {SECURITY_TOKEN}")
        return CST, SECURITY_TOKEN

    except Exception as e:
        print("Erro ao tentar login:", str(e))
        return None, None

# Rota para login manual
@app.route("/login", methods=["POST"])
def api_login():
    tipo_conta = request.json.get("tipo", "demo")  # Se não for informado, assume DEMO
    if selecionar_conta(tipo_conta):
        cst, security_token = login()
        if cst and security_token:
            return jsonify({"CST": cst, "X-SECURITY-TOKEN": security_token})
    return jsonify({"error": "Falha no login"}), 401

# Rota para abrir uma posição
@app.route("/abrir_posicao", methods=["POST"])
def abrir_posicao():
    if not CST or not SECURITY_TOKEN:
        return jsonify({"error": "Autenticação necessária"}), 401

    url = f"{API_URL}/positions"
    headers = {
        "Content-Type": "application/json",
        "X-SECURITY-TOKEN": SECURITY_TOKEN,
        "CST": CST,
        "X-CAP-API-KEY": API_KEY
    }
    payload = {
        "epic": "BTCUSD",
        "direction": "BUY",
        "size": 1,
        "orderType": "MARKET",
        "guaranteedStop": False
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

# Rota para fechar uma posição
@app.route("/fechar_posicao", methods=["POST"])
def fechar_posicao():
    data = request.json
    deal_id = data.get("dealId")

    if not CST or not SECURITY_TOKEN:
        return jsonify({"error": "Autenticação necessária"}), 401

    url = f"{API_URL}/positions/otc"
    headers = {
        "Content-Type": "application/json",
        "X-SECURITY-TOKEN": SECURITY_TOKEN,
        "CST": CST,
        "X-CAP-API-KEY": API_KEY
    }
    payload = {
        "dealId": deal_id,
        "size": 1,
        "orderType": "MARKET"
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
