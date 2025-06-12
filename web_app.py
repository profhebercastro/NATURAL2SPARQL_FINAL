# Arquivo: web_app.py

import os
import sys
import json
import subprocess
import logging
from flask import Flask, request, jsonify, send_from_directory
from rdflib import Graph, Namespace
from rdflib.plugins.sparql import prepareQuery
import requests

# --- 1. CONFIGURAÇÃO ---
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - WEB - %(levelname)s - %(message)s')

APP_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCES_DIR = os.path.join(APP_BASE_DIR, 'src', 'main', 'resources')
STATIC_DIR = os.path.join(RESOURCES_DIR, 'static')
PLN_SCRIPT_PATH = os.path.join(RESOURCES_DIR, 'pln_processor.py')
TEMPLATES_DIR = os.path.join(RESOURCES_DIR, 'Templates')
ONTOLOGY_PATH_LOCAL = os.path.join(APP_BASE_DIR, 'ontologiaB3_com_inferencia.ttl')

app = Flask(__name__, static_folder=STATIC_DIR)

# --- 2. CARREGAMENTO DA ONTOLOGIA ---
graph = Graph()
NS = { "b3": Namespace("..."), "rdf": Namespace("..."), "rdfs": Namespace("...") } # Seus namespaces
if os.path.exists(ONTOLOGY_PATH_LOCAL):
    graph.parse(ONTOLOGY_PATH_LOCAL, format="turtle")
    logging.info(f"Ontologia carregada com {len(graph)} triplas.")
else:
    logging.warning(f"ONTOLOGIA NÃO ENCONTRADA: {ONTOLOGY_PATH_LOCAL}")

# --- 3. ROTAS ---
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index2.html')

@app.route('/process', methods=['POST'])
def process_question_route():
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        if not question: return jsonify({"error": "Pergunta não fornecida."}), 400
        
        logging.info(f"Gerando consulta para: '{question}'")

        pln_result = run_pln_processor(question)
        if "error" in pln_result: return jsonify({"sparql_query": "Erro no PLN", "error": pln_result["error"]}), 500

        template_name = pln_result.get("template_nome")
        entities = pln_result.get("mapeamentos", {})
        query_build = build_sparql_query(template_name, entities)
        if "error" in query_build: return jsonify({"sparql_query": "Erro na montagem", "error": query_build["error"]}), 500
        
        return jsonify({"sparql_query": query_build["sparql_query"]})
    except Exception as e:
        logging.error(f"Erro em /process: {e}", exc_info=True)
        return jsonify({"error": f"Erro interno ao gerar consulta: {e}"}), 500

@app.route('/execute_query', methods=['POST'])
def execute_query_route():
    try:
        data = request.get_json()
        query_string = data.get('sparql_query', '').strip()
        endpoint = data.get('endpoint', '').strip()
        if not query_string: return jsonify({"error": "Nenhuma consulta SPARQL fornecida."}), 400

        logging.info(f"Executando consulta (Endpoint: {endpoint or 'Local'})")
        logging.debug(f"Query para executar:\n{query_string}")

        if endpoint: result = execute_remote_sparql(query_string, endpoint)
        else: result = execute_local_sparql(query_string)

        if "error" in result: return jsonify({"result": result["error"]}), 500
        return jsonify({"result": result.get("data", "Nenhum resultado.")})
    except Exception as e:
        logging.error(f"Erro em /execute_query: {e}", exc_info=True)
        return jsonify({"error": f"Erro interno ao executar consulta: {e}"}), 500

# --- 4. FUNÇÕES AUXILIARES ---
def run_pln_processor(question: str) -> dict:
    try:
        process = subprocess.run(['python', PLN_SCRIPT_PATH, question], capture_output=True, text=True, check=True, cwd=RESOURCES_DIR, encoding='utf-8')
        return json.loads(process.stdout)
    except subprocess.CalledProcessError as e: return {"error": f"Erro no script PLN: {e.stderr}"}
    except Exception as e: return {"error": f"Erro ao chamar PLN: {e}"}

def build_sparql_query(template_name: str, entities: dict) -> dict:
    if not template_name: return {"error": "Nome do template não fornecido pelo PLN."}
    corrected_template_name = template_name.replace(" ", "_")
    template_path = os.path.join(TEMPLATES_DIR, f"{corrected_template_name}.txt")
    try:
        with open(template_path, 'r', encoding='utf-8') as f: final_query = f.read()
        for key, value in entities.items():
            placeholder = key 
            if placeholder == "#ENTIDADE_NOME#" and '#ENTIDADE_NOME#@pt' in final_query:
                escaped_value = str(value).replace('"', '\\"')
                formatted_value = f'"{escaped_value}"@pt'
                final_query = final_query.replace('#ENTIDADE_NOME#@pt', formatted_value)
                continue
            if placeholder == "#ENTIDADE_NOME#": formatted_value = f'"{str(value).replace("\"", "\\\"")}"'
            elif placeholder == "#DATA#": formatted_value = f'"{value}"^^xsd:date'
            elif placeholder == "#VALOR_DESEJADO#": formatted_value = str(value)
            elif placeholder == "#SETOR#": formatted_value = f'"{str(value).replace("\"", "\\\"")}"'
            else: continue
            final_query = final_query.replace(placeholder, formatted_value)
        return {"sparql_query": final_query}
    except FileNotFoundError: return {"error": f"Template '{corrected_template_name}.txt' não encontrado."}

def execute_local_sparql(query_string: str) -> dict:
    if len(graph) == 0: return {"error": "Ontologia local não carregada."}
    try:
        q = prepareQuery(query_string, initNs=NS)
        results = [row.asdict() for row in graph.query(q)]
        return {"data": json.dumps(results, indent=2, ensure_ascii=False)}
    except Exception as e: return {"error": f"Erro na query local: {e}"}

def execute_remote_sparql(query_string: str, endpoint_url: str) -> dict:
    try:
        response = requests.post(endpoint_url, data={'query': query_string}, headers={'Accept': 'application/sparql-results+json'}, timeout=30)
        response.raise_for_status()
        return {"data": response.json()}
    except requests.exceptions.RequestException as e: return {"error": f"Falha na consulta remota: {e}"}

# --- PONTO DE ENTRADA ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)