import os
import sys
import json
import subprocess
import logging
import re
from flask import Flask, request, jsonify, send_from_directory
from rdflib import Graph, Namespace
from rdflib.plugins.sparql import prepareQuery
import requests # Para consultar endpoints remotos

# --- 1. CONFIGURAÇÃO INICIAL E LOGGING ---

# Configuração do logging para ver o que está acontecendo
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Cria a aplicação Flask
# O 'static_folder' deve apontar para o diretório onde o seu 'index2.html' está.
# Ajuste este caminho se necessário.
static_dir = os.path.join(os.path.dirname(__file__), 'src', 'main', 'resources', 'static')
app = Flask(__name__, static_folder=static_dir)

# --- 2. CONFIGURAÇÃO DOS CAMINHOS ---

# Caminho para o diretório de recursos, usado como diretório de trabalho para o script PLN
RESOURCES_DIR = os.path.join(os.path.dirname(__file__), 'src', 'main', 'resources')
PLN_SCRIPT_PATH = os.path.join(RESOURCES_DIR, 'pln_processor.py')
TEMPLATES_DIR = os.path.join(RESOURCES_DIR, 'Templates')
ONTOLOGY_PATH_LOCAL = os.path.join(os.path.dirname(__file__), 'ontologiaB3_com_inferencia.ttl')

# --- 3. CARREGAMENTO DA ONTOLOGIA LOCAL ---

graph = Graph()
# Define os namespaces para facilitar a escrita das queries
NS = {
    "b3": Namespace("https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#"),
    "rdf": Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
    "rdfs": Namespace("http://www.w3.org/2000/01/rdf-schema#"),
    "xsd": Namespace("http://www.w3.org/2001/XMLSchema#"),
    "owl": Namespace("http://www.w3.org/2002/07/owl#")
}

# Tenta carregar a ontologia local na inicialização
if os.path.exists(ONTOLOGY_PATH_LOCAL):
    logging.info(f"Carregando ontologia local de: {ONTOLOGY_PATH_LOCAL}")
    try:
        graph.parse(ONTOLOGY_PATH_LOCAL, format="turtle")
        logging.info(f"Ontologia local carregada com {len(graph)} triplas.")
        if len(graph) == 0:
            logging.warning("AVISO: Ontologia local está vazia (0 triplas).")
    except Exception as e:
        logging.error(f"ERRO CRÍTICO ao carregar ontologia local: {e}", exc_info=True)
else:
    logging.error(f"ARQUIVO DE ONTOLOGIA LOCAL NÃO ENCONTRADO em: {ONTOLOGY_PATH_LOCAL}. As consultas locais falharão.")


# --- 4. DEFINIÇÃO DAS ROTAS DA API ---

@app.route('/')
def index():
    """Serve a página principal da interface."""
    logging.info(f"Servindo 'index2.html' de '{app.static_folder}'")
    return send_from_directory(app.static_folder, 'index2.html')

@app.route('/process', methods=['POST'])
def process_question():
    """
    Rota principal que recebe a pergunta, orquestra o PLN e a execução SPARQL.
    """
    try:
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({"error": "A 'pergunta' não foi fornecida."}), 400

        question = data['question']
        endpoint_url = data.get('endpoint', '').strip() # Pega a URL do endpoint remoto
        logging.info(f"Pergunta recebida: '{question}', Endpoint: '{endpoint_url or 'Local'}'")

        # --- Etapa 1: Chamar o Processador de Linguagem Natural (PLN) ---
        pln_result = run_pln_processor(question)
        if "error" in pln_result:
            return jsonify(pln_result), 500

        # --- Etapa 2: Montar a consulta SPARQL a partir do template ---
        template_name = pln_result.get("template_id")
        entities = pln_result.get("entities", {})
        
        sparql_query = build_sparql_query(template_name, entities)
        if "error" in sparql_query:
            return jsonify(sparql_query), 500
        
        final_query_string = sparql_query["sparql_query"]

        # --- Etapa 3: Executar a consulta SPARQL (Local ou Remota) ---
        if endpoint_url:
            # Execução Remota
            query_result = execute_remote_sparql(final_query_string, endpoint_url)
        else:
            # Execução Local
            if len(graph) == 0:
                raise Exception("A ontologia local não está carregada ou está vazia.")
            query_result = execute_local_sparql(final_query_string)

        if "error" in query_result:
             return jsonify({ "sparql_query": final_query_string, "result": query_result["error"] }), 500

        # --- Etapa 4: Retornar o resultado formatado ---
        return jsonify({
            "sparql_query": final_query_string,
            "result": query_result.get("data", "Nenhum resultado encontrado.")
        })

    except Exception as e:
        logging.error(f"Erro inesperado na rota /process: {e}", exc_info=True)
        return jsonify({"error": f"Erro interno no servidor: {e}"}), 500


