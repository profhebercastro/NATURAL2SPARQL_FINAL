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

app = Flask(__name__, static_folder='src/main/resources/static') # Static folder para o frontend HTML/JS/CSS

# --- CONFIGURAÇÕES DE CAMINHO DENTRO DO CONTAINER ---
BASE_APP_DIR = "/app" # Diretório base da aplicação no container Docker

# Caminho para o script PLN dentro da estrutura de resources copiada para o container
PLN_PROCESSOR_SCRIPT_PATH = os.path.join(BASE_APP_DIR, "src", "main", "resources", "pln_processor.py")
# Diretório de trabalho para o script PLN (onde ele espera encontrar seus próprios resources como setor_map.json)
CWD_FOR_PLN = os.path.join(BASE_APP_DIR, "src", "main", "resources")
# Diretório onde os templates SPARQL .txt estão localizados
SPARQL_TEMPLATES_DIR = os.path.join(BASE_APP_DIR, "src", "main", "resources", "Templates")
# Caminho para o arquivo de ontologia principal que será carregado
ONTOLOGY_FILE_PATH = os.path.join(BASE_APP_DIR, "ontologiaB3_com_inferencia.ttl") # USANDO A ONTOLOGIA COM INFERENCIA

# Carregar a ontologia
graph = Graph()
NS_B3 = Namespace("https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#")
NS_STOCK = Namespace("https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#")
NS_RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
NS_RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
NS_XSD = Namespace("http://www.w3.org/2001/XMLSchema#")
NS_OWL = Namespace("http://www.w3.org/2002/07/owl#")

# Bind dos prefixos para serem usados nas queries e serialização
graph.bind("b3", NS_B3)
graph.bind("stock", NS_STOCK)
graph.bind("rdf", NS_RDF)
graph.bind("rdfs", NS_RDFS)
graph.bind("xsd", NS_XSD)
graph.bind("owl", NS_OWL)

# Dicionário de namespaces para prepareQuery
INIT_NS = {
    "b3": NS_B3, "stock": NS_STOCK, "rdf": NS_RDF, "rdfs": NS_RDFS,
    "xsd": NS_XSD, "owl": NS_OWL
}

# Tenta carregar a ontologia na inicialização da aplicação
if os.path.exists(ONTOLOGY_FILE_PATH):
    flask_logger.info(f"Carregando ontologia de: {ONTOLOGY_FILE_PATH}")
    try:
        graph.parse(ONTOLOGY_FILE_PATH, format="turtle")
        flask_logger.info(f"Ontologia carregada com {len(graph)} triplas.")
    except Exception as e:
        flask_logger.error(f"Erro CRÍTICO ao carregar ontologia de {ONTOLOGY_FILE_PATH}: {e}. A aplicação pode não funcionar corretamente.", exc_info=True)
else:
    flask_logger.error(f"ARQUIVO DE ONTOLOGIA NÃO ENCONTRADO EM: {ONTOLOGY_FILE_PATH}. As consultas SPARQL falharão.")

@app.route('/', methods=['GET'])
def index():
    # Servir a página HTML principal do frontend
    # static_folder está configurado no Flask(__name__, static_folder=...)
    # Flask procura 'index2.html' dentro dessa static_folder.
    # O caminho no Dockerfile deve copiar 'src/main/resources/static' para '/app/src/main/resources/static'
    flask_logger.info(f"Tentando servir arquivo estático: 'index2.html' de '{app.static_folder}'")
    try:
        return send_from_directory(app.static_folder, 'index2.html')
    except Exception as e:
        flask_logger.error(f"Erro ao tentar servir o index2.html de {app.static_folder}: {e}", exc_info=True)
        return "Erro ao carregar a interface principal. Verifique os logs do servidor.", 500

