from flask import Flask, request, jsonify, send_from_directory
import subprocess
import json
import os
from rdflib import Graph, Namespace
from rdflib.plugins.sparql import prepareQuery
import logging
import sys
import re

# Configuração do logging do Flask
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
flask_logger = logging.getLogger('flask.app')

app = Flask(__name__, static_folder='src/main/resources/static')

# --- CONFIGURAÇÕES DE CAMINHO DENTRO DO CONTAINER ---
BASE_APP_DIR = "/app"

PLN_PROCESSOR_SCRIPT_PATH = os.path.join(BASE_APP_DIR, "src", "main", "resources", "pln_processor.py")
CWD_FOR_PLN = os.path.join(BASE_APP_DIR, "src", "main", "resources")
SPARQL_TEMPLATES_DIR = os.path.join(BASE_APP_DIR, "src", "main", "resources", "Templates")

# ATENÇÃO: Verifique se este é o caminho correto no container Docker.
# Se 'ontologiaB3_com_inferencia.ttl' está na raiz do seu projeto, este caminho está correto.
# Se estiver dentro de 'src/main/resources', o caminho seria os.path.join(CWD_FOR_PLN, "ontologiaB3_com_inferencia.ttl")
ONTOLOGY_FILE_PATH = os.path.join(BASE_APP_DIR, "ontologiaB3_com_inferencia.ttl")
flask_logger.info(f"Caminho configurado para a ontologia: {ONTOLOGY_FILE_PATH}")

# Carregar a ontologia
graph = Graph()
NS_B3 = Namespace("https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#")
NS_STOCK = Namespace("https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#") # Pode ser o mesmo que NS_B3
NS_RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
NS_RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
NS_XSD = Namespace("http://www.w3.org/2001/XMLSchema#")
NS_OWL = Namespace("http://www.w3.org/2002/07/owl#")

graph.bind("b3", NS_B3)
graph.bind("stock", NS_STOCK)
graph.bind("rdf", NS_RDF)
graph.bind("rdfs", NS_RDFS)
graph.bind("xsd", NS_XSD)
graph.bind("owl", NS_OWL)

INIT_NS = {
    "b3": NS_B3, "stock": NS_STOCK, "rdf": NS_RDF, "rdfs": NS_RDFS,
    "xsd": NS_XSD, "owl": NS_OWL
}

if os.path.exists(ONTOLOGY_FILE_PATH):
    flask_logger.info(f"Carregando ontologia de: {ONTOLOGY_FILE_PATH}")
    try:
        graph.parse(ONTOLOGY_FILE_PATH, format="turtle")
        flask_logger.info(f"Ontologia carregada com {len(graph)} triplas.")
        if len(graph) == 0:
            flask_logger.warning("AVISO: A ontologia foi carregada, mas está vazia (0 triplas). Verifique o arquivo.")
    except Exception as e:
        flask_logger.error(f"Erro CRÍTICO ao carregar ontologia de {ONTOLOGY_FILE_PATH}: {e}. A aplicação pode não funcionar corretamente.", exc_info=True)
else:
    flask_logger.error(f"ARQUIVO DE ONTOLOGIA NÃO ENCONTRADO EM: {ONTOLOGY_FILE_PATH}. As consultas SPARQL falharão.")

@app.route('/', methods=['GET'])
def index():
    flask_logger.info(f"Tentando servir arquivo estático: 'index2.html' de '{app.static_folder}'")
    if not os.path.exists(os.path.join(app.static_folder, 'index2.html')):
        flask_logger.error(f"Arquivo 'index2.html' NÃO ENCONTRADO em {app.static_folder}")
        return "Erro: Arquivo de interface 'index2.html' não encontrado.", 404
    try:
        return send_from_directory(app.static_folder, 'index2.html')
    except Exception as e:
        flask_logger.error(f"Erro ao tentar servir o index2.html de {app.static_folder}: {e}", exc_info=True)
        return "Erro ao carregar a interface principal. Verifique os logs do servidor.", 500

