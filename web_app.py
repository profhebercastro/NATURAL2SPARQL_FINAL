import os
import sys
import json
import logging
import re
import subprocess
from flask import Flask, request, jsonify, send_from_directory
from rdflib import Graph, Namespace
from rdflib.plugins.sparql import prepareQuery

# --- CONFIGURAÇÃO INICIAL ---
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Obtém o diretório raiz da aplicação (onde web_app.py está)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- DEFINIÇÃO DOS CAMINHOS CORRETOS (A PARTE MAIS IMPORTANTE) ---
# Define o caminho para a pasta 'resources'
RESOURCES_DIR = os.path.join(BASE_DIR, "src", "main", "resources")

# Define o caminho para a pasta 'static' DENTRO da pasta 'resources'
STATIC_DIR = os.path.join(RESOURCES_DIR, "static")

# Inicializa o Flask, informando a ele ONDE encontrar os arquivos estáticos (CSS, JS, index.html)
app = Flask(__name__, static_folder=STATIC_DIR)

# Caminhos para os outros recursos
PLN_PROCESSOR_SCRIPT_PATH = os.path.join(RESOURCES_DIR, "pln_processor.py")
# Assumindo que a pasta de templates está dentro de resources. Ajuste se o nome for diferente.
SPARQL_TEMPLATES_DIR = os.path.join(RESOURCES_DIR, "templates_sparql") 
ONTOLOGY_FILE_PATH = os.path.join(BASE_DIR, "ontologiaB3_com_inferencia.ttl") # Este já está na raiz

# --- CÓDIGO DE DEBUG para verificar se os caminhos estão corretos ---
logging.info("--- INICIANDO VERIFICAÇÃO DE ARQUIVOS (ESTRUTURA ATUAL) ---")
logging.info(f"VERIFICAÇÃO: O arquivo 'pln_processor.py' existe em '{PLN_PROCESSOR_SCRIPT_PATH}'? -> {os.path.exists(PLN_PROCESSOR_SCRIPT_PATH)}")
logging.info(f"VERIFICAÇÃO: A pasta de templates existe em '{SPARQL_TEMPLATES_DIR}'? -> {os.path.exists(SPARQL_TEMPLATES_DIR)}")
logging.info(f"VERIFICAÇÃO: A pasta estática existe em '{app.static_folder}'? -> {os.path.exists(app.static_folder)}")
if os.path.exists(app.static_folder):
    logging.info(f"Conteúdo da pasta estática: {os.listdir(app.static_folder)}")
logging.info("--- FIM DA VERIFICAÇÃO DE ARQUIVOS ---")


# --- CARREGAMENTO DA ONTOLOGIA ---
graph = Graph()
try:
    if not os.path.exists(ONTOLOGY_FILE_PATH):
        raise FileNotFoundError(f"Arquivo de ontologia não encontrado em {ONTOLOGY_FILE_PATH}")
    
    logging.info(f"Carregando ontologia de: {ONTOLOGY_FILE_PATH}")
    graph.parse(ONTOLOGY_FILE_PATH, format="turtle")
    logging.info(f"Ontologia carregada com {len(graph)} triplas.")
except Exception as e:
    logging.critical(f"Erro CRÍTICO ao carregar a ontologia: {e}", exc_info=True)


# --- DEFINIÇÃO DAS ROTAS ---

@app.route('/')
def serve_index():
    """Serve a página principal (index2.html) da pasta 'static' que foi configurada."""
    logging.info(f"Tentando servir 'index2.html' da pasta estática configurada: {app.static_folder}")
    return send_from_directory(app.static_folder, 'index2.html')

