import os
import logging
import requests
from flask import Flask, request, jsonify

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carrega credenciais de ambiente (para segurança das credenciais)
API_KEY = os.environ.get("CAPITAL_API_KEY")
USERNAME = os.environ.get("CAPITAL_LOGIN") or os.environ.get("CAPITAL_USERNAME")
PASSWORD = os.environ.get("CAPITAL_PASSWORD")
# Determina URL base (live ou demo) a partir de variável de ambiente
API_MODE = os.environ.get("CAPITAL_API_MODE", "live").lower()
if API_MODE not in ["live", "demo"]:
    API_MODE = "live"
BASE_URL = "https://api-capital.backend-capital.com/api/v1"
if API_MODE == "demo":
    BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1"

# Verifica se credenciais essenciais foram fornecidas
if not API_KEY or not USERNAME or not PASSWORD:
    logger.error("Credenciais da API ausentes. Defina CAPITAL_API_KEY, CAPITAL_LOGIN e CAPITAL_PASSWORD.")
    # Não encerramos a aplicação aqui, mas as requisições falharão sem essas credenciais.

# Inicializa o app Flask
app = Flask(__name__)

class CapitalAPI:
    def __init__(self, api_key, username, password, base_url):
        self.api_key = api_key
        self.username = username
        self.password = password
        self.base_url = base_url
        self.session = requests.Session()
        # Define o cabeçalho da chave de API para todas as requisições
        self.session.headers.update({"X-CAP-API-KEY": self.api_key})
        # Tokens de sessão serão armazenados após autenticação
        self.authenticated = False

    def authenticate(self):
        """
        Autentica na API da Capital.com usando as credenciais fornecidas.
        Reutiliza tokens existentes se já estiver autenticado.
        """
        if self.authenticated:
            return  # Já autenticado (tokens já definidos)
        login_url = f"{self.base_url}/session"
        payload = {
            "identifier": self.username,
            "password": self.password,
            "encryptedPassword": False
        }
        try:
            response = self.session.post(login_url, json=payload)
        except Exception as e:
            logger.error(f"Erro de conexão em {login_url}: {e}")
            raise APIError(500, "Erro interno ao autenticar.")
        if response.status_code != 200:
            # Falha na autenticação
            error_info = None
            try:
                if response.headers.get("Content-Type", "").startswith("application/json"):
                    error_info = response.json().get("errorCode") or response.json()
            except ValueError:
                error_info = response.text
            error_info = error_info or response.text or "Erro desconhecido"
            logger.error(f"Falha na autenticação: {error_info}")
            raise APIError(response.status_code, f"Falha na autenticação: {error_info}")
        # Extrai tokens do cabeçalho de resposta
        cst = response.headers.get("CST")
        security_token = response.headers.get("X-SECURITY-TOKEN")
        if not cst or not security_token:
            logger.error("Resposta de autenticação não forneceu tokens de segurança.")
            raise APIError(500, "Tokens de autenticação não recebidos da API.")
        # Atualiza cabeçalhos da sessão com tokens para próximas requisições
        self.session.headers.update({"CST": cst, "X-SECURITY-TOKEN": security_token})
        self.authenticated = True
        logger.info("Autenticação bem-sucedida, tokens de sessão obtidos.")

    def request(self, method, endpoint, **kwargs):
        """
        Handler genérico de requisições que garante autenticação e trata erros.
        """
        self.authenticate()
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
        except Exception as e:
            logger.error(f"Requisição falhou: {e}")
            raise APIError(500, f"Falha na requisição para {endpoint} (erro de conexão).")
        # Se o token expirou ou acesso não autorizado, tenta reautenticar uma vez
        if response.status_code == 401:
            logger.info("Sessão expirada ou não autorizada. Reautenticando...")
            self.authenticated = False
            self.session.headers.pop("CST", None)
            self.session.headers.pop("X-SECURITY-TOKEN", None)
            self.authenticate()
            try:
                response = self.session.request(method, url, **kwargs)
            except Exception as e:
                logger.error(f"Requisição falhou após reautenticação: {e}")
                raise APIError(500, f"Falha na requisição para {endpoint} após reautenticar.")
        # Trata erros (códigos 4xx/5xx)
        if response.status_code >= 400:
            error_msg = ""
            try:
                data = response.json()
                error_msg = data.get("errorCode") or data.get("message") or str(data)
            except ValueError:
                error_msg = response.text or "Erro desconhecido"
            logger.error(f"Erro da API {response.status_code} em {endpoint}: {error_msg}")
            raise APIError(response.status_code, error_msg)
        # Retorna dados JSON, se disponíveis, caso contrário texto bruto
        if response.headers.get("Content-Type", "").startswith("application/json"):
            return response.json()
        else:
            return response.text

# Exceção customizada para erros da API
class APIError(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code
        self.message = message

# Instancia o cliente da API Capital.com
capital_api = CapitalAPI(API_KEY, USERNAME, PASSWORD, BASE_URL)

# Handler de erro para APIError
@app.errorhandler(APIError)
def handle_api_error(error):
    response = jsonify({"error": error.message})
    response.status_code = error.status_code
    return response

# Handler de erro genérico (para erros inesperados)
@app.errorhandler(Exception)
def handle_general_error(error):
    logger.exception("Erro inesperado: %s", error)
    response = jsonify({"error": "Erro interno no servidor"})
    response.status_code = 500
    return response

# --- Endpoints de Autenticação ---

@app.route("/session", methods=["POST"])
def login():
    """
    Inicia uma nova sessão (login).
    As credenciais são lidas das variáveis de ambiente por segurança.
    Retorna confirmação de sucesso na autenticação.
    """
    # Opcionalmente, poderíamos aceitar credenciais via JSON no request para sobrescrever as de ambiente.
    capital_api.authenticated = False  # reseta qualquer sessão existente
    capital_api.session.headers.pop("CST", None)
    capital_api.session.headers.pop("X-SECURITY-TOKEN", None)
    capital_api.authenticate()
    return jsonify({"message": "Autenticado com sucesso"}), 200

@app.route("/session", methods=["GET"])
def get_session_status():
    """
    Obtém informações da sessão atual, incluindo detalhes da conta ativa.
    """
    data = capital_api.request("GET", "/session")
    return jsonify(data), 200

@app.route("/session", methods=["PUT"])
def switch_account():
    """
    Altera a conta financeira ativa na sessão.
    Espera um JSON {"accountId": "..."} no corpo da requisição.
    """
    if not request.is_json:
        raise APIError(400, "Corpo JSON com accountId é obrigatório.")
    body = request.get_json()
    account_id = body.get("accountId")
    if not account_id:
        raise APIError(400, "accountId é obrigatório para trocar de conta.")
    data = capital_api.request("PUT", "/session", json={"accountId": account_id})
    return jsonify(data), 200

# --- Endpoints de Contas ---

@app.route("/accounts", methods=["GET"])
def get_accounts():
    """
    Obtém a lista de todas as contas financeiras associadas ao login.
    """
    data = capital_api.request("GET", "/accounts")
    return jsonify(data), 200

@app.route("/accounts/preferences", methods=["GET"])
def get_account_preferences():
    """
    Obtém as preferências da conta (ex: modo hedge, alavancagem).
    """
    data = capital_api.request("GET", "/accounts/preferences")
    return jsonify(data), 200

@app.route("/accounts/preferences", methods=["PUT"])
def update_account_preferences():
    """
    Atualiza as preferências da conta, como modo de hedge ou alavancagem.
    Espera um JSON com as preferências a serem atualizadas.
    """
    if not request.is_json:
        raise APIError(400, "Corpo JSON com preferências é obrigatório.")
    prefs = request.get_json()
    data = capital_api.request("PUT", "/accounts/preferences", json=prefs)
    return jsonify(data), 200

@app.route("/accounts/topup", methods=["POST"])
def topup_account():
    """
    Adiciona fundos (top-up) à conta demo.
    Espera um JSON {"amount": valor}.
    Apenas funciona para contas demo e possui limites definidos pela API.
    """
    if not request.is_json:
        raise APIError(400, "Corpo JSON com 'amount' é obrigatório.")
    payload = request.get_json()
    amount = payload.get("amount")
    if amount is None:
        raise APIError(400, "Valor 'amount' é obrigatório para top-up.")
    data = capital_api.request("POST", "/accounts/topUp", json={"amount": amount})
    return jsonify(data), 200

# --- Endpoints de Dados de Mercado ---

@app.route("/markets", methods=["GET"])
def search_markets():
    """
    Busca mercados por nome ou símbolo.
    Use o parâmetro de query 'search' (ou 'searchTerm') para especificar o termo de busca.
    """
    search_term = request.args.get("search") or request.args.get("searchTerm")
    endpoint = "/markets"
    if search_term:
        endpoint += f"?searchTerm={search_term}"
    data = capital_api.request("GET", endpoint)
    return jsonify(data), 200

@app.route("/markets/<string:epic>", methods=["GET"])
def get_market(epic):
    """
    Obtém informações detalhadas de um mercado específico pelo seu código EPIC.
    """
    data = capital_api.request("GET", f"/markets/{epic}")
    return jsonify(data), 200

@app.route("/marketnavigation", methods=["GET"])
def market_navigation_root():
    """
    Obtém os nós de navegação de mercado de nível superior (ex: classes de ativos).
    """
    data = capital_api.request("GET", "/marketnavigation")
    return jsonify(data), 200

@app.route("/marketnavigation/<string:node_id>", methods=["GET"])
def market_navigation_node(node_id):
    """
    Obtém detalhes de navegação de mercado para um determinado node (lista mercados de uma categoria).
    """
    data = capital_api.request("GET", f"/marketnavigation/{node_id}")
    return jsonify(data), 200

# --- Endpoints de Watchlists ---

@app.route("/watchlists", methods=["GET"])
def get_watchlists():
    """
    Obtém todas as watchlists do usuário.
    """
    data = capital_api.request("GET", "/watchlists")
    return jsonify(data), 200

@app.route("/watchlists", methods=["POST"])
def create_watchlist():
    """
    Cria uma nova watchlist.
    Espera um JSON {"name": "nome_da_watchlist"} no corpo.
    """
    if not request.is_json:
        raise APIError(400, "Corpo JSON com 'name' é obrigatório para criar watchlist.")
    body = request.get_json()
    name = body.get("name")
    if not name:
        raise APIError(400, "Nome da watchlist é obrigatório.")
    data = capital_api.request("POST", "/watchlists", json={"name": name})
    return jsonify(data), 200

@app.route("/watchlists/<string:watchlist_id>", methods=["GET"])
def get_watchlist(watchlist_id):
    """
    Obtém os ativos de uma watchlist específica pelo ID.
    """
    data = capital_api.request("GET", f"/watchlists/{watchlist_id}")
    return jsonify(data), 200

@app.route("/watchlists/<string:watchlist_id>", methods=["DELETE"])
def delete_watchlist(watchlist_id):
    """
    Exclui uma watchlist pelo ID.
    """
    data = capital_api.request("DELETE", f"/watchlists/{watchlist_id}")
    return jsonify(data), 200

@app.route("/watchlists/<string:watchlist_id>", methods=["PUT"])
def add_to_watchlist(watchlist_id):
    """
    Adiciona um instrumento (EPIC) a uma watchlist existente.
    Espera um JSON {"epic": "código_do_mercado"}.
    """
    if not request.is_json:
        raise APIError(400, "Corpo JSON com 'epic' é obrigatório.")
    body = request.get_json()
    epic = body.get("epic")
    if not epic:
        raise APIError(400, "Código EPIC é obrigatório para adicionar na watchlist.")
    data = capital_api.request("PUT", f"/watchlists/{watchlist_id}", json={"epic": epic})
    return jsonify(data), 200

@app.route("/watchlists/<string:watchlist_id>/<string:epic>", methods=["DELETE"])
def remove_from_watchlist(watchlist_id, epic):
    """
    Remove um instrumento (EPIC) de uma watchlist pelo ID e código do ativo.
    """
    data = capital_api.request("DELETE", f"/watchlists/{watchlist_id}/{epic}")
    return jsonify(data), 200

@app.route("/prices/<string:epic>/<string:resolution>/<string:start_date>/<string:end_date>", methods=["GET"])
def get_prices(epic, resolution, start_date, end_date):
    """
    Obtém dados históricos de preços para um mercado.
    Parâmetros de path:
      epic: código EPIC do mercado (ex: símbolo do ativo)
      resolution: período de tempo (ex: 'MINUTE', 'HOUR', 'DAY')
      start_date, end_date: intervalo de datas (formato ISO YYYY-MM-DD ou timestamp em ms).
    """
    data = capital_api.request("GET", f"/prices/{epic}/{resolution}/{start_date}/{end_date}")
    return jsonify(data), 200

# --- Endpoints de Trading (Posições e Ordens) ---

@app.route("/positions", methods=["GET"])
def get_positions():
    """
    Obtém todas as posições abertas da conta.
    """
    data = capital_api.request("GET", "/positions")
    return jsonify(data), 200

@app.route("/positions/<string:position_id>", methods=["GET"])
def get_position(position_id):
    """
    Obtém detalhes de uma posição aberta específica pelo deal ID.
    """
    data = capital_api.request("GET", f"/positions/{position_id}")
    return jsonify(data), 200

@app.route("/positions", methods=["POST"])
def open_position():
    """
    Abre uma nova posição (ordem de mercado).
    Espera um JSON com os detalhes da operação, por exemplo:
    {
        "epic": "...", "direction": "BUY/SELL", "size": <float>,
        "limitLevel": <preço_opcional>, "stopLevel": <preço_opcional>, etc.
    }
    """
    if not request.is_json:
        raise APIError(400, "Corpo JSON com detalhes da operação é obrigatório.")
    order = request.get_json()
    # Campos obrigatórios para abrir posição
    required_fields = ["epic", "direction", "size"]
    for field in required_fields:
        if field not in order:
            raise APIError(400, f"'{field}' é obrigatório para abrir uma posição.")
    data = capital_api.request("POST", "/positions", json=order)
    return jsonify(data), 200

@app.route("/positions/<string:position_id>", methods=["PUT"])
def update_position(position_id):
    """
    Atualiza uma posição aberta (ex: definir/altera stop loss ou take profit).
    Espera um JSON com os campos a serem atualizados (ex: stopLevel, limitLevel).
    """
    if not request.is_json:
        raise APIError(400, "Corpo JSON com campos para atualizar é obrigatório.")
    updates = request.get_json()
    data = capital_api.request("PUT", f"/positions/{position_id}", json=updates)
    return jsonify(data), 200

@app.route("/positions/<string:position_id>", methods=["DELETE"])
def close_position(position_id):
    """
    Fecha uma posição aberta pelo deal ID.
    Opcionalmente, pode incluir um JSON {"size": <valor>} para fechar parcialmente.
    Se nenhum tamanho for especificado, a posição inteira será fechada.
    """
    kwargs = {}
    if request.is_json:
        body = request.get_json()
        if body:
            kwargs["json"] = body
    data = capital_api.request("DELETE", f"/positions/{position_id}", **kwargs)
    return jsonify(data), 200

@app.route("/confirms/<string:deal_reference>", methods=["GET"])
def get_confirm(deal_reference):
    """
    Obtém o resultado de confirmação de uma operação através do dealReference.
    Use este endpoint para verificar o status de uma ordem enviada.
    """
    data = capital_api.request("GET", f"/confirms/{deal_reference}")
    return jsonify(data), 200

@app.route("/orders", methods=["GET"])
def get_orders():
    """
    Obtém todas as ordens abertas (ordens pendentes) da conta.
    """
    data = capital_api.request("GET", "/workingorders")
    return jsonify(data), 200

@app.route("/orders/<string:order_id>", methods=["GET"])
def get_order(order_id):
    """
    Obtém detalhes de uma ordem pendente específica pelo deal ID.
    """
    data = capital_api.request("GET", f"/workingorders/{order_id}")
    return jsonify(data), 200

@app.route("/orders", methods=["POST"])
def create_order():
    """
    Cria uma nova ordem pendente (working order).
    Espera um JSON com detalhes da ordem, por exemplo:
    {
        "epic": "...", "direction": "BUY/SELL", "size": <float>, "level": <preço>,
        "type": "STOP" ou "LIMIT" (opcional), "stopLevel": <preço>, "limitLevel": <preço>, 
        "goodTill": "DATE"/"CANCELLED" (se aplicável), etc.
    }
    """
    if not request.is_json:
        raise APIError(400, "Corpo JSON com detalhes da ordem é obrigatório.")
    order = request.get_json()
    # Campos obrigatórios para criar ordem pendente
    required_fields = ["epic", "direction", "size", "level"]
    for field in required_fields:
        if field not in order:
            raise APIError(400, f"'{field}' é obrigatório para criar a ordem.")
    data = capital_api.request("POST", "/workingorders", json=order)
    return jsonify(data), 200

@app.route("/orders/<string:order_id>", methods=["PUT"])
def update_order(order_id):
    """
    Atualiza uma ordem pendente existente (ex: modificar preço ou stop).
    Espera um JSON com os campos a serem atualizados.
    """
    if not request.is_json:
        raise APIError(400, "Corpo JSON com campos para atualizar é obrigatório.")
    updates = request.get_json()
    data = capital_api.request("PUT", f"/workingorders/{order_id}", json=updates)
    return jsonify(data), 200

@app.route("/orders/<string:order_id>", methods=["DELETE"])
def cancel_order(order_id):
    """
    Cancela (exclui) uma ordem pendente pelo deal ID.
    """
    data = capital_api.request("DELETE", f"/workingorders/{order_id}")
    return jsonify(data), 200

# --- Endpoint de Sentimento de Cliente ---

@app.route("/sentiment/<string:market_id>", methods=["GET"])
def get_client_sentiment(market_id):
    """
    Obtém o sentimento dos clientes para um mercado.
    O parâmetro pode ser o market ID numérico ou o código EPIC do ativo.
    Se um EPIC for fornecido em vez do ID, o endpoint busca o ID correspondente primeiro.
    """
    if market_id.isdigit():
        endpoint = f"/clientsentiment/{market_id}"
    else:
        market_data = capital_api.request("GET", f"/markets/{market_id}")
        # A estrutura do retorno /markets pode variar; checamos possíveis chaves
        market_info = {}
        if isinstance(market_data, dict):
            if "market" in market_data:
                market_info = market_data["market"]
            elif "instrument" in market_data:
                market_info = market_data["instrument"]
            else:
                market_info = market_data
        market_id_value = market_info.get("marketId") or market_info.get("marketIdentifier") or market_info.get("instrumentId")
        if not market_id_value:
            raise APIError(404, "Market ID não encontrado para o EPIC fornecido.")
        endpoint = f"/clientsentiment/{market_id_value}"
    data = capital_api.request("GET", endpoint)
    return jsonify(data), 200

# --- Endpoints de Histórico de Transações e Atividades ---

@app.route("/history/transactions", methods=["GET"])
def get_transactions_history():
    """
    Obtém o histórico de transações da conta.
    Parâmetros de query opcionais:
      from=<timestamp> & to=<timestamp> para especificar período (em ms ou data ISO).
      type=<tipo> para filtrar por tipo de transação.
    Se nenhum parâmetro for fornecido, retorna as transações recentes.
    """
    endpoint = "/history/transactions"
    query_params = []
    if "from" in request.args:
        query_params.append(f"from={request.args.get('from')}")
    if "to" in request.args:
        query_params.append(f"to={request.args.get('to')}")
    if "type" in request.args:
        query_params.append(f"type={request.args.get('type')}")
    if query_params:
        endpoint += "?" + "&".join(query_params)
    data = capital_api.request("GET", endpoint)
    return jsonify(data), 200

@app.route("/history/activity", methods=["GET"])
def get_activity_history():
    """
    Obtém o histórico de atividades da conta (operações de trade, etc).
    Parâmetros de query opcionais semelhantes a /history/transactions.
    """
    endpoint = "/history/activity"
    query_params = []
    if "from" in request.args:
        query_params.append(f"from={request.args.get('from')}")
    if "to" in request.args:
        query_params.append(f"to={request.args.get('to')}")
    if "filter" in request.args:
        query_params.append(f"filter={request.args.get('filter')}")
    if query_params:
        endpoint += "?" + "&".join(query_params)
    data = capital_api.request("GET", endpoint)
    return jsonify(data), 200

if __name__ == "__main__":
    # Executa o app Flask (em produção, usar um servidor WSGI como Gunicorn no Render)
    app.run(host="0.0.0.0", port=5000)
