# Arquivo: web_app.py

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
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - WEB - %(levelname)s - %(message)s')

# --- 2. CONFIGURAÇÃO DOS CAMINHOS (MANTENDO A ESTRUTURA ORIGINAL) ---
APP_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCES_DIR = os.path.join(APP_BASE_DIR, 'src', 'main', 'resources')
STATIC_DIR = os.path.join(RESOURCES_DIR, 'static')
PLN_SCRIPT_PATH = os.path.join(RESOURCES_DIR, 'pln_processor.py')
TEMPLATES_DIR = os.path.join(RESOURCES_DIR, 'Templates')
ONTOLOGY_PATH_LOCAL = os.path.join(APP_BASE_DIR, 'ontologiaB3_com_inferencia.ttl')

app = Flask(__name__, static_folder=STATIC_DIR)

# --- 3. CARREGAMENTO DA ONTOLOGIA ---
graph = Graph()
NS = {
    "b3": Namespace("https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#"),
    "rdf": Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
    "rdfs": Namespace("http://www.w3.org/2000/01/rdf-schema#"),
    "xsd": Namespace("http://www.w3.org/2001/XMLSchema#"),
    "owl": Namespace("http://www.w3.org/2002/07/owl#")
}
if os.path.exists(ONTOLOGY_PATH_LOCAL):
    logging.info(f"Carregando ontologia de: {ONTOLOGY_PATH_LOCAL}")
    graph.parse(ONTOLOGY_PATH_LOCAL, format="turtle")
    logging.info(f"Ontologia carregada com {len(graph)} triplas.")
else:
    logging.warning(f"ARQUIVO DE ONTOLOGIA NÃO ENCONTRADO: {ONTOLOGY_PATH_LOCAL}")

# --- 4. ROTAS ---
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index2.html')

@app.route('/process', methods=['POST'])
def process_question():
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        endpoint = data.get('endpoint', '').strip()

        if not question: return jsonify({"error": "Pergunta não fornecida."}), 400
        logging.info(f"Processando: '{question}' (Endpoint: {endpoint or 'Local'})")

        pln_result = run_pln_processor(question)
        if "error" in pln_result:
            return jsonify({ "sparql_query": "Erro no PLN", "result": pln_result["error"] }), 500

        template_name = pln_result.get("template_nome")
        entities = pln_result.get("mapeamentos", {})
        query_build = build_sparql_query(template_name, entities)
        if "error" in query_build:
            return jsonify({"sparql_query": "Erro na montagem", "result": query_build["error"]}), 500
        
        final_query = query_build["sparql_query"]
        logging.info(f"Consulta SPARQL Gerada:\n{final_query}")

        if endpoint: result = execute_remote_sparql(final_query, endpoint)
        else: result = execute_local_sparql(final_query)

        if "error" in result: return jsonify({"sparql_query": final_query, "result": result["error"]}), 500
        return jsonify({"sparql_query": final_query, "result": result.get("data", "Nenhum resultado.")})
    except Exception as e:
        logging.error(f"Erro inesperado em /process: {e}", exc_info=True)
        return jsonify({"error": f"Erro interno no servidor: {e}"}), 500

# --- 5. FUNÇÕES AUXILIARES ---
def run_pln_processor(question: str) -> dict:
    logging.info(f"Executando script PLN: '{PLN_SCRIPT_PATH}' com CWD: '{RESOURCES_DIR}'")
    try:
        process = subprocess.run(
            ['python', PLN_SCRIPT_PATH, question],
            capture_output=True, text=True, check=True, cwd=RESOURCES_DIR, encoding='utf-8'
        )
        return json.loads(process.stdout)
    except subprocess.CalledProcessError as e:
        return {"error": f"Erro no script PLN (código {e.returncode}): {e.stderr}"}
    except Exception as e:
        return {"error": f"Erro ao chamar PLN: {e}"}

def build_sparql_query(template_name: str, entities: dict) -> dict:
    if not template_name: return {"error": "Nome do template não fornecido pelo PLN."}
    
    corrected_template_name = template_name.replace(" ", "_")
    template_path = os.path.join(TEMPLATES_DIR, f"{corrected_template_name}.txt")
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            final_query = f.read()

        for key, value in entities.items():
            placeholder = key 
            
            if placeholder == "#ENTIDADE_NOME#" and '#ENTIDADE_NOME#@pt' in final_query:
                escaped_value = str(value).replace('"', '\\"')
                formatted_value = f'"{escaped_value}"@pt'
                final_query = final_query.replace('#ENTIDADE_NOME#@pt', formatted_value)
                continue
            
            if placeholder == "#ENTIDADE_NOME#":
                escaped_value = str(value).replace('"', '\\"')
                formatted_value = f'"{escaped_value}"'
            elif placeholder == "#DATA#":
                formatted_value = f'"{value}"^^xsd:date'
            elif placeholder == "#VALOR_DESEJADO#":
                formatted_value = str(value) 
            elif placeholder == "#SETOR#":
                escaped_value = str(value).replace('"', '\\"')
                formatted_value = f'"{escaped_value}"'
            else:
                continue # Pula placeholders não reconhecidos

            final_query = final_query.replace(placeholder, formatted_value)
                
        return {"sparql_query": final_query}
    except FileNotFoundError:
        return {"error": f"Template '{corrected_template_name}.txt' não encontrado em {TEMPLATES_DIR}."}

def execute_local_sparql(query_string: str) -> dict:
    if len(graph) == 0: return {"error": "Ontologia local não carregada."}
    try:
        q = prepareQuery(query_string, initNs=NS)
        results = [row.asdict() for row in graph.query(q)]
        return {"data": json.dumps(results, indent=2, ensure_ascii=False)}
    except Exception as e:
        return {"error": f"Erro na execução da query local: {e}"}

def execute_remote_sparql(query_string: str, endpoint_url: str) -> dict:
    try:
        response = requests.post(endpoint_url, data={'query': query_string}, headers={'Accept': 'application/sparql-results+json'}, timeout=30)
        response.raise_for_status()
        return {"data": response.json()}
    except requests.exceptions.RequestException as e:
        return {"error": f"Falha na consulta ao endpoint remoto: {e}"}

# --- 6. INICIALIZAÇÃO DA APLICAÇÃO ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)