# Arquivo: web_app.py
# Versão FINAL corrigida e robustecida para deploy no Render

import os
import sys
import json
import subprocess
import logging
from flask import Flask, request, jsonify, render_template
from rdflib import Graph

# --- 1. CONFIGURAÇÃO ---
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - WEB_APP - %(levelname)s - %(message)s')

# --- CORREÇÃO DE CAMINHOS ---
# O Dockerfile copia os recursos para a raiz do /app, então os caminhos são diretos
APP_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCES_DIR = APP_BASE_DIR 

STATIC_FOLDER = os.path.join(RESOURCES_DIR, 'static')
TEMPLATE_FOLDER = STATIC_FOLDER

PLN_SCRIPT_PATH = os.path.join(RESOURCES_DIR, 'pln_processor.py')
TEMPLATES_DIR = os.path.join(RESOURCES_DIR, 'templates') # Nome da pasta deve ser minúsculo
ONTOLOGY_PATH = os.path.join(RESOURCES_DIR, 'ontologiaB3_com_inferencia.ttl')

app = Flask(__name__, 
            static_folder=STATIC_FOLDER,
            template_folder=TEMPLATE_FOLDER)

# --- 2. CARREGAMENTO DA ONTOLOGIA ---
graph = Graph()
try:
    logging.info(f"Tentando carregar ontologia de: {ONTOLOGY_PATH}")
    if os.path.exists(ONTOLOGY_PATH):
        graph.parse(ONTOLOGY_PATH, format="turtle")
        logging.info(f"Ontologia local carregada com sucesso. Total de triplas: {len(graph)}.")
    else:
        logging.error(f"ARQUIVO DE ONTOLOGIA NÃO ENCONTRADO EM: {ONTOLOGY_PATH}. A execução de consultas falhará.")
except Exception as e:
    logging.error(f"FALHA CRÍTICA AO CARREGAR ONTOLOGIA LOCAL: {e}", exc_info=True)

# --- 3. ROTAS DA API ---
@app.route('/')
def index():
    return render_template('index2.html')

@app.route('/generate_query', methods=['POST'])
def generate_query_route():
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        if not question: return jsonify({"error": "A pergunta não pode estar vazia."}), 400

        logging.info(f"Iniciando PLN para pergunta: '{question}'")
        pln_output = run_pln_processor(question)
        
        if "erro" in pln_output: return jsonify({"error": pln_output["erro"], "sparql_query": ""}), 400

        template_name = pln_output.get("template_nome")
        entities = pln_output.get("mapeamentos", {})
        
        query_build_result = build_sparql_query(template_name, entities)
        
        if "error" in query_build_result: return jsonify(query_build_result), 500
        
        logging.info(f"Consulta SPARQL gerada com sucesso para o template '{template_name}'.")
        return jsonify(query_build_result)

    except Exception as e:
        logging.error(f"Erro inesperado em /generate_query: {e}", exc_info=True)
        return jsonify({"error": "Erro interno do servidor ao gerar a consulta.", "sparql_query": ""}), 500

@app.route('/execute_query', methods=['POST'])
def execute_query_route():
    try:
        data = request.get_json()
        sparql_query = data.get('sparql_query', '').strip()
        if not sparql_query: return jsonify({"error": "Nenhuma consulta SPARQL fornecida."}), 400

        logging.info("Executando consulta na ontologia local.")
        execution_result = execute_local_sparql(sparql_query)
        
        if "error" in execution_result: return jsonify({"result": execution_result["error"]}), 500
        
        return jsonify({"result": execution_result["data"]})
    except Exception as e:
        logging.error(f"Erro inesperado em /execute_query: {e}", exc_info=True)
        return jsonify({"error": f"Erro interno ao executar a consulta: {e}"}), 500

# --- 4. FUNÇÕES AUXILIARES ---
def run_pln_processor(question: str) -> dict:
    python_executables = ['python3', 'python']
    for executable in python_executables:
        try:
            process = subprocess.run(
                [executable, PLN_SCRIPT_PATH, question], 
                capture_output=True, text=True, check=True, encoding='utf-8', timeout=20
            )
            return json.loads(process.stdout)
        except FileNotFoundError: continue
        except Exception as e: return {"erro": f"Falha ao executar processo PLN: {e}"}
    return {"erro": "Nenhum executável Python ('python3' ou 'python') foi encontrado."}

# *** FUNÇÃO CORRIGIDA ***
def build_sparql_query(template_name: str, entities: dict) -> dict:
    template_path = os.path.join(TEMPLATES_DIR, f"{template_name}.txt")
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            final_query = f.read()

        for placeholder, value in entities.items():
            if value is None: continue

            # Prepara o valor escapando aspas internas
            escaped_value = str(value).replace('"', '\\"')
            
            # --- LÓGICA DE SUBSTITUIÇÃO CORRIGIDA ---
            if placeholder == "#ENTIDADE_NOME#" and (template_name == "Template_1A" or template_name == "Template_2A"):
                # O placeholder no template já tem @pt, então só precisamos substituir a chave
                final_query = final_query.replace(f"{placeholder}@pt", f'"{escaped_value}"@pt')
            elif placeholder == "#DATA#":
                final_query = final_query.replace(placeholder, f'"{escaped_value}"^^xsd:date')
            elif placeholder in ["#VALOR_DESEJADO#", "#SETOR_URI#"]:
                # Substituição direta, sem aspas
                final_query = final_query.replace(placeholder, str(value))
            else:
                # Caso padrão para outros literais string
                final_query = final_query.replace(placeholder, f'"{escaped_value}"')
        
        return {"sparql_query": final_query}
    except FileNotFoundError:
        return {"error": f"Template '{template_path}' não encontrado no servidor."}
    except Exception as e:
        return {"error": f"Erro ao construir a consulta: {e}"}

def execute_local_sparql(query_string: str) -> dict:
    if len(graph) == 0: return {"error": "A base de conhecimento local não está carregada ou está vazia."}
    try:
        results = graph.query(query_string)
        var_names = [str(v) for v in results.vars]
        output_lines = []
        for row in results:
            line_parts = [str(row[var]) if row[var] else "N/A" for var in var_names]
            output_lines.append(" - ".join(line_parts))
        formatted_data = "\n".join(output_lines)
        return {"data": formatted_data if formatted_data else "Nenhum resultado encontrado."}
    except Exception as e:
        logging.error(f"Erro na execução do SPARQL: {e}", exc_info=True)
        return {"error": f"A consulta SPARQL parece ser inválida. Detalhes: {e}"}

# --- 5. PONTO DE ENTRADA ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)