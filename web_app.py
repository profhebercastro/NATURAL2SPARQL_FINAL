import os
import sys
import json
import subprocess
import logging
import re
from flask import Flask, request, jsonify, send_from_directory
from rdflib import Graph, Namespace
from rdflib.plugins.sparql import prepareQuery
import requests

# --- 1. CONFIGURAÇÃO INICIAL E LOGGING ---
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 2. CONFIGURAÇÃO DOS CAMINHOS CORRETOS ---

# O diretório base da aplicação é onde o web_app.py está.
APP_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# O diretório 'resources' contém os scripts e templates.
RESOURCES_DIR = os.path.join(APP_BASE_DIR, 'src', 'main', 'resources')

# Caminho para a pasta 'static' que contém o index2.html
STATIC_DIR = os.path.join(RESOURCES_DIR, 'static')

# Caminhos específicos para os arquivos e pastas
PLN_SCRIPT_PATH = os.path.join(RESOURCES_DIR, 'pln_processor.py')
TEMPLATES_DIR = os.path.join(RESOURCES_DIR, 'Templates') # Assumindo que a pasta se chama 'Templates' com 'T' maiúsculo
ONTOLOGY_PATH_LOCAL = os.path.join(APP_BASE_DIR, 'ontologiaB3_com_inferencia.ttl')

# --- Verificação de sanidade dos caminhos (muito útil para debug) ---
logging.info(f"VERIFICANDO CAMINHOS CONFIGURADOS:")
logging.info(f"  - Diretório Estático: {STATIC_DIR} (Existe? {os.path.isdir(STATIC_DIR)})")
logging.info(f"  - Script PLN: {PLN_SCRIPT_PATH} (Existe? {os.path.isfile(PLN_SCRIPT_PATH)})")
logging.info(f"  - Pasta de Templates: {TEMPLATES_DIR} (Existe? {os.path.isdir(TEMPLATES_DIR)})")
logging.info(f"  - Ontologia Local: {ONTOLOGY_PATH_LOCAL} (Existe? {os.path.isfile(ONTOLOGY_PATH_LOCAL)})")
# --------------------------------------------------------------------

app = Flask(__name__, static_folder=STATIC_DIR)

# --- 3. CARREGAMENTO DA ONTOLOGIA LOCAL ---
graph = Graph()
NS = {
    "b3": Namespace("https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#"),
    "rdf": Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
    "rdfs": Namespace("http://www.w3.org/2000/01/rdf-schema#"),
    "xsd": Namespace("http://www.w3.org/2001/XMLSchema#"),
    "owl": Namespace("http://www.w3.org/2002/07/owl#")
}
if os.path.exists(ONTOLOGY_PATH_LOCAL):
    logging.info(f"Carregando ontologia local de: {ONTOLOGY_PATH_LOCAL}")
    try:
        graph.parse(ONTOLOGY_PATH_LOCAL, format="turtle")
        logging.info(f"Ontologia local carregada com {len(graph)} triplas.")
    except Exception as e:
        logging.error(f"ERRO CRÍTICO ao carregar ontologia local: {e}", exc_info=True)
else:
    logging.warning(f"ARQUIVO DE ONTOLOGIA LOCAL NÃO ENCONTRADO em: {ONTOLOGY_PATH_LOCAL}. As consultas locais falharão.")

# --- 4. DEFINIÇÃO DAS ROTAS DA API ---
@app.route('/')
def index():
    """Serve a página principal da interface."""
    logging.info(f"Servindo 'index2.html' de '{app.static_folder}'")
    return send_from_directory(app.static_folder, 'index2.html')

@app.route('/process', methods=['POST'])
def process_question():
    """Rota principal que orquestra o PLN e a execução SPARQL."""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        endpoint_url = data.get('endpoint', '').strip()
        
        if not question:
            return jsonify({"error": "A 'pergunta' não foi fornecida."}), 400

        logging.info(f"Pergunta recebida: '{question}', Endpoint: '{endpoint_url or 'Local'}'")

        # Etapa 1: Chamar o PLN
        pln_result = run_pln_processor(question)
        if "error" in pln_result:
            return jsonify({ "sparql_query": "Erro no PLN", "result": pln_result["error"] }), 500

        # Etapa 2: Montar a query
        template_name = pln_result.get("template_id")
        entities = pln_result.get("entities", {})
        
        sparql_build_result = build_sparql_query(template_name, entities)
        if "error" in sparql_build_result:
            return jsonify({ "sparql_query": "Erro na montagem", "result": sparql_build_result["error"] }), 500
        
        final_query_string = sparql_build_result["sparql_query"]

        # Etapa 3: Executar a query
        if endpoint_url:
            query_result = execute_remote_sparql(final_query_string, endpoint_url)
        else:
            if len(graph) == 0:
                raise Exception("A ontologia local não está carregada ou está vazia.")
            query_result = execute_local_sparql(final_query_string)

        if "error" in query_result:
             return jsonify({ "sparql_query": final_query_string, "result": query_result["error"] }), 500

        # Etapa 4: Retornar o resultado
        return jsonify({
            "sparql_query": final_query_string,
            "result": query_result.get("data", "Nenhum resultado encontrado.")
        })

    except Exception as e:
        logging.error(f"Erro inesperado na rota /process: {e}", exc_info=True)
        return jsonify({"error": f"Erro interno no servidor: {e}"}), 500

