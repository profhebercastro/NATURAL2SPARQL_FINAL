# Arquivo: web_app.py
# Versão FINAL corrigida e robustecida para deploy no Render

import os
import sys
import json
import subprocess
import logging
from flask import Flask, request, jsonify, render_template
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import XSD

# --- 1. CONFIGURAÇÃO ---
# Configura o logging para ir para o stdout, que é visível nos logs do Render
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - WEB_APP - %(levelname)s - %(message)s')

# --- CORREÇÃO DE CAMINHOS ---
# O script roda a partir da raiz do projeto no Render, não de dentro de /src
# Os caminhos devem ser relativos à raiz.
APP_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# No Docker, os recursos estarão na pasta 'target/classes' após o build do Maven.
# Se rodar localmente com `python web_app.py`, os caminhos precisam ser ajustados.
# A melhor abordagem é usar caminhos relativos ao diretório do script.
RESOURCES_DIR = APP_BASE_DIR # Assume que os recursos foram copiados para a raiz durante o build do Docker

STATIC_FOLDER = os.path.join(RESOURCES_DIR, 'static')
TEMPLATE_FOLDER = STATIC_FOLDER

PLN_SCRIPT_PATH = os.path.join(RESOURCES_DIR, 'pln_processor.py')
TEMPLATES_DIR = os.path.join(RESOURCES_DIR, 'templates') # Nome da pasta em minúsculas
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
    """Serve a página principal."""
    return render_template('index2.html')

@app.route('/generate_query', methods=['POST'])
def generate_query_route():
    """Recebe uma pergunta, chama o PLN e retorna a consulta SPARQL gerada."""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        if not question:
            return jsonify({"error": "A pergunta não pode estar vazia."}), 400

        logging.info(f"Iniciando PLN para pergunta: '{question}'")
        pln_output = run_pln_processor(question)
        
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
    """Recebe uma consulta SPARQL e a executa na ontologia local."""
    try:
        data = request.get_json()
        sparql_query = data.get('sparql_query', '').strip()
        if not sparql_query:
            return jsonify({"error": "Nenhuma consulta SPARQL fornecida."}), 400

        logging.info("Executando consulta na ontologia local.")
        execution_result = execute_local_sparql(sparql_query)
        
        if "error" in execution_result:
            return jsonify({"result": execution_result["error"]}), 500
        
        # O frontend espera um objeto com uma chave 'data' que contém a string formatada
        return jsonify({"result": execution_result["data"]})
    except Exception as e:
        logging.error(f"Erro inesperado em /execute_query: {e}", exc_info=True)
        return jsonify({"error": f"Erro interno ao executar a consulta: {e}"}), 500

# --- 4. FUNÇÕES AUXILIARES ---
def run_pln_processor(question: str) -> dict:
    """Executa o script Python do PLN de forma robusta."""
    # Tenta 'python3' primeiro, se falhar, tenta 'python'. Ideal para ambientes como o Render.
    python_executables = ['python3', 'python']
    for executable in python_executables:
        try:
            process = subprocess.run(
                [executable, PLN_SCRIPT_PATH, question], 
                capture_output=True, text=True, check=True, encoding='utf-8', timeout=20
            )
            return json.loads(process.stdout)
        except FileNotFoundError:
            continue # Tenta o próximo executável
        except subprocess.TimeoutExpired:
            return {"erro": "O processamento da linguagem demorou demais."}
        except subprocess.CalledProcessError as e:
            # Tenta parsear o stdout mesmo em erro, pois o script pode ter impresso um erro JSON
            try:
                return json.loads(e.stdout)
            except json.JSONDecodeError:
                return {"erro": f"O script PLN falhou e não retornou um JSON válido. Stderr: {e.stderr}"}
        except Exception as e:
            return {"erro": f"Falha desconhecida ao executar o processo PLN: {e}"}
    return {"erro": "Nenhum executável Python ('python3' ou 'python') foi encontrado no ambiente."}

def build_sparql_query(template_name: str, entities: dict) -> dict:
    """Constrói a consulta SPARQL substituindo placeholders no template."""
    template_path = os.path.join(TEMPLATES_DIR, f"{template_name}.txt")
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            final_query = f.read()

        # Substituição inteligente de placeholders
        for placeholder, value in entities.items():
            if value is None: continue

            # Trata o caso especial de label com tag de idioma
            if placeholder == "#ENTIDADE_NOME#" and (template_name == "Template_1A" or template_name == "Template_2A"):
                literal_com_idioma = f'"{str(value).replace("\"", "\\\"")}"@pt'
                final_query = final_query.replace(f"{placeholder}@pt", literal_com_idioma)
            elif placeholder == "#DATA#":
                literal_tipado = f'"{value}"^^xsd:date'
                final_query = final_query.replace(placeholder, literal_tipado)
            elif placeholder in ["#VALOR_DESEJADO#", "#SETOR_URI#"]:
                # Substituição direta para URIs ou partes de sintaxe
                final_query = final_query.replace(placeholder, str(value))
            else: # Para #ENTIDADE_NOME# em 1B e #SETOR# em 3A/4A
                literal_string = f'"{str(value).replace("\"", "\\\"")}"'
                final_query = final_query.replace(placeholder, literal_string)

        return {"sparql_query": final_query}
    except FileNotFoundError:
        return {"error": f"Arquivo de template '{template_path}' não encontrado no servidor."}
    except Exception as e:
        return {"error": f"Erro ao construir a consulta: {e}"}


def execute_local_sparql(query_string: str) -> dict:
    """Executa a consulta SPARQL e formata a resposta."""
    if len(graph) == 0:
        return {"error": "A base de conhecimento local não está carregada ou está vazia."}
    try:
        results = graph.query(query_string)
        
        # Extrai os nomes das variáveis do resultado (ex: ['ticker', 'volume'])
        var_names = [str(v) for v in results.vars]

        # Formata a saída como uma string simples, lidando com 1 ou mais colunas
        output_lines = []
        for row in results:
            line_parts = []
            for var in var_names:
                # Converte o valor para string, seja Literal, URIRef ou outro
                value = row[var]
                line_parts.append(str(value) if value else "N/A")
            output_lines.append(" - ".join(line_parts))
        
        formatted_data = "\n".join(output_lines)
        return {"data": formatted_data if formatted_data else "Nenhum resultado encontrado."}

    except Exception as e:
        logging.error(f"Erro na execução do SPARQL: {e}", exc_info=True)
        return {"error": f"A consulta SPARQL parece ser inválida. Detalhes: {e}"}

# --- 5. PONTO DE ENTRADA ---
if __name__ == '__main__':
    # A porta é definida pelo Render através da variável de ambiente PORT
    port = int(os.environ.get("PORT", 10000))
    # 'debug=False' é importante para produção
    app.run(host='0.0.0.0', port=port, debug=False)