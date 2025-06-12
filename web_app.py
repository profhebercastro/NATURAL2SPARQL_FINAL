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
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 2. CONFIGURAÇÃO DOS CAMINHOS ---
APP_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCES_DIR = os.path.join(APP_BASE_DIR, 'src', 'main', 'resources')
STATIC_DIR = os.path.join(RESOURCES_DIR, 'static')
PLN_SCRIPT_PATH = os.path.join(RESOURCES_DIR, 'pln_processor.py')
TEMPLATES_DIR = os.path.join(RESOURCES_DIR, 'Templates')
ONTOLOGY_PATH_LOCAL = os.path.join(APP_BASE_DIR, 'ontologiaB3_com_inferencia.ttl')

logging.info(f"--- VERIFICANDO CAMINHOS (no início) ---")
logging.info(f"  - SCRIPT PLN: {PLN_SCRIPT_PATH} (Existe? {os.path.isfile(PLN_SCRIPT_PATH)})")
logging.info(f"  - PASTA TEMPLATES: {TEMPLATES_DIR} (Existe? {os.path.isdir(TEMPLATES_DIR)})")

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
    logging.warning(f"ONTOLOGIA NÃO ENCONTRADA: {ONTOLOGY_PATH_LOCAL}")

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

        template_name = pln_result.get("template_id")
        entities = pln_result.get("entities", {})
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
        logging.error(f"Erro em /process: {e}", exc_info=True)
        return jsonify({"error": f"Erro interno: {e}"}), 500

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
    """
    Constrói a consulta SPARQL substituindo placeholders de forma inteligente.
    """
    if not template_name: return {"error": "Nome do template não fornecido pelo PLN."}
    
    # Garante que o nome do arquivo seja consistente (sem espaços)
    corrected_template_name = template_name.replace(" ", "_")
    template_path = os.path.join(TEMPLATES_DIR, f"{corrected_template_name}.txt")
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            query_template = f.read()

        final_query = query_template
        
        for key, value in entities.items():
            placeholder = f"<{key}>"
            formatted_value = ""

            # ✅ LÓGICA DE SUBSTITUIÇÃO INTELIGENTE
            # Chaves terminadas em '_prop' são tratadas como nomes de propriedades (sem aspas)
            if key.endswith('_prop'):
                formatted_value = str(value) # Ex: b3:precoFechamento
            
            # Chaves específicas como 'date' recebem formatação de tipo
            elif key == 'date':
                formatted_value = f'"{value}"^^xsd:date'
            
            # Todas as outras chaves são tratadas como strings literais (com aspas)
            else:
                escaped_value = str(value).replace('"', '\\"')
                formatted_value = f'"{escaped_value}"'
            
            # Realiza a substituição na query
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