# --- 5. FUNÇÕES AUXILIARES ---
def run_pln_processor(question: str) -> dict:
    """Executa o script pln_processor.py."""
    logging.info(f"Executando script PLN: {PLN_SCRIPT_PATH}")
    try:
        # cwd (current working directory) é crucial para que o pln_processor
        # encontre seus próprios arquivos (ex: perguntas_de_interesse.txt)
        process = subprocess.run(
            ['python', PLN_SCRIPT_PATH, question],
            capture_output=True, text=True, check=True, cwd=RESOURCES_DIR, encoding='utf-8'
        )
        return json.loads(process.stdout)
    except subprocess.CalledProcessError as e:
        error_message = f"Erro no script PLN (código {e.returncode}): {e.stderr}"
        logging.error(error_message)
        return {"error": error_message}
    except json.JSONDecodeError as e:
        error_message = f"Erro ao decodificar a saída JSON do script PLN. Saída recebida: {e.doc}"
        logging.error(error_message)
        return {"error": error_message}
    except FileNotFoundError:
        error_message = f"Erro de configuração: script PLN não encontrado em '{PLN_SCRIPT_PATH}'."
        logging.error(error_message)
        return {"error": error_message}

def build_sparql_query(template_name: str, entities: dict) -> dict:
    """Carrega um template e preenche com as entidades."""
    if not template_name:
        return {"error": "Nome do template não fornecido pelo PLN."}
    
    template_path = os.path.join(TEMPLATES_DIR, f"{template_name}.txt")
    logging.info(f"Montando query com template: {template_path}")
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            query_template = f.read()

        final_query = query_template
        for key, value in entities.items():
            placeholder = f"<{key}>"
            # Lógica de formatação de valor
            if key == 'date':
                formatted_value = f'"{value}"^^xsd:date'
            else: # Para 'company' e outros, tratar como string
                formatted_value = f'"{value}"'
            final_query = final_query.replace(placeholder, formatted_value)
        
        return {"sparql_query": final_query}
    except FileNotFoundError:
        logging.error(f"Arquivo de template não encontrado: {template_path}")
        return {"error": f"Template '{template_name}' não encontrado."}

def execute_local_sparql(query_string: str) -> dict:
    """Executa a consulta SPARQL no grafo rdflib local."""
    logging.info("Executando consulta na ontologia local.")
    try:
        q = prepareQuery(query_string, initNs=NS)
        results = graph.query(q)
        
        output = [row.asdict() for row in results]
        return {"data": json.dumps(output, indent=2, ensure_ascii=False)}
    except Exception as e:
        error_message = f"Erro na execução da consulta SPARQL local: {e}"
        logging.error(f"{error_message}\nQuery: {query_string}", exc_info=True)
        return {"error": error_message}

def execute_remote_sparql(query_string: str, endpoint_url: str) -> dict:
    """Executa a consulta SPARQL em um endpoint remoto."""
    logging.info(f"Executando consulta no endpoint remoto: {endpoint_url}")
    try:
        response = requests.post(
            endpoint_url,
            data={'query': query_string},
            headers={'Accept': 'application/sparql-results+json'},
            timeout=30 # Timeout de 30 segundos
        )
        response.raise_for_status()
        return {"data": response.json()}
    except requests.exceptions.RequestException as e:
        error_message = f"Falha ao conectar ou consultar o endpoint remoto: {e}"
        logging.error(error_message, exc_info=True)
        return {"error": error_message}

# --- 6. INICIALIZAÇÃO DA APLICAÇÃO ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    # Para deploy, o Gunicorn ou outro servidor WSGI é recomendado em vez de app.run()
    # O comando no Render.com (ex: gunicorn web_app:app) cuidará disso.
    app.run(host='0.0.0.0', port=port, debug=False)