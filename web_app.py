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
# Configuração do logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Inicialização do Flask. A pasta 'static' será usada para servir arquivos de interface.
app = Flask(__name__)

# --- CONFIGURAÇÃO DE CAMINHOS RELATIVOS ---
# Define o diretório base como o local onde o script web_app.py está.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PLN_PROCESSOR_SCRIPT_PATH = os.path.join(BASE_DIR, "pln_processor.py")
SPARQL_TEMPLATES_DIR = os.path.join(BASE_DIR, "templates_sparql")
ONTOLOGY_FILE_PATH = os.path.join(BASE_DIR, "ontologiaB3_com_inferencia.ttl")

logging.info(f"Diretório base da aplicação: {BASE_DIR}")
logging.info(f"Caminho do script PLN: {PLN_PROCESSOR_SCRIPT_PATH}")
logging.info(f"Caminho dos templates SPARQL: {SPARQL_TEMPLATES_DIR}")
logging.info(f"Caminho da ontologia: {ONTOLOGY_FILE_PATH}")

# --- CARREGAMENTO DA ONTOLOGIA ---
graph = Graph()
try:
    logging.info(f"Carregando ontologia de: {ONTOLOGY_FILE_PATH}")
    if not os.path.exists(ONTOLOGY_FILE_PATH):
        raise FileNotFoundError(f"Arquivo de ontologia não encontrado em {ONTOLOGY_FILE_PATH}")
    
    graph.parse(ONTOLOGY_FILE_PATH, format="turtle")
    logging.info(f"Ontologia carregada com {len(graph)} triplas.")
    if len(graph) == 0:
        logging.warning("AVISO: A ontologia foi carregada, mas está vazia (0 triplas). Verifique o arquivo.")
except Exception as e:
    logging.critical(f"Erro CRÍTICO ao carregar a ontologia: {e}", exc_info=True)
    # Em um ambiente de produção, você poderia optar por encerrar a aplicação se a ontologia é essencial.

# --- DEFINIÇÃO DAS ROTAS ---

@app.route('/')
def serve_index():
    """Serve a página principal (index2.html) da pasta 'static'."""
    logging.info("Tentando servir a página principal 'index2.html'.")
    return send_from_directory('static', 'index2.html')

@app.route('/processar_pergunta', methods=['POST'])
def processar_pergunta_completa():
    data = request.get_json()
    if not data or 'pergunta' not in data:
        logging.warning("Requisição recebida sem 'pergunta' no corpo JSON.")
        return jsonify({"erro": "Pergunta não fornecida"}), 400

    pergunta_usuario = data['pergunta']
    logging.info(f"Recebida pergunta: '{pergunta_usuario}'")

    # 1. Chamar o script de PLN
    try:
        logging.info(f"Executando script PLN: {PLN_PROCESSOR_SCRIPT_PATH}")
        process_pln = subprocess.run(
            ['python', PLN_PROCESSOR_SCRIPT_PATH, pergunta_usuario],
            capture_output=True, text=True, check=True, cwd=BASE_DIR, env=dict(os.environ, PYTHONIOENCODING='utf-8')
        )
        pln_output_str = process_pln.stdout.strip()
        pln_output_json = json.loads(pln_output_str)
        logging.info(f"PLN retornou: {pln_output_json}")

    except subprocess.CalledProcessError as e:
        logging.error(f"Erro ao executar o script PLN (código {e.returncode}): {e.stderr.strip()}")
        return jsonify({"erro": f"Erro no processador de linguagem: {e.stderr.strip()}"}), 500
    except json.JSONDecodeError:
        logging.error(f"Erro ao decodificar a saída JSON do PLN. Saída recebida: {process_pln.stdout.strip()}")
        return jsonify({"erro": "Formato de resposta do processador de linguagem inválido."}), 500
    except Exception as e:
        logging.error(f"Erro inesperado ao chamar o PLN: {e}", exc_info=True)
        return jsonify({"erro": "Erro interno no servidor ao processar a pergunta."}), 500

    # 2. Montar a query SPARQL a partir do template
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
            # Simplificação da lógica de substituição. Ajuste se precisar de formatação específica.
            formatted_value = f'"{str(value)}"' # Formatação padrão como string
            if placeholder == "#DATA#":
                 formatted_value = f'"{str(value)}"^^xsd:date'
            elif placeholder == "#VALOR_DESEJADO#":
                 formatted_value = str(value) # Não colocar aspas
            
            sparql_query_final = sparql_query_final.replace(placeholder, formatted_value)
        
        logging.info(f"Consulta SPARQL final gerada:\n{sparql_query_final}")

    except FileNotFoundError:
        logging.error(f"Arquivo de template não encontrado: {template_path}")
        return jsonify({"erro": f"Template SPARQL '{template_nome}' não encontrado no servidor."}), 500
    except Exception as e:
        logging.error(f"Erro ao montar a query SPARQL: {e}", exc_info=True)
        return jsonify({"erro": "Erro interno ao gerar a consulta."}), 500
    
    # 3. Executar a query na ontologia
    if len(graph) == 0:
        return jsonify({"erro": "A ontologia não está carregada. Não é possível executar a consulta."}), 500

    try:
        query_obj = prepareQuery(sparql_query_final)
        qres = graph.query(query_obj)
        
        resultados = []
        for row in qres:
            resultados.append({str(var): str(val) for var, val in row.asdict().items()})
        
        resposta_final = json.dumps(resultados, ensure_ascii=False) if resultados else "Nenhum resultado encontrado."
        logging.info(f"Consulta executada com sucesso. {len(resultados)} resultados encontrados.")

    except Exception as e:
        logging.error(f"Erro ao executar a consulta SPARQL: {e}", exc_info=True)
        return jsonify({"erro": "Erro ao consultar a base de conhecimento.", "sparqlQuery": sparql_query_final}), 500

    return jsonify({
        "sparqlQuery": sparql_query_final,
        "resposta": resposta_final
    })


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False)