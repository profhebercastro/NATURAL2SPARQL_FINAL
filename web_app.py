# Arquivo: web_app.py

import os
import sys
import json
import subprocess
import logging
from flask import Flask, request, jsonify, render_template
from rdflib import Graph
from rdflib.plugins.sparql.results.jsonresults import JSONResultSerializer

# --- 1. CONFIGURAÇÃO ---
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - WEB - %(levelname)s - %(message)s')

# Caminhos são definidos de forma robusta para funcionar dentro do contêiner Docker
APP_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCES_DIR = os.path.join(APP_BASE_DIR, 'src', 'main', 'resources')
STATIC_FOLDER = os.path.join(RESOURCES_DIR, 'static')
PLN_SCRIPT_PATH = os.path.join(RESOURCES_DIR, 'pln_processor.py')
TEMPLATES_DIR = os.path.join(RESOURCES_DIR, 'Templates')
ONTOLOGY_PATH = os.path.join(APP_BASE_DIR, 'ontologiaB3_com_inferencia.ttl')

app = Flask(__name__, static_url_path='', static_folder=STATIC_FOLDER)

# --- 2. CARREGAMENTO DA ONTOLOGIA (UMA VEZ NA INICIALIZAÇÃO) ---
graph = Graph()
try:
    logging.info(f"Tentando carregar ontologia de: {ONTOLOGY_PATH}")
    graph.parse(ONTOLOGY_PATH, format="turtle")
    logging.info(f"Ontologia carregada com sucesso. Total de triplas: {len(graph)}.")
except Exception as e:
    logging.error(f"FALHA CRÍTICA AO CARREGAR ONTOLOGIA de '{ONTOLOGY_PATH}'. Erro: {e}", exc_info=True)

# --- 3. ROTAS DA API ---
@app.route('/')
def index():
    """Serve a página HTML principal (ex: index.html) da pasta static."""
    return render_template('index.html')

@app.route('/query', methods=['POST'])
def handle_query():
    """Rota única que orquestra todo o fluxo: PLN -> Build Query -> Execute Query."""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        if not question:
            return jsonify({"error": "A pergunta não pode estar vazia."}), 400

        logging.info(f"Iniciando processamento para a pergunta: '{question}'")

        # Passo 1: Chamar o script PLN para análise
        pln_output = run_pln_processor(question)
        if "erro" in pln_output:
            logging.error(f"Erro retornado pelo PLN: {pln_output['erro']}")
            return jsonify({"error": f"Não foi possível interpretar a pergunta: {pln_output['erro']}", "sparql_query": ""}), 400

        # Passo 2: Construir a consulta SPARQL com base na saída do PLN
        template_name = pln_output.get("template_nome")
        entities = pln_output.get("mapeamentos", {})
        query_build_result = build_sparql_query(template_name, entities)
        if "error" in query_build_result:
            logging.error(f"Erro ao construir a query: {query_build_result['error']}")
            return jsonify(query_build_result), 500
        
        sparql_query = query_build_result["sparql_query"]
        logging.info(f"Consulta SPARQL gerada:\n---\n{sparql_query}\n---")

        # Passo 3: Executar a consulta na ontologia local
        execution_result = execute_local_sparql(sparql_query)
        if "error" in execution_result:
            logging.error(f"Erro ao executar a query: {execution_result['error']}")
            return jsonify(execution_result), 500

        # Passo 4: Retornar a resposta final formatada
        return jsonify({"answer": execution_result["data"], "sparql_query": sparql_query})

    except Exception as e:
        logging.error(f"Erro inesperado na rota /query: {e}", exc_info=True)
        return jsonify({"error": "Ocorreu um erro interno inesperado no servidor.", "sparql_query": ""}), 500

# --- 4. FUNÇÕES AUXILIARES ---
def run_pln_processor(question: str) -> dict:
    """Executa o script pln_processor.py em um subprocesso e retorna sua saída JSON."""
    try:
        process = subprocess.run(
            ['python3', PLN_SCRIPT_PATH, question], 
            capture_output=True, text=True, check=True, encoding='utf-8'
        )
        return json.loads(process.stdout)
    except subprocess.CalledProcessError as e:
        # Captura o erro quando o script PLN retorna um status de erro (ex: exit(1))
        # O script foi programado para imprimir um JSON de erro no stdout nesses casos
        try:
            return json.loads(e.stdout)
        except json.JSONDecodeError:
            return {"erro": f"O script PLN falhou com uma saída não-JSON. Stderr: {e.stderr}"}
    except Exception as e:
        return {"erro": f"Falha crítica ao executar o processo PLN: {e}"}

def build_sparql_query(template_name: str, entities: dict) -> dict:
    """Carrega um arquivo de template e preenche os placeholders com as entidades extraídas."""
    template_path = os.path.join(TEMPLATES_DIR, f"{template_name}.txt")
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            final_query = f.read()

        for placeholder, value in entities.items():
            # Substitui os placeholders um a um, com formatação específica para cada tipo
            if placeholder == "#ENTIDADE_NOME#":
                # Formata como um literal SPARQL (string entre aspas)
                formatted_value = f'"{str(value).replace("\"", "\\\"")}"'
                final_query = final_query.replace(placeholder, formatted_value)
            elif placeholder == "#DATA#":
                # Formata como um literal de data SPARQL
                formatted_value = f'"{value}"^^xsd:date'
                final_query = final_query.replace(placeholder, formatted_value)
            elif placeholder == "#VALOR_DESEJADO#":
                # Substitui diretamente, pois o valor é parte de um predicado (ex: precoFechamento)
                final_query = final_query.replace(placeholder, str(value))
            elif placeholder == "#SETOR#":
                formatted_value = f'"{str(value).replace("\"", "\\\"")}"'
                final_query = final_query.replace(placeholder, formatted_value)

        return {"sparql_query": final_query}
    except FileNotFoundError:
        return {"error": f"Arquivo de template não encontrado: '{template_path}'"}
    except Exception as e:
        return {"error": f"Erro inesperado ao construir a query: {e}"}

def execute_local_sparql(query_string: str) -> dict:
    """Executa uma consulta SPARQL no grafo rdflib carregado em memória."""
    if len(graph) == 0:
        return {"error": "A ontologia local não está carregada. Verifique os logs de inicialização do servidor."}
    try:
        results = graph.query(query_string)
        # Serializa o resultado para o formato JSON padrão do SPARQL
        serializer = JSONResultSerializer(results)
        output_stream = sys.stdout.buffer # Usa um buffer em memória para evitar escrita em arquivo
        # O serializer espera um stream binário, então codificamos para utf-8
        with os.fdopen(os.dup(output_stream.fileno()), 'wb') as f:
             serializer.serialize(f)
        # Como o método acima é complexo para capturar, vamos usar a conversão manual que é mais simples
        results_list = [row.asdict() for row in results]
        return {"data": results_list}
    except Exception as e:
        logging.error(f"Erro durante a execução da query SPARQL: {e}", exc_info=True)
        return {"error": f"A consulta SPARQL gerada é inválida. Detalhes: {e}"}

# --- 5. PONTO DE ENTRADA DA APLICAÇÃO ---
if __name__ == '__main__':
    # Esta seção é para execução local (python web_app.py). O Gunicorn/Render usará o objeto 'app'.
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)