# --- 5. FUNÇÕES AUXILIARES ---

def run_pln_processor(question: str) -> dict:
    """Executa o script pln_processor.py e retorna o resultado como um dicionário."""
    logging.info(f"Executando script PLN para a pergunta: '{question}'")
    try:
        process = subprocess.run(
            ['python', PLN_SCRIPT_PATH, question],
            capture_output=True, text=True, check=True, cwd=RESOURCES_DIR, encoding='utf-8'
        )
        return json.loads(process.stdout)
    except subprocess.CalledProcessError as e:
        logging.error(f"Erro no script PLN: {e.stderr}")
        return {"error": f"Erro no processamento da linguagem natural: {e.stderr}"}
    except json.JSONDecodeError:
        logging.error("Erro ao decodificar a saída JSON do script PLN.")
        return {"error": "Formato de resposta inválido do processador de linguagem."}
    except FileNotFoundError:
        logging.error(f"Script PLN não encontrado em: {PLN_SCRIPT_PATH}")
        return {"error": "Erro de configuração do servidor: script PLN não encontrado."}


def build_sparql_query(template_name: str, entities: dict) -> dict:
    """Carrega um template e preenche com as entidades extraídas."""
    if not template_name:
        return {"error": "Nome do template não fornecido pelo PLN."}
    
    template_path = os.path.join(TEMPLATES_DIR, f"{template_name}.txt")
    logging.info(f"Montando query com template: {template_path}")
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            query_template = f.read()

        # Substitui os placeholders (ex: <company>, <date>) pelos valores
        final_query = query_template
        for key, value in entities.items():
            placeholder = f"<{key}>"
            # Formata o valor para ser seguro em SPARQL (adiciona aspas para strings)
            # Lógica mais avançada pode ser necessária aqui para datas, números, etc.
            formatted_value = f'"{value}"' # Simples, mas funcional para strings
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
        
        # Formata os resultados para JSON
        output = []
        for row in results:
            output.append({var: str(val) for var, val in row.asdict().items()})
            
        return {"data": json.dumps(output, indent=2, ensure_ascii=False)}
    except Exception as e:
        logging.error(f"Erro ao executar consulta SPARQL local: {e}\nQuery: {query_string}", exc_info=True)
        return {"error": f"Erro na sintaxe ou execução da consulta SPARQL: {e}"}

def execute_remote_sparql(query_string: str, endpoint_url: str) -> dict:
    """Executa a consulta SPARQL em um endpoint remoto."""
    logging.info(f"Executando consulta no endpoint remoto: {endpoint_url}")
    try:
        response = requests.post(
            endpoint_url,
            data={'query': query_string},
            headers={'Accept': 'application/sparql-results+json'}
        )
        response.raise_for_status() # Lança um erro para status 4xx/5xx
        return {"data": response.json()}
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao conectar ao endpoint SPARQL remoto: {e}", exc_info=True)
        return {"error": f"Falha ao conectar ao endpoint remoto: {e}"}

# --- 6. INICIALIZAÇÃO DA APLICAÇÃO ---

if __name__ == '__main__':
    # A porta é pega da variável de ambiente PORT, comum em serviços de nuvem como Render, Heroku, etc.
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)