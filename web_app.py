import os
import sys
import json
import subprocess
import logging
from flask import Flask, request, jsonify, render_template
from rdflib import Graph

# --- 1. CONFIGURAÇÃO ---
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - WEB_APP - %(levelname)s - %(message)s')

# --- CAMINHOS CORRIGIDOS PARA A ESTRUTURA DO DOCKER ---
# Dentro do contêiner, nosso diretório de trabalho é /app
APP_BASE_DIR = '/app'
RESOURCES_DIR = os.path.join(APP_BASE_DIR, 'src', 'main', 'resources')

STATIC_FOLDER = os.path.join(RESOURCES_DIR, 'static')
TEMPLATE_FOLDER = STATIC_FOLDER

PLN_SCRIPT_PATH = os.path.join(RESOURCES_DIR, 'pln_processor.py')
TEMPLATES_DIR = os.path.join(RESOURCES_DIR, 'templates')
ONTOLOGY_PATH = os.path.join(APP_BASE_DIR, 'ontologiaB3_com_inferencia.ttl')

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
    """Serve a página principal."""
    return render_template('index2.html')

@app.route('/generate_query', methods=['POST'])
def generate_query_route():
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        if not question:
            return jsonify({"error": "A pergunta não pode estar vazia."}), 400

        logging.info(f"Iniciando PLN para pergunta: '{question}'")
        # Passa o caminho absoluto dos resources para o script PLN
        pln_output = run_pln_processor(question, RESOURCES_DIR)
        
        if "erro" in pln_output:
            return jsonify({"error": pln_output["erro"], "sparql_query": ""}), 400

        template_name = pln_output.get("template_nome")
        entities = pln_output.get("mapeamentos", {})
        
        query_build_result = build_sparql_query(template_name, entities)
        
        if "error" in query_build_result:
            return jsonify(query_build_result), 500
        
        logging.info(f"Consulta SPARQL gerada com sucesso para o template '{template_name}'.")
        return jsonify(query_build_result)

    except Exception as e:
        logging.error(f"Erro inesperado em /generate_query: {e}", exc_info=True)
        return jsonify({"error": "Erro interno do servidor ao gerar a consulta.", "sparql_query": ""}), 500
        
@app.route('/execute_query', methods=['POST'])
def execute_query_route():
    # Esta rota pode ser usada para executar consultas na ontologia carregada no Python, se necessário
    # Atualmente, a execução principal acontece no backend Java.
    pass

# --- 4. FUNÇÕES AUXILIARES ---
def run_pln_processor(question: str, resources_path: str) -> dict:
    """Executa o script Python do PLN de forma robusta."""
    python_executables = ['python3', 'python']
    for executable in python_executables:
        try:
            # Passa o caminho dos resources como um argumento para o script PLN
            command = [executable, PLN_SCRIPT_PATH, question, resources_path]
            logging.info(f"Executando comando PLN: {' '.join(command)}")
            process = subprocess.run(
                command, 
                capture_output=True, text=True, check=True, encoding='utf-8', timeout=20
            )
            return json.loads(process.stdout)
        except FileNotFoundError:
            continue
        except Exception as e:
            return {"erro": f"Falha ao executar processo PLN: {e}"}
    return {"erro": "Nenhum executável Python ('python3' ou 'python') foi encontrado."}

def build_sparql_query(template_name: str, entities: dict) -> dict:
    """Constrói a consulta SPARQL substituindo placeholders no template."""
    template_path = os.path.join(TEMPLATES_DIR, f"{template_name}.txt")
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            final_query = f.read()

        for placeholder, value in entities.items():
            if value is None: continue
            
            escaped_value = str(value).replace('"', '\\"')
            
            if placeholder == "#DATA#":
                final_query = final_query.replace(placeholder, f'"{escaped_value}"^^xsd:date')
            elif placeholder in ["#VALOR_DESEJADO#", "#SETOR_URI#"]:
                final_query = final_query.replace(placeholder, str(value))
            elif template_name == "Template_1A" and placeholder == "#ENTIDADE_NOME#":
                 final_query = final_query.replace(f"{placeholder}@pt", f'"{escaped_value}"@pt')
            else:
                final_query = final_query.replace(placeholder, f'"{escaped_value}"')
        
        return {"sparql_query": final_query}
    except FileNotFoundError:
        return {"error": f"Template '{template_path}' não encontrado no servidor."}
    except Exception as e:
        return {"error": f"Erro ao construir a consulta: {e}"}

# --- 5. PONTO DE ENTRADA ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)