@app.route('/processar_pergunta', methods=['POST'])
def processar_pergunta_completa():
    logging.info("Endpoint '/processar_pergunta' foi chamado.")
    data = request.get_json()
    pergunta_usuario = data.get('pergunta')
    if not pergunta_usuario:
        return jsonify({"erro": "Pergunta não fornecida"}), 400

    logging.info(f"Recebida pergunta: '{pergunta_usuario}'")

    # 1. Chamar o script de PLN
    try:
        # IMPORTANTE: O diretório de trabalho (cwd) do subprocesso deve ser a pasta 'resources'
        # para que o pln_processor.py encontre quaisquer outros arquivos que ele precise.
        logging.info(f"Executando script PLN '{PLN_PROCESSOR_SCRIPT_PATH}' com CWD='{RESOURCES_DIR}'")
        process_pln = subprocess.run(
            ['python', PLN_PROCESSOR_SCRIPT_PATH, pergunta_usuario],
            capture_output=True, text=True, check=True, cwd=RESOURCES_DIR, env=dict(os.environ, PYTHONIOENCODING='utf-8')
        )
        pln_output_json = json.loads(process_pln.stdout.strip())
        logging.info(f"PLN retornou: {pln_output_json}")

    except FileNotFoundError:
        logging.error(f"Erro FATAL: O script PLN não foi encontrado em '{PLN_PROCESSOR_SCRIPT_PATH}'. Verifique se o caminho e a estrutura de pastas estão corretos no repositório.")
        return jsonify({"erro": "Erro de configuração interna: Script de processamento não encontrado."}), 500
    except subprocess.CalledProcessError as e:
        logging.error(f"Erro ao executar o script PLN (código {e.returncode}): {e.stderr.strip()}")
        return jsonify({"erro": f"Erro no processador de linguagem: {e.stderr.strip()}"}), 500
    except Exception as e:
        logging.error(f"Erro inesperado ao chamar o PLN: {e}", exc_info=True)
        return jsonify({"erro": "Erro interno no servidor ao processar a pergunta."}), 500

    # O resto do código continua igual, pois agora ele usa os caminhos corretos
    template_nome = pln_output_json.get("template_nome")
    mapeamentos = pln_output_json.get("mapeamentos", {})

    if not template_nome:
        return jsonify({"erro": "Processador de linguagem não retornou um template válido."}), 500

    try:
        template_path = os.path.join(SPARQL_TEMPLATES_DIR, f"{template_nome}.txt")
        with open(template_path, 'r', encoding='utf-8') as f:
            sparql_query_template = f.read()
        
        sparql_query_final = sparql_query_template
        for placeholder, value in mapeamentos.items():
            formatted_value = f'"{str(value)}"'
            if placeholder == "#DATA#":
                 formatted_value = f'"{str(value)}"^^xsd:date'
            elif placeholder == "#VALOR_DESEJADO#":
                 formatted_value = str(value)
            
            sparql_query_final = sparql_query_final.replace(placeholder, formatted_value)
        logging.info(f"Consulta SPARQL final gerada:\n{sparql_query_final}")
    except FileNotFoundError:
        logging.error(f"Arquivo de template não encontrado: {template_path}")
        return jsonify({"erro": f"Template SPARQL '{template_nome}' não encontrado no servidor."}), 500
    except Exception as e:
        logging.error(f"Erro ao montar a query SPARQL: {e}", exc_info=True)
        return jsonify({"erro": "Erro interno ao gerar a consulta."}), 500
    
    if len(graph) == 0:
        return jsonify({"erro": "A ontologia não está carregada. Não é possível executar a consulta."}), 500

    try:
        query_obj = prepareQuery(sparql_query_final)
        qres = graph.query(query_obj)
        resultados = [{str(var): str(val) for var, val in row.asdict().items()} for row in qres]
        resposta_final = json.dumps(resultados, ensure_ascii=False) if resultados else "Nenhum resultado encontrado."
        logging.info(f"Consulta executada com sucesso. {len(resultados)} resultados encontrados.")
    except Exception as e:
        logging.error(f"Erro ao executar a consulta SPARQL: {e}", exc_info=True)
        return jsonify({"erro": "Erro ao consultar a base de conhecimento.", "sparqlQuery": sparql_query_final}), 500

    return jsonify({"sparqlQuery": sparql_query_final, "resposta": resposta_final})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)