@app.route('/processar_pergunta', methods=['POST'])
def processar_pergunta_completa():
    data = request.get_json()
    if not data or 'pergunta' not in data:
        return jsonify({"erro": "Pergunta não fornecida no corpo JSON", "sparqlQuery": "N/A"}), 400

    pergunta_usuario = data['pergunta']
    flask_logger.info(f"Recebida pergunta: '{pergunta_usuario}'")

    pln_output_json_obj = None 
    output_str_pln = "" # Para armazenar a saída bruta do PLN para debug
    try:
        # Chama o script pln_processor.py como um subprocesso
        flask_logger.info(f"Chamando PLN: python {PLN_PROCESSOR_SCRIPT_PATH} '{pergunta_usuario}' com CWD: {CWD_FOR_PLN}")
        process_pln = subprocess.run(
            ['python', PLN_PROCESSOR_SCRIPT_PATH, pergunta_usuario],
            capture_output=True, text=True, check=False, cwd=CWD_FOR_PLN, env=dict(os.environ)
        )
        
        # Prioriza stdout, mas usa stderr se stdout estiver vazio (para capturar erros do script PLN)
        output_str_pln = process_pln.stdout.strip() if process_pln.stdout.strip() else process_pln.stderr.strip()
        
        flask_logger.debug(f"Saída bruta PLN (stdout): {process_pln.stdout[:500].strip()}...")
        flask_logger.debug(f"Saída bruta PLN (stderr): {process_pln.stderr[:500].strip()}...")
        flask_logger.info(f"Código de saída do PLN: {process_pln.returncode}")

        if not output_str_pln: # Se ambas as saídas estiverem vazias
            flask_logger.error("PLN não produziu saída (stdout/stderr).")
            return jsonify({"erro": "PLN não produziu saída.", "sparqlQuery": "N/A (Erro no PLN)"}), 500
        
        pln_output_json_obj = json.loads(output_str_pln) # Tenta decodificar a saída (que deve ser JSON)

        # Verifica se o JSON retornado pelo PLN contém um erro estruturado
        if "erro" in pln_output_json_obj:
            flask_logger.error(f"Erro estruturado retornado pelo PLN: {pln_output_json_obj['erro']}")
            # Retorna o erro do PLN diretamente, mas com código 400 se for erro de input/lógica do PLN
            return jsonify(pln_output_json_obj), 400 if process_pln.returncode == 0 else 500
        
        # Valida se a saída do PLN tem os campos esperados
        if "template_nome" not in pln_output_json_obj or "mapeamentos" not in pln_output_json_obj:
            flask_logger.error(f"Saída do PLN inesperada ou incompleta: {pln_output_json_obj}")
            return jsonify({"erro": "Saída do PLN inválida ou incompleta.", "sparqlQuery": "N/A", "debug_pln_output": output_str_pln}), 500

    except json.JSONDecodeError as jde:
        flask_logger.error(f"Erro ao decodificar JSON do PLN: {jde}. Saída PLN: {output_str_pln}")
        return jsonify({"erro": "Erro ao decodificar saída do PLN.", "sparqlQuery": "N/A (Erro na decodificação PLN)", "debug_pln_output": output_str_pln}), 500
    except Exception as e_pln: # Captura outros erros na execução do PLN (e.g., FileNotFoundError se o script não existir)
        flask_logger.error(f"Erro genérico ao executar PLN: {e_pln}", exc_info=True)
        return jsonify({"erro": f"Erro crítico ao executar o processador PLN: {str(e_pln)}", "sparqlQuery": "N/A (Erro no PLN)"}), 500

    template_nome = pln_output_json_obj.get("template_nome") # Ex: "Template_3A"
    mapeamentos = pln_output_json_obj.get("mapeamentos", {})
    flask_logger.info(f"PLN retornou: template='{template_nome}', mapeamentos='{mapeamentos}'")

    sparql_query_string_final = "Consulta SPARQL não pôde ser gerada."
    sparql_query_template_content = "Template SPARQL não carregado." # Para debug
    try:
        # template_nome já deve vir com underscore do pln_processor.py se necessário
        template_filename = f"{template_nome}.txt" # Ex: "Template_3A.txt"
        template_file_path = os.path.join(SPARQL_TEMPLATES_DIR, template_filename)
        flask_logger.info(f"Tentando carregar template SPARQL de: {template_file_path}")

        if not os.path.exists(template_file_path):
            flask_logger.error(f"Arquivo de template SPARQL não encontrado: {template_file_path}")
            return jsonify({"erro": f"Template SPARQL '{template_filename}' não encontrado.", "sparqlQuery": "N/A"}), 500
        
        with open(template_file_path, 'r', encoding='utf-8') as f_template:
            sparql_query_template_content = f_template.read()
        
        sparql_query_string_final = sparql_query_template_content

        for placeholder_key, valor_raw in mapeamentos.items():
            valor_sparql_formatado = None 
            valor_str_raw = str(valor_raw)

            # Só tenta substituir se o placeholder existir no template atual
            if str(placeholder_key) not in sparql_query_string_final:
                flask_logger.debug(f"Placeholder '{placeholder_key}' do PLN não encontrado no template '{template_nome}'. Ignorando.")
                continue

            if placeholder_key == "#DATA#":
                valor_sparql_formatado = f'"{valor_str_raw}"^^xsd:date'
            elif placeholder_key == "#ENTIDADE_NOME#":
                valor_escapado = valor_str_raw.replace('\\', '\\\\').replace('"', '\\"')
                valor_sparql_formatado = f'"{valor_escapado}"'
            elif placeholder_key == "#VALOR_DESEJADO#":
                if ":" not in valor_str_raw and not valor_str_raw.startswith("<"):
                    valor_sparql_formatado = f'b3:{valor_str_raw}'
                else:
                    valor_sparql_formatado = valor_str_raw
            elif placeholder_key == "#SETOR#":
                valor_escapado = valor_str_raw.replace('\\', '\\\\').replace('"', '\\"')
                valor_sparql_formatado = f'"{valor_escapado}"'
            else:
                if str(placeholder_key).startswith("#") and str(placeholder_key).endswith("#"):
                    flask_logger.warning(f"Placeholder '{placeholder_key}' não possui formatação explícita. Tratando como string literal SPARQL.")
                    valor_escapado = valor_str_raw.replace('\\', '\\\\').replace('"', '\\"')
                    valor_sparql_formatado = f'"{valor_escapado}"'
                else:
                    flask_logger.debug(f"Item '{placeholder_key}' em mapeamentos não é um placeholder padrão, ignorando substituição.")
                    continue

            if valor_sparql_formatado is not None:
                flask_logger.info(f"Substituindo '{placeholder_key}' por '{valor_sparql_formatado}' na query.")
                sparql_query_string_final = sparql_query_string_final.replace(str(placeholder_key), valor_sparql_formatado)
        
        flask_logger.info(f"Consulta SPARQL final (após todas as substituições):\n{sparql_query_string_final}")
        
        placeholders_restantes = re.findall(r'(#\w+#)', sparql_query_string_final)
        if placeholders_restantes:
            # Verifica se os placeholders restantes estão em linhas comentadas
            placeholders_nao_comentados = []
            linhas_query = sparql_query_string_final.splitlines()
            for ph_restante in placeholders_restantes:
                encontrado_nao_comentado = False
                for linha in linhas_query:
                    if ph_restante in linha and not linha.strip().startswith("#"):
                        encontrado_nao_comentado = True
                        break
                if encontrado_nao_comentado:
                    placeholders_nao_comentados.append(ph_restante)
            
            if placeholders_nao_comentados:
                flask_logger.warning(f"AVISO: Query final AINDA CONTÉM placeholders NÃO COMENTADOS não substituídos: {', '.join(placeholders_nao_comentados)}. Query:\n{sparql_query_string_final}")

    except Exception as e_template:
        flask_logger.error(f"Erro ao processar template SPARQL: {e_template}", exc_info=True)
        return jsonify({"erro": f"Erro ao gerar consulta SPARQL: {str(e_template)}", "sparqlQuery": sparql_query_template_content}), 500

    resposta_formatada_final = "Não foi possível executar a consulta ou não houve resultados."
    try:
        if not graph or len(graph) == 0:
            flask_logger.error("Ontologia não carregada ou vazia. Verifique o caminho e o arquivo da ontologia.")
            return jsonify({"erro": "Falha ao carregar a ontologia base.", "sparqlQuery": sparql_query_string_final}), 500
        
        query_obj = prepareQuery(sparql_query_string_final, initNs=INIT_NS)
        flask_logger.info("Executando consulta SPARQL principal...")
        qres = graph.query(query_obj)
        
        resultados_json_list = []
        
        if qres.type == 'SELECT':
            # Materializa os resultados para poder contar e iterar
            all_rows_from_select = list(qres) 
            flask_logger.info(f"--- {template_nome}: Número de linhas/resultados SELECT encontrados: {len(all_rows_from_select)} ---")

            for row_data in all_rows_from_select: # Itera sobre a lista já materializada
                row_dict = {}
                # row_data.labels contém os nomes das variáveis SELECT para aquela linha
                if hasattr(row_data, 'labels'): 
                    for var_name in row_data.labels:
                        value = row_data[var_name] # Acessa o valor usando o nome da variável
                        row_dict[str(var_name)] = str(value) if value is not None else None
                else:
                    # Fallback menos provável com rdflib moderno, mas para segurança
                    flask_logger.warning("row_data não tem atributo 'labels'. Tentando iterar como tupla (pode ser impreciso).")
                    # Se não houver labels, qres.vars (antes da conversão para lista) poderia ser usado,
                    # mas é mais complexo de alinhar aqui. Este fallback é básico.
                    for i, item in enumerate(row_data):
                        row_dict[f"var_{i}"] = str(item) if item is not None else None
                
                if row_dict: # Adiciona apenas se o dicionário não estiver vazio
                    resultados_json_list.append(row_dict)

            if not resultados_json_list:
                resposta_formatada_final = "Nenhum resultado encontrado." 
            else:
                resposta_formatada_final = json.dumps(resultados_json_list, ensure_ascii=False)
        
        elif qres.type == 'ASK':
            ask_result = False # Default
            # Itera sobre o resultado ASK (que deve ter no máximo uma solução)
            # bool(next(iter(qres), False)) é uma forma idiomática
            for row_ask in qres: # qres para ASK é um gerador que produz um booleano
                ask_result = row_ask # O resultado em si é o booleano
                break 
            resposta_formatada_final = json.dumps({"resultado_ask": ask_result})
        
        elif qres.type == 'CONSTRUCT' or qres.type == 'DESCRIBE':
            resposta_serializada = qres.serialize(format='turtle') # Turtle é um formato comum
            if not resposta_serializada.strip(): 
                resposta_formatada_final = "Nenhum resultado para CONSTRUCT/DESCRIBE."
            else:
                resposta_formatada_final = resposta_serializada
        else:
            resposta_formatada_final = f"Tipo de consulta não suportado para formatação de resposta: {qres.type}"
            
        flask_logger.info(f"Consulta SPARQL executada. Tipo: {qres.type}. Resposta (início): {str(resposta_formatada_final)[:200]}...")

    except Exception as e_sparql:
        flask_logger.error(f"Erro ao executar consulta SPARQL principal: {e_sparql}", exc_info=True)
        flask_logger.error(f"Consulta que falhou: \n{sparql_query_string_final}")
        return jsonify({"erro": f"Erro ao executar consulta SPARQL: {str(e_sparql)}", "sparqlQuery": sparql_query_string_final}), 500

    return jsonify({
        "sparqlQuery": sparql_query_string_final,
        "resposta": resposta_formatada_final
    })

if __name__ == '__main__':
    local_port = int(os.environ.get("PORT", 5000)) # Render usa PORT; 5000 é um padrão comum
    flask_logger.info(f"Iniciando servidor Flask em http://0.0.0.0:{local_port}")
    # debug=False para produção. O Gunicorn (ou outro servidor WSGI) é usado no Render.
    app.run(host='0.0.0.0', port=local_port, debug=False)