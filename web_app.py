# Arquivo: web_app.py
# Versão corrigida para a dinâmica de dois botões (Gerar -> Executar)

import os
import sys
import json
import subprocess
import logging
from flask import Flask, request, jsonify, render_template
from rdflib import Graph

# --- 1. CONFIGURAÇÃO ---
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - WEB - %(levelname)s - %(message)s')

APP_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCES_DIR = os.path.join(APP_BASE_DIR, 'src', 'main', 'resources')

STATIC_FOLDER = os.path.join(RESOURCES_DIR, 'static')
TEMPLATE_FOLDER = STATIC_FOLDER

PLN_SCRIPT_PATH = os.path.join(RESOURCES_DIR, 'pln_processor.py')
TEMPLATES_DIR = os.path.join(RESOURCES_DIR, 'Templates')
ONTOLOGY_PATH = os.path.join(APP_BASE_DIR, 'ontologiaB3_com_inferencia.ttl')

app = Flask(__name__, 
            static_folder=STATIC_FOLDER,
            template_folder=TEMPLATE_FOLDER)

# --- 2. CARREGAMENTO DA ONTOLOGIA ---
graph = Graph()
try:
    logging.info(f"Tentando carregar ontologia de: {ONTOLOGY_PATH}")
    graph.parse(ONTOLOGY_PATH, format="turtle")
    logging.info(f"Ontologia carregada com sucesso. Total de triplas: {len(graph)}.")
except Exception as e:
    logging.error(f"FALHA CRÍTICA AO CARREGAR ONTOLOGIA: {e}", exc_info=True)

# --- 3. ROTAS DA API (SEPARADAS) ---
@app.route('/')
def index():
    """Serve a página principal (index2.html)."""
    return render_template('index2.html')

@app.route('/process', methods=['POST'])
def process_question_route():
    """Etapa 1: Recebe a pergunta e retorna APENAS a consulta SPARQL gerada."""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        if not question:
            return jsonify({"error": "A pergunta não pode estar vazia."}), 400

        logging.info(f"Gerando consulta para: '{question}'")
        
        pln_output = run_pln_processor(question)
        if "erro" in pln_output:
            return jsonify({"error": pln_output["erro"], "sparql_query": ""}), 400

        template_name = pln_output.get("template_nome")
        entities = pln_output.get("mapeamentos", {})
        
        query_build_result = build_sparql_query(template_name, entities)
        if "error" in query_build_result:
            return jsonify(query_build_result), 500
        
        # Retorna apenas a query gerada, como o frontend espera
        return jsonify(query_build_result)

    except Exception as e:
        logging.error(f"Erro inesperado em /process: {e}", exc_info=True)
        return jsonify({"error": "Erro interno ao gerar a consulta.", "sparql_query": ""}), 500

@app.route('/execute_query', methods=['POST'])
def execute_query_route():
    """Etapa 2: Recebe uma consulta SPARQL pronta e a executa."""
    try:
        data = request.get_json()
        sparql_query = data.get('sparql_query', '').strip()
        if not sparql_query:
            return jsonify({"error": "Nenhuma consulta SPARQL fornecida."}), 400

        logging.info("Executando consulta na ontologia local.")
        
        execution_result = execute_local_sparql(sparql_query)
        if "error" in execution_result:
            return jsonify({"result": execution_result["error"]}), 500
        
        # O frontend espera o campo 'result' contendo os dados
        return jsonify({"result": execution_result["data"]})

    except Exception as e:
        logging.error(f"Erro inesperado em /execute_query: {e}", exc_info=True)
        return jsonify({"error": f"Erro interno ao executar a consulta: {e}"}), 500

# --- 4. FUNÇÕES AUXILIARES ---
def run_pln_processor(question: str) -> dict:
    try:
        process = subprocess.run(
            ['python3', PLN_SCRIPT_PATH, question], 
            capture_output=True, text=True, check=True, encoding='utf-8', timeout=20
        )
        return json.loads(process.stdout)
    except subprocess.TimeoutExpired:
        return {"erro": "O processamento da linguagem demorou demais (timeout)."}
    except subprocess.CalledProcessError as e:
        try:
            return json.loads(e.stdout)
        except json.JSONDecodeError:
            return {"erro": f"O script PLN falhou com saída não-JSON. Stderr: {e.stderr}"}
    except Exception as e:
        return {"erro": f"Falha ao executar o processo PLN: {e}"}

def build_sparql_query(template_name: str, entities: dict) -> dict:
    template_path = os.path.join(TEMPLATES_DIR, f"{template_name}.txt")
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            final_query = f.read()

        for placeholder, value in entities.items():
            if placeholder in ["#ENTIDADE_NOME#", "#SETOR#"]:
                escaped_value = str(value).replace('"', '\\"')
                formatted_value = f'"{escaped_value}"'
                final_query = final_query.replace(placeholder, formatted_value)
            elif placeholder == "#DATA#":
                formatted_value = f'"{value}"^^xsd:date'
                final_query = final_query.replace(placeholder, formatted_value)
            elif placeholder == "#VALOR_DESEJADO#":
                final_query = final_query.replace(placeholder, str(value))
        
        return {"sparql_query": final_query}
    except FileNotFoundError:
        return {"error": f"Template '{template_path}' não encontrado."}

def execute_local_sparql(query_string: str) -> dict:
    if len(graph) == 0:
        return {"error": "A ontologia local não está carregada."}
    try:
        results = graph.query(query_string)
        results_list = [row.asdict() for row in results]
        return {"data": results_list}
    except Exception as e:
        return {"error": f"A consulta SPARQL parece ser inválida. Detalhes: {e}"}

# --- 5. PONTO DE ENTRADA ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)