@app.route('/processar_pergunta', methods=['POST'])
def processar_pergunta_completa():
    data = request.get_json()
    if not data or 'pergunta' not in data:
        flask_logger.warning("Requisição recebida sem 'pergunta' no corpo JSON.")
        return jsonify({"erro": "Pergunta não fornecida no corpo JSON", "sparqlQuery": "N/A"}), 400

    pergunta_usuario = data['pergunta']
    flask_logger.info(f"Recebida pergunta: '{pergunta_usuario}'")

    pln_output_json_obj = None
    output_str_pln = ""
    try:
        if not os.path.exists(PLN_PROCESSOR_SCRIPT_PATH):
            flask_logger.error(f"Script PLN NÃO ENCONTRADO em: {PLN_PROCESSOR_SCRIPT_PATH}")
            return jsonify({"erro": f"Script PLN não encontrado no servidor.", "sparqlQuery": "N/A (Erro de configuração)"}), 500

        flask_logger.info(f"Chamando PLN: python {PLN_PROCESSOR_SCRIPT_PATH} '{pergunta_usuario}' com CWD: {CWD_FOR_PLN}")
        process_pln = subprocess.run(
            ['python', PLN_PROCESSOR_SCRIPT_PATH, pergunta_usuario],
            capture_output=True, text=True, check=False, cwd=CWD_FOR_PLN, env=dict(os.environ, PYTHONIOENCODING='utf-8')
        )

        output_str_pln = process_pln.stdout.strip() if process_pln.stdout.strip() else process_pln.stderr.strip()

        flask_logger.debug(f"Saída bruta PLN (stdout): {process_pln.stdout.strip()}")
        flask_logger.debug(f"Saída bruta PLN (stderr): {process_pln.stderr.strip()}") # Erros do script PLN podem vir aqui
        flask_logger.info(f"Código de saída do PLN: {process_pln.returncode}")

        if process_pln.returncode != 0:
            flask_logger.error(f"PLN executado com erro (código {process_pln.returncode}). Saída: {output_str_pln}")
            # Mesmo com erro, tenta parsear o JSON, pois o PLN pode retornar um erro estruturado
            # Mas se não conseguir, o erro genérico abaixo será usado.

        if not output_str_pln:
            flask_logger.error("PLN não produziu saída (stdout/stderr).")
            return jsonify({"erro": "PLN não produziu saída.", "sparqlQuery": "N/A (Erro no PLN)"}), 500

        pln_output_json_obj = json.loads(output_str_pln)
        flask_logger.info(f"PLN output (parsed JSON): {json.dumps(pln_output_json_obj, ensure_ascii=False)}") # Log do JSON completo

        if "erro" in pln_output_json_obj:
            flask_logger.error(f"Erro estruturado retornado pelo PLN: {pln_output_json_obj['erro']}")
            return jsonify(pln_output_json_obj), 400 # Erro de input/lógica do PLN

        if "template_nome" not in pln_output_json_obj or "mapeamentos" not in pln_output_json_obj:
            flask_logger.error(f"Saída do PLN inesperada ou incompleta: {pln_output_json_obj}")
            return jsonify({"erro": "Saída do PLN inválida ou incompleta.", "sparqlQuery": "N/A", "debug_pln_output": output_str_pln}), 500

    except json.JSONDecodeError as jde:
        flask_logger.error(f"Erro ao decodificar JSON do PLN: {jde}. Saída PLN: {output_str_pln}", exc_info=True)
        return jsonify({"erro": "Erro ao decodificar saída do PLN.", "sparqlQuery": "N/A (Erro na decodificação PLN)", "debug_pln_output": output_str_pln}), 500
    except FileNotFoundError: # Especificamente para o caso do script python não ser encontrado
        flask_logger.error(f"Erro: Script PLN '{PLN_PROCESSOR_SCRIPT_PATH}' não encontrado.", exc_info=True)
        return jsonify({"erro": f"Erro crítico: Script PLN não encontrado.", "sparqlQuery": "N/A (Erro de configuração)"}), 500
    except Exception as e_pln:
        flask_logger.error(f"Erro genérico ao executar PLN: {e_pln}", exc_info=True)
        return jsonify({"erro": f"Erro crítico ao executar o processador PLN: {str(e_pln)}", "sparqlQuery": "N/A (Erro no PLN)"}), 500

    template_nome = pln_output_json_obj.get("template_nome")
    mapeamentos = pln_output_json_obj.get("mapeamentos", {})
    flask_logger.info(f"PLN retornou: template='{template_nome}', mapeamentos='{json.dumps(mapeamentos, ensure_ascii=False)}'")

    sparql_query_string_final = "Consulta SPARQL não pôde ser gerada."
    sparql_query_template_content = "Template SPARQL não carregado."
    try:
        template_filename = f"{template_nome}.txt"
        template_file_path = os.path.join(SPARQL_TEMPLATES_DIR, template_filename)
        flask_logger.info(f"Tentando carregar template SPARQL de: {template_file_path}")

        if not os.path.exists(template_file_path):
            flask_logger.error(f"Arquivo de template SPARQL NÃO ENCONTRADO: {template_file_path}")
            return jsonify({"erro": f"Template SPARQL '{template_filename}' não encontrado.", "sparqlQuery": "N/A (Erro de configuração)"}), 500

        with open(template_file_path, 'r', encoding='utf-8') as f_template:
            sparql_query_template_content = f_template.read()

        sparql_query_string_final = sparql_query_template_content
        flask_logger.debug(f"Template '{template_nome}' carregado. Conteúdo inicial:\n{sparql_query_string_final}")

        for placeholder_key, valor_raw in mapeamentos.items():
            valor_sparql_formatado = None
            valor_str_raw = str(valor_raw) # Garantir que é string

            # Log antes da substituição para ver o que será substituído
            flask_logger.info(f"Para template '{template_nome}', placeholder '{placeholder_key}', valor raw do PLN: '{valor_str_raw}'")

            if str(placeholder_key) not in sparql_query_string_final:
                flask_logger.debug(f"Placeholder '{placeholder_key}' do PLN não encontrado no template '{template_nome}'. Ignorando.")
                continue

            # Lógica de formatação de valor para SPARQL
            if placeholder_key == "#DATA#":
                # Validação simples de data (YYYY-MM-DD) - ajuste conforme necessário
                if re.match(r"^\d{4}-\d{2}-\d{2}$", valor_str_raw):
                    valor_sparql_formatado = f'"{valor_str_raw}"^^xsd:date'
                else:
                    flask_logger.warning(f"Valor para #DATA# ('{valor_str_raw}') não parece ser uma data válida YYYY-MM-DD. Usando como string literal.")
                    valor_sparql_formatado = f'"{valor_str_raw}"' # Fallback para string se não for data
            elif placeholder_key == "#ENTIDADE_NOME#": # Para nomes de empresa, tickers, etc. que vão como strings no SPARQL
                valor_escapado = valor_str_raw.replace('\\', '\\\\').replace('"', '\\"')
                valor_sparql_formatado = f'"{valor_escapado}"'
            elif placeholder_key == "#VALOR_DESEJADO#": # Para predicados como b3:precoFechamento
                if ":" not in valor_str_raw and not valor_str_raw.startswith("<"): # Se não for URI completo ou prefixed name
                    valor_sparql_formatado = f'b3:{valor_str_raw}' # Adiciona prefixo default 'b3:'
                else:
                    valor_sparql_formatado = valor_str_raw # Assume que já está formatado (ex: stock:precoFechamento)
            elif placeholder_key == "#SETOR#": # Especificamente para o filtro de setor
                valor_escapado = valor_str_raw.replace('\\', '\\\\').replace('"', '\\"')
                valor_sparql_formatado = f'"{valor_escapado}"' # Será usado como string literal no FILTER
            else: # Fallback para outros placeholders genéricos (tratar como string)
                if str(placeholder_key).startswith("#") and str(placeholder_key).endswith("#"):
                    flask_logger.warning(f"Placeholder '{placeholder_key}' não possui formatação explícita definida. Tratando como string literal SPARQL.")
                    valor_escapado = valor_str_raw.replace('\\', '\\\\').replace('"', '\\"')
                    valor_sparql_formatado = f'"{valor_escapado}"'
                else:
                    flask_logger.debug(f"Item '{placeholder_key}' em mapeamentos não é um placeholder padrão, ignorando substituição.")
                    continue

            if valor_sparql_formatado is not None:
                flask_logger.info(f"Substituindo '{placeholder_key}' por '{valor_sparql_formatado}' na query.")
                sparql_query_string_final = sparql_query_string_final.replace(str(placeholder_key), valor_sparql_formatado)

        flask_logger.info(f"--- CONSULTA SPARQL FINAL GERADA (Template: {template_nome}) ---\n{sparql_query_string_final}\n----------------------------------------------------")

        placeholders_restantes = re.findall(r'(#\w+#)', sparql_query_string_final)
        if placeholders_restantes:
            placeholders_nao_comentados = []
            linhas_query = sparql_query_string_final.splitlines()
            for ph_restante in placeholders_restantes:
                encontrado_nao_comentado = False
                for linha in linhas_query:
                    if ph_restante in linha and not linha.strip().startswith("#"): # Ignora linhas comentadas
                        encontrado_nao_comentado = True
                        break
                if encontrado_nao_comentado:
                    placeholders_nao_comentados.append(ph_restante)
            
            if placeholders_nao_comentados:
                flask_logger.warning(f"AVISO: Query final AINDA CONTÉM placeholders NÃO COMENTADOS não substituídos: {', '.join(placeholders_nao_comentados)}. Isso pode levar a erros na consulta SPARQL.")

    except Exception as e_template:
        flask_logger.error(f"Erro ao processar template SPARQL '{template_nome}': {e_template}", exc_info=True)
        return jsonify({"erro": f"Erro ao gerar consulta SPARQL: {str(e_template)}", "sparqlQuery": sparql_query_template_content}), 500

    resposta_formatada_final = "Não foi possível executar a consulta ou não houve resultados."
    try:
        if not graph or len(graph) == 0:
            flask_logger.error("ONTOLOGIA NÃO CARREGADA OU VAZIA. Não é possível executar a consulta SPARQL. Verifique o carregamento da ontologia e o arquivo.")
            return jsonify({"erro": "Falha crítica: Ontologia não disponível para consulta.", "sparqlQuery": sparql_query_string_final}), 500

        query_obj = prepareQuery(sparql_query_string_final, initNs=INIT_NS)
        flask_logger.info(f"Executando consulta SPARQL (Template: {template_nome})...")
        qres = graph.query(query_obj)

        resultados_json_list = []
        if qres.type == 'SELECT':
            all_rows_from_select = list(qres) # Materializa resultados
            num_resultados = len(all_rows_from_select)
            flask_logger.info(f"--- {template_nome}: Número de linhas/resultados SELECT encontrados: {num_resultados} ---")

            if num_resultados == 0:
                 flask_logger.info(f"A consulta SELECT para o template '{template_nome}' não retornou resultados. Query:\n{sparql_query_string_final}")
                 # Isso é importante para a Pergunta 4. Se aqui for 0, o problema está na query/dados, não no código de formatação.
            
            for row_data in all_rows_from_select:
                row_dict = {}
                if hasattr(row_data, 'labels'):
                    for var_name in row_data.labels:
                        value = row_data[var_name]
                        row_dict[str(var_name)] = str(value) if value is not None else None
                else: # Fallback menos provável
                    for i, item in enumerate(row_data):
                        row_dict[f"var_{i}"] = str(item) if item is not None else None
                if row_dict:
                    resultados_json_list.append(row_dict)

            if not resultados_json_list:
                resposta_formatada_final = "Nenhum resultado encontrado."
            else:
                # Para a pergunta 4, que espera uma lista de tickers, esta formatação pode ser útil
                if template_nome == "Template_3A" and all('valor' in res for res in resultados_json_list):
                    tickers_list = sorted(list(set(res['valor'] for res in resultados_json_list if res.get('valor'))))
                    if tickers_list:
                         resposta_formatada_final = json.dumps(tickers_list, ensure_ascii=False)
                    else: # Se 'valor' não estava presente ou estava None/vazio em todos
                         resposta_formatada_final = json.dumps(resultados_json_list, ensure_ascii=False) # Fallback para lista de dicts
                else:
                    resposta_formatada_final = json.dumps(resultados_json_list, ensure_ascii=False)

        elif qres.type == 'ASK':
            ask_result = False
            for row_ask in qres: ask_result = row_ask; break
            resposta_formatada_final = json.dumps({"resultado_ask": ask_result})
        
        elif qres.type == 'CONSTRUCT' or qres.type == 'DESCRIBE':
            resposta_serializada = qres.serialize(format='turtle')
            if not resposta_serializada.strip():
                resposta_formatada_final = "Nenhum resultado para CONSTRUCT/DESCRIBE."
            else:
                resposta_formatada_final = resposta_serializada # Retorna como string Turtle
        else:
            resposta_formatada_final = f"Tipo de consulta não suportado para formatação de resposta: {qres.type}"

        flask_logger.info(f"Consulta SPARQL executada (Template: {template_nome}). Tipo: {qres.type}. Resposta (início): {str(resposta_formatada_final)[:300]}...")

    except Exception as e_sparql:
        flask_logger.error(f"Erro CRÍTICO ao executar consulta SPARQL (Template: {template_nome}): {e_sparql}", exc_info=True)
        flask_logger.error(f"Consulta que falhou (Template: {template_nome}): \n{sparql_query_string_final}")
        return jsonify({"erro": f"Erro ao executar consulta SPARQL: {str(e_sparql)}", "sparqlQuery": sparql_query_string_final}), 500

    return jsonify({
        "sparqlQuery": sparql_query_string_final,
        "resposta": resposta_formatada_final
    })

if __name__ == '__main__':
    # Render define a variável de ambiente PORT
    local_port = int(os.environ.get("PORT", 8080)) # Usar 8080 como padrão local se PORT não estiver definida
    flask_logger.info(f"Iniciando servidor Flask em http://0.0.0.0:{local_port}")
    # debug=False é crucial para produção. Gunicorn (ou similar) é usado no Render.
    # Para testes locais, você pode mudar debug=True temporariamente, mas NUNCA em produção.
    app.run(host='0.0.0.0', port=local_port, debug=False)