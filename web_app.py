import os
import sys
import json
import logging
import requests
from flask import Flask, request, jsonify, render_template
from requests.exceptions import RequestException

# --- 1. CONFIGURAÇÃO ---
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - WEB_APP - %(levelname)s - %(message)s')

# O diretório do script é a raiz do app no contêiner
APP_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# O frontend (HTML/CSS/JS) deve estar na pasta 'static'
STATIC_FOLDER = os.path.join(APP_BASE_DIR, 'src/main/resources/static')
TEMPLATE_FOLDER = STATIC_FOLDER

# O endereço do serviço Java rodando no mesmo contêiner
JAVA_API_URL = "http://localhost:8080/processar_pergunta" # O Spring Boot roda na porta 8080 por padrão

app = Flask(__name__, 
            static_folder=STATIC_FOLDER,
            template_folder=TEMPLATE_FOLDER)

# --- 2. ROTAS DA API ---
@app.route('/')
def index():
    """Serve a página HTML principal."""
    try:
        # O Spring Boot vai cuidar de servir o index, mas podemos ter um fallback
        return render_template('index2.html')
    except Exception as e:
        logging.error(f"Erro ao tentar renderizar index2.html: {e}")
        return "Erro ao carregar a página principal. Verifique os logs do servidor.", 500

@app.route('/processar_pergunta', methods=['POST'])
def process_question_route():
    """
    Recebe a pergunta do frontend e atua como um proxy para o serviço Java.
    """
    try:
        data = request.get_json()
        question = data.get('pergunta', '').strip()

        if not question:
            return jsonify({"erro": "A pergunta não pode estar vazia."}), 400

        logging.info(f"Recebida pergunta: '{question}'. Repassando para o serviço Java em {JAVA_API_URL}")

        # Corpo da requisição que será enviado para o serviço Java
        java_payload = {"pergunta": question}

        # Faz a requisição HTTP para o serviço Java
        response = requests.post(JAVA_API_URL, json=java_payload, timeout=120) # Timeout de 2 minutos

        # Verifica se a requisição para o Java foi bem-sucedida
        response.raise_for_status()

        # Retorna a resposta exata do serviço Java para o frontend
        java_response_data = response.json()
        logging.info(f"Resposta recebida do Java e sendo enviada ao cliente: {java_response_data}")
        return jsonify(java_response_data)

    except RequestException as e:
        logging.error(f"Erro de comunicação ao tentar contatar o serviço Java: {e}", exc_info=True)
        return jsonify({"erro": "O serviço de processamento principal (Java) não está respondendo. Pode estar inicializando."}), 503 # Service Unavailable
    
    except Exception as e:
        logging.error(f"Erro inesperado no proxy Python: {e}", exc_info=True)
        return jsonify({"erro": "Ocorreu um erro inesperado no servidor."}), 500

# --- 3. PONTO DE ENTRADA ---
if __name__ == '__main__':
    # A porta é definida pelo Render através da variável de ambiente PORT
    port = int(os.environ.get("PORT", 10000))
    # 'debug=False' é importante para produção
    app.run(host='0.0.0.0', port=port, debug=False)