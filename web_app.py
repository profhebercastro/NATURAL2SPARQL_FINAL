from flask import Flask, request, jsonify, send_from_directory
import subprocess
import json
import os
from rdflib import Graph, Namespace
from rdflib.plugins.sparql import prepareQuery
import logging
import sys
# import re # Não parece ser usado diretamente após a remoção de normalizar_para_regex_pattern
# import unicodedata # Não parece ser usado diretamente após a remoção de normalizar_para_regex_pattern

# Configuração do logging do Flask
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
flask_logger = logging.getLogger('flask.app')

app = Flask(__name__, static_folder='src/main/resources/static')

# --- CONFIGURAÇÕES DE CAMINHO DENTRO DO CONTAINER ---
BASE_APP_DIR = "/app"
PLN_PROCESSOR_SCRIPT_PATH = os.path.join(BASE_APP_DIR, "src", "main", "resources", "pln_processor.py")
CWD_FOR_PLN = os.path.join(BASE_APP_DIR, "src", "main", "resources")
SPARQL_TEMPLATES_DIR = os.path.join(BASE_APP_DIR, "src", "main", "resources", "Templates")
ONTOLOGY_FILE_PATH = os.path.join(BASE_APP_DIR, "ontologiaB3.ttl")

# Carregar a ontologia
graph = Graph()
NS_B3 = Namespace("https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#")
NS_STOCK = Namespace("https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#") # Duplicado, mas ok
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
    except Exception as e:
        flask_logger.error(f"Erro CRÍTICO ao carregar ontologia: {e}. A aplicação pode não funcionar corretamente.", exc_info=True)
else:
    flask_logger.error(f"ARQUIVO DE ONTOLOGIA NÃO ENCONTRADO EM: {ONTOLOGY_FILE_PATH}. As consultas SPARQL falharão.")

@app.route('/', methods=['GET'])
def index():
    flask_logger.info(f"Tentando servir: {app.static_folder} / index2.html")
    try:
        return send_from_directory(app.static_folder, 'index2.html')
    except Exception as e:
        flask_logger.error(f"Erro ao tentar servir o index2.html: {e}", exc_info=True)
        return "Erro ao carregar a interface principal. Verifique os logs do servidor.", 500

@app.route('/processar_pergunta', methods=['POSTCom'])
def processar_pergunta_completa():
    data = request.get_json()
    if not data or 'pergunta' not in data:
        return jsonify({"erro": "Pergunta não fornecida no corpo JSON", "sparqlQuery": "N/A"}), 400

    pergunta_usuario = data['pergunta']
    flask_logger.info(f"Recebida pergunta: '{pergunta_usuario}'")

    pln_output_json_obj = None # Para armazenar o objeto JSON deserializado
    output_str_pln = ""
    try:
        flask_logger.info(f"Chamando PLN: python {PLN_PROCESSOR_SCRIPT_PATH} '{pergunta_usuario}' com CWD: {CWD_FOR_PLN}")
        process_pln = subprocess.run(
            ['python', PLN_PROCESSOR_SCRIPT_PATH, pergunta_usuario],
            capture_output=True, text=True, check=False, cwd=CWD_FOR_PLN, env=dict(os.environ) # Adicionado env
        )
        output_str_pln = process_pln.stdout if process_pln.stdout.strip() else process_pln.stderr
        flask_logger.debug(f"Saída bruta PLN (stdout): {process_pln.stdout[:500]}...")
        flask_logger.debug(f"Saída bruta PLN (stderr): {process_pln.stderr[:500]}...")
        flask_logger.info(f"Código de saída do PLN: {process_pln.returncode}")

        if not output_str_pln.strip():
            flask_logger.error("PLN não produziu saída (stdout/stderr).")
            return jsonify({"erro": "PLN não produziu saída.", "sparqlQuery": "N/A (Erro no PLN)"}), 500
        
        pln_output_json_obj = json.loads(output_str_pln) # Armazena o objeto JSON

        if "erro" in pln_output_json_obj:
            flask_logger.error(f"Erro estruturado retornado pelo PLN: {pln_output_json_obj['erro']}")
            return jsonify(pln_output_json_obj), 400
        if "template_nome" not in pln_output_json_obj or "mapeamentos" not in pln_output_json_obj:
            flask_logger.error(f"Saída do PLN inesperada: {pln_output_json_obj}")
            return jsonify({"erro": "Saída do PLN inválida ou incompleta.", "sparqlQuery": "N/A"}), 500
    except json.JSONDecodeError as jde:
        flask_logger.error(f"Erro ao decodificar JSON do PLN: {jde}. Saída PLN: {output_str_pln}")
        return jsonify({"erro": "Erro ao decodificar saída do PLN.", "sparqlQuery": " certeza! Abaixo está o arquivo `web_app.py` inteiro com as correções e simplificações discutidas, focando em:

1.  **Substituição correta do placeholder `#SETOR#`** para o `Template_3A.txt` (assumindo que este template sempre usará `LCASE(#SETOR#)`).
2.  **Remoção da lógica de geração e substituição de `#SETOR_REGEX_PATTERN#`** se ela não for mais necessária para o `Template_3A` (se você tiver *outros* templates que a usam, essa parte precisaria ser reavaliada ou mantida condicionalmente).
3.  **Melhoria na formatação da resposta para `SELECT` queries**, para incluir múltiplos campos (como nome da empresa e ticker).

```python
from flask import Flask, request, jsonify, send_from_directory
import subprocess
import json
import os
from rdflib import Graph, Namespace
from rdflib.plugins.sparql import prepareQuery
import logging
import sys
import re
import unicodedata # Removido se normalizar_para_regex_pattern não for mais usada

# Configuração do logging do Flask
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
flask_logger = logging.getLogger('flask.app')

app = Flask(__name__, static_folder='src/main/resources/static')

# --- CONFIGURAÇÕES DE CAMINHO DENTRO DO CONTAINER ---
BASE_APP_DIR = "/app"
PLN_PROCESSOR_SCRIPT_PATH = os.path.join(BASE_APP_DIR, "src", "main", "resources", "pln_processor.py")
CWD_FOR_PLN = os.path.join(BASE_APP_DIR, "src", "main", "resources")
SPARQL_TEMPLATES_DIR = os.path.join(BASE_APP_DIR, "src", "main", "resources", "Templates")
ONTOLOGY_FILE_PATH = os.path.join(BASE_APP_DIR, "ontologiaB3.ttl")

# Carregar a ontologia
graph = Graph()
NS_B3 = Namespace("httpsN/A (Erro no PLN)", "debug_pln_output": output_str_pln}), 500
    except Exception as e_pln:
        flask_logger.error(f"Erro genérico ao executar PLN: {e_pln}", exc_info=True)
        return jsonify({"erro": f"Erro crítico ao executar o processador PLN: {str(e_pln)}", "sparqlQuery": "N/A (Erro no PLN)"}), 500

    template_nome = pln_output_json_obj.get("template_nome")
    mapeamentos = pln_output_json_obj.get("mapeamentos", {})
    flask_logger.info(f"PLN retornou: template='{template_nome}', mapeamentos='{mapeamentos}'")

    sparql_query_string_final = "Consulta SPARQL não pôde ser gerada."
    sparql_query_template_content = "Template SPARQL não carregado."
    try:
        template_filename = f"{template_nome.replace(' ', '_')}.txt" # Ex: "Template_3A.txt"
        template_file_path = os.path.join(SPARQL_TEMPLATES_DIR, template_filename)
        flask_logger.info(f"Tentando carregar template SPARQL de: {template_file_path}")

        if not os.path.exists(template_file_path):
            flask_logger.error(f"Arquivo de template SPARQL não encontrado: {template_file_path}")
            return jsonify({"erro": f"Template SPARQL '{template_filename}' não encontrado.", "sparqlQuery": "N/A"}), 500
        
        with open(template_file_path, 'r', encoding='utf-8') as f_template:
            sparql_query_template_content = f_template.read()
        
        sparql_query_string_final = sparql_query_template_content # Começa com o conteúdo original do template

        for placeholder_key, valor_raw in mapeamentos.items():
            valor_sparql_formatado = None 
            valor_str_raw = str(valor_raw) # Converte o valor bruto para string

            ://dcm.ffclrp.usp.br/lssb/stock-market-ontology#")
NS_STOCK = Namespace("https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#") # Mesmo que NS_B3, pode ser simplificado
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
    except Exception as e:
        flask_logger.error(f"Erro CRÍTICO ao carregar ontologia: {e}. A aplicação pode não funcionar corretamente.", exc_info=True)
else:
    flask_logger.error(f"ARQUIVO DE ONTOLOGIA NÃO ENCONTRADO EM: {ONTOLOGY_FILE_PATH}. As consultas SPARQL falharão.")

# Removida a função normalizar_para_regex_pattern se não for mais usada.
# Se você ainda precisar dela para outros templates, mantenha-a.
# def normalizar_para_regex_pattern(texto_setor_bruto):
    # ... (código anterior) ...

@app.route('/', methods=['GET'])
def index():
    flask_logger.info(f"Tentando servir: {app.static_folder} / index2.html")
    try:
        return send_from_directory(app.static_folder, 'index2.html')
    except Exception as e:
        flask_logger.error(f"Erro ao tentar servir o index2.html: {e}", exc_info=True)
        return "Erro ao carregar a interface principal. Verifique os logs do servidor.", 500

@app.route('/processar_pergunta', methods=['POST'])
def processar_pergunta_completa():
    data = request.get_json()
    if not data or 'pergunta' not in data:
        return jsonify({"erro": "Pergunta não fornecida no corpo JSON", "sparqlQuery": "N/A"}), 400
    
    pergunta_usuario = data['pergunta']
    flask_logger.info(f"Recebida pergunta: '{pergunta_usuario}'")

    pln_output_json = None
    output_str_pln# Lógica de formatação do valor para SPARQL baseada no placeholder
            if placeholder_key == "#DATA#":
                # Assume que valor_str_raw já está no formato "YYYY-MM-DD"
                valor_sparql_formatado = f'"{valor_str_raw}"^^xsd:date'
            elif placeholder_key == "#ENTIDADE_NOME#":
                # Escapa aspas duplas e barras invertidas para strings SPARQL
                valor_escapado = valor_str_raw.replace('\\', '\\\\').replace('"', '\\"')
                valor_sparql_formatado = f'"{valor_escapado}"'
            elif placeholder_key == "#VALOR_DESEJADO#": # Usado para propriedades como precoFechamento, precoAbertura
                # Se não for um URI completo (<...>) ou já prefixado (prefix:localName)
                if ":" not in valor_str_raw and not valor_str_raw.startswith("<"):
                    valor_sparql_formatado = f'b3:{valor_str_raw}' # Adiciona prefixo padrão b3:
                else:
                    valor_sparql_formatado = valor_str_raw # Usa como está
            elif placeholder_key == "#SETOR#": # Usado em Template_3A
                valor_escapado = valor_str_raw.replace('\\', '\\\\').replace('"', '\\"')
                valor_sparql_formatado = f'"{valor_escapado}"' # Formata como string literal
            # Adicione outros elif para placeholders específicos se necessário
            # Ex: elif placeholder_key == "#ALGUM_NUMERO#":
            # valor_sparql_formatado = f'{valor_str_raw}' # Se for um número e não precisa de aspas

            else: # Fallback para placeholders não explicitamente listados acima
                if str(placeholder_key).startswith("#") and str(placeholder_key).endswith("#"):
                    flask_logger.warning(f"Placeholder '{placeholder_key}' não tratado explicitamente. Formatando como string literal SPARQL.")
                    valor_escapado = valor_str_raw.replace('\\', '\\\\').replace('"', '\\"')
                    valor_sparql_formatado = f'"{valor_escapado}"'
                 = ""
    try:
        flask_logger.info(f"Chamando PLN: python {PLN_PROCESSOR_SCRIPT_PATH} '{pergunta_usuario}' com CWD: {CWD_FOR_PLN}")
        process_pln = subprocess.run(
            ['python', PLN_PROCESSOR_SCRIPT_PATH, pergunta_usuario],
            capture_output=True, text=True, check=False, cwd=CWD_FOR_PLN, env=dict(os.environ)
        )
        output_str_pln = process_pln.stdout if process_pln.stdout.strip() else process_pln.stderr
        flask_logger.debug(f"Saída bruta PLN (stdout): {process_pln.stdout[:500]}...")
        flask_logger.debug(f"Saída bruta PLN (stderr): {process_pln.stderr[:500]}...")
        flask_logger.info(f"Código de saída do PLN: {process_pln.returncode}")

        if not output_str_pln.strip():
            flask_logger.error("PLN não produziu saída (stdout/stderr).")
            return jsonify({"erro": "PLN não produziu saída.", "sparqlQuery": "N/A (Erro no PLN)"}), 500
        pln_output_json = json.loads(output_str_pln)
        if "erro" in pln_output_json:
            flask_logger.error(f"Erro estruturado retornado pelo PLN: {pln_output_json['erro']}")
            return jsonify(pln_output_json), 400
        if "template_nome" not in pln_output_json or "mapeamentos" not in pln_output_json:
            flask_logger.error(f"Saída do PLN inesperada: {pln_output_json}")
            return jsonify({"erro": "Saída do PLN inválida ou incompleta.", "sparqlQuery": "N/A"}), 500
    except json.JSONDecodeError as jde:
        flask_logger.error(f"Erro ao decodificar JSON do PLN: {jde}. Saída PLN: {output_str_pln}")
        return jsonify({"erro": "Erro ao decodificar saída do PLN.", "sparqlQuery": "N/A (Erro no PLN)", "debug_pln_output": output_str_pln}), 500
    except Exception as e_pln:
        flask_logger.error(f"Erro genérico ao executar PLN: {e_pln}", exc_info=True)
        return jsonify({"erro": f"Erro crítico ao executar o processador PLN: {str(e_pln)}", "sparqlQuery": "N/A (Erro no PLN)"}), 500

    template_nome = pln_output_json.get("template_nome")
    mapeamentos = pln_output_json.get("mapeamentos", {})
    flask_logger.info(f"PLN retornou: template='{template_nome}', mapeamentos='{mapeamentos}'")

    sparql_query_string_final = "Consulta SPARQL não pôde ser gerada."
    sparql_query_template_content = "Template SPARQL não carregado."
    try:
        template_filename = f"{template_nome.replace(' ', '_')}.txt" # Ex: "Template_3A.txt"
        template_file_path = os.path.join(SPARQL_TEMPLATES_DIR, template_filename)
        flask_logger.info(f"Tentando carregar template SPARQL de: {template_file_path}")
        if not os.path.exists(template_file_path):
            flask_logger.error(f"Arquivo de template SPARQL não encontrado: {template_file_path}")
            return jsonify({"erro": f"Template SPARQL '{template_filename}' não encontrado.", "sparqlQuery": "N/A"}), 500
        with open(template_file_path, 'r', encoding='utf-8') as f_template:
else:
                    # Se não for um placeholder reconhecido (não começa/termina com #), ignora.
                    flask_logger.debug(f"Item '{placeholder_key}' nos mapeamentos não é um placeholder padrão, ignorando substituição.")
                    continue # Pula para o próximo item em mapeamentos

            # Realiza a substituição se o valor formatado foi definido e o placeholder existe na query atual
            if valor_sparql_formatado is not None and str(placeholder_key) in sparql_query_string_final:
                flask_logger.info(f"Substituindo '{placeholder_key}' por '{valor_sparql_formatado}' na query.")
                sparql_query_string_final = sparql_query_string_final.replace(str(placeholder_key), valor_sparql_formatado)
            elif str(placeholder_key) in sparql_query_template_content: # Verifica no template original
                 flask_logger.warning(f"Placeholder '{placeholder_key}' estava no template original, mas não foi substituído (valor_sparql_formatado is None ou placeholder não encontrado na string atual da query).")
        
        flask_logger.info(f"Consulta SPARQL final (após todas as substituições):\n{sparql_query_string_final}")

        # Checagem final por placeholders não substituídos (opcional mas útil)
        if "#" in sparql_query_string_final:
             # Tenta encontrar placeholders específicos restantes
            placeholders_restantes = [word for word in sparql_query_string_final.split() if word.startswith("#") and word.endswith("#")]
            if placeholders_restantes:
                flask_logger.warning(f"AVISO: Query final AINDA CONTÉM placeholders não substituídos: {', '.join(placeholders_restantes)}. Query: {sparql_query_string_final}")

    except Exception as e_template:
        flask_logger.error(f"Erro ao processar template SPARQL: {e_template}", exc_info=True)
        return jsonify({"erro": f"Erro ao gerar consulta SPARQL: {str(e_template)}", "sparqlQuery": sparql_query_template_content}), 500

    resposta_formatada_final = "Não foi possível executar a consulta ou não houve resultados."
    try:
        if not graph or len(graph) == 0:
            flask_logger.error("Ontologia não carregada ou vazia.")
            return jsonify({"erro": "Falha ao carregar a ontologia base.", "sparqlQuery": sparql_query_string_final}), 500
        
        query_obj = prepareQuery(sparql_query_string_final, initNs=INIT_NS)
        flask_logger.info("Executando consulta SPARQL principal...")
        qres = graph.query(query_obj)
        
        resultados_para_json = [] # Lista para armazenar resultados formatados
        if qres.type == 'SELECT':
            all_rows_from_select = list(qres) 
            flask_logger.info(f"--- {template_nome}: Número de linhas/resultados SELECT encontrados: {len(all_rows_from_select)} ---")

            for row_data in all_rows_from_select:
                # Para Template_3A e outros que selecionam ?valor e ?empresaLabel (ou similares)
                ticker = str(row_data.valor) if hasattr(row_data, 'valor') and row_data.valor is not None else "N/A"
                nome_empresa = str(row_data.empresaLabel) if hasattr(row_data, 'empresaLabel') and row_data.empresaLabel is not None else "N/A"
                
                # Verifica se pelo menos um dos campos principais tem valor
                # Evita adicionar entradas totalmente "N/A" se não for o objetivo
                if ticker != "N/A" or nome            sparql_query_template_content = f_template.read()
        
        sparql_query_string_final = sparql_query_template_content # Inicia com o conteúdo original do template

        for placeholder_key, valor_raw in mapeamentos.items():
            valor_sparql_formatado = None # Redefinir para None a cada iteração
            valor_str_raw = str(valor_raw) # Garantir que o valor é uma string

            # Verifica se o placeholder realmente existe no template atual antes de formatar
            if str(placeholder_key) not in sparql_query_string_final:
                flask_logger.debug(f"Placeholder '{placeholder_key}' do PLN não encontrado no template atual '{template_nome}'. Ignorando.")
                continue

            if placeholder_key == "#DATA#":
                # Assume que valor_str_raw já está no formato "YYYY-MM-DD"
                valor_sparql_formatado = f'"{valor_str_raw}"^^xsd:date'
            elif placeholder_key == "#ENTIDADE_NOME#": # Usado por Template_1A, Template_2A
                valor_escapado = valor_str_raw.replace('\\', '\\\\').replace('"', '\\"')
                valor_sparql_formatado = f'"{valor_escapado}"'
            elif placeholder_key == "#VALOR_DESEJADO#": # Usado por Template_1A, Template_1B (para propriedades como b3:precoFechamento)
                if ":" not in valor_str_raw and not valor_str_raw.startswith("<"):
                    # Assume que é um nome local e precisa do prefixo b3:
                    valor_sparql_formatado = f'b3:{valor_str_raw}' # Ex: b3:precoAbertura
                else:
                    # Assume que já é um URI completo ou uma propriedade prefixada
                    valor_sparql_formatado = valor_str_raw
            elif placeholder_key == "#SETOR#": # Usado por Template_3A
                valor_escapado = valor_str_raw.replace('\\', '\\\\').replace('"', '\\"')
                valor_sparql_formatado = f'"{valor_escapado}"' # Ex: "Energia Elétrica"
            
            # Adicione aqui outros placeholders específicos se necessário
            # elif placeholder_key == "#OUTRO_PLACEHOLDER#":
            #     valor_sparql_formatado = ...
            
            else: # Fallback para placeholders não explicitamente listados acima
                # Se o PLN fornecer um placeholder que não tem formatação especial,
                # mas ainda precisa ser substituído (ex: um valor numérico que não precisa de ^^xsd:type)
                # Por segurança, vamos tratá-lo como string literal se não for um dos conhecidos.
                # Se você tiver placeholders para números ou booleanos, adicione casos específicos.
                if str(placeholder_key).startswith("#") and str(placeholder_key).endswith("#"):
                    flask_logger.warning(f"Placeholder '{placeholder_key}' não possui formatação explícita. Tratando como string literal SPARQL.")
                    valor_escapado = valor_str_raw.replace('\\', '\\\\').replace('"', '\\"')
                    valor_sparql_formatado = f'"{valor_escapado}"'
                else:
                    # Não é um formato de placeholder esperado, provavelmente um metadado do PLN
                    flask_logger.debug(f"Item '{placeholder_key}' em mapeamentos não é um placeholder padrão, ignorando.")
                    continue

            if valor_sparql_formatado is not None:
                flask_empresa != "N/A":
                    entry = {}
                    if hasattr(row_data, 'empresaLabel'): # Se a query pedir ?empresaLabel
                        entry["empresa"] = nome_empresa
                    if hasattr(row_data, 'valor'): # Se a query pedir ?valor (ticker, preco, etc.)
                        entry["ticker_ou_valor"] = ticker 
                    
                    # Adicionar outros campos se a query os retornar
                    # Ex: if hasattr(row_data, 'dataNegociacao'): entry["data"] = str(row_data.dataNegociacao)

                    if entry: # Só adiciona se o dicionário não estiver vazio
                        resultados_para_json.append(entry)
                else: # Caso onde ambos são N/A, pode logar se for inesperado
                    flask_logger.debug(f"Linha do resultado ignorada pois ticker e nome da empresa são N/A: {row_data}")


            if not resultados_para_json:
                resposta_formatada_final = "Nenhum resultado encontrado."
            else:
                resposta_formatada_final = json.dumps(resultados_para_json) # Retorna lista de dicionários como JSON
        
        elif qres.type == 'ASK':
            ask_result = bool(next(iter(qres), False)) # Forma segura de obter o booleano
            resposta_formatada_final = json.dumps({"resultado_ask": ask_result})
        
        elif qres.type == 'CONSTRUCT' or qres.type == 'DESCRIBE':
            # Serializa para um formato mais legível ou padronizado, como JSON-LD ou N-Triples
            # Turtle pode ser muito verboso para respostas diretas de API, mas é uma opção
            try:
                # Tenta serializar para JSON-LD se possível, senão fallback
                context = {"@vocab": str(NS_B3)} # Exemplo simples de contexto
                resposta_formatada_final = qres.serialize(format='json-ld', context=context, indent=2)
            except: # Fallback para turtle ou ntriples
                resposta_formatada_final = qres.serialize(format='turtle')

            if not resposta_formatada_final.strip(): # Verifica se a string serializada está vazia
                resposta_formatada_final = "Nenhum resultado para CONSTRUCT/DESCRIBE."
        else:
            resposta_formatada_final = f"Tipo de consulta não suportado para formatação: {qres.type}"

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
    # Para debug local, roda em uma porta diferente para não conflitar com o Java se estiver rodando junto
    local_port = int(os.environ.get("PORT", 5001)) 
    flask_logger.info(f"Iniciando servidor Flask de desenvolvimento em http://0.0.0.0:{local_port}")
    # 'debug=True' é bom para desenvolvimento local, mas deve ser False em produção (Render geralmente gerencia isso)
    # 'use_reloader=False' pode ser útil para evitar problemas de recarregamento duplo com alguns setups de logging/recursos
    app.run(host_logger.info(f"Substituindo '{placeholder_key}' por '{valor_sparql_formatado}' na query.")
                sparql_query_string_final = sparql_query_string_final.replace(str(placeholder_key), valor_sparql_formatado)
            # Não precisa de um 'else' aqui, pois o 'continue' no início do loop já cuida de placeholders não encontrados.

        flask_logger.info(f"Consulta SPARQL final gerada: \n{sparql_query_string_final}")
        
        # Checagem final por placeholders não substituídos (bom para debug)
        placeholders_restantes = re.findall(r'(#\w+#)', sparql_query_string_final)
        if placeholders_restantes:
            flask_logger.warning(f"AVISO: Query final AINDA CONTÉM placeholders não substituídos: {', '.join(placeholders_restantes)}. Query:\n{sparql_query_string_final}")

    except Exception as e_template:
        flask_logger.error(f"Erro ao processar template SPARQL: {e_template}", exc_info=True)
        return jsonify({"erro": f"Erro ao gerar consulta SPARQL: {str(e_template)}", "sparqlQuery": sparql_query_template_content}), 500

    resposta_formatada_final = "Não foi possível executar a consulta ou não houve resultados."
    try:
        if not graph or len(graph) == 0:
            flask_logger.error("Ontologia não carregada ou vazia.")
            return jsonify({"erro": "Falha ao carregar a ontologia base.", "sparqlQuery": sparql_query_string_final}), 500
        
        query_obj = prepareQuery(sparql_query_string_final, initNs=INIT_NS)
        flask_logger.info("Executando consulta SPARQL principal...")
        qres = graph.query(query_obj)
        
        resultados_json_list = [] # Lista para armazenar os resultados formatados como dicts
        
        if qres.type == 'SELECT':
            all_rows_from_select = list(qres)
            flask_logger.info(f"--- {template_nome}: Número de linhas/resultados SELECT encontrados: {len(all_rows_from_select)} ---")

            for row_data in all_rows_from_select:
                row_dict = {}
                # qres.vars contém os nomes das variáveis na SELECT (e.g., ['valor', 'empresaLabel'])
                # No entanto, qres.vars pode estar vazio se o gerador foi consumido por list(qres)
                # É mais seguro usar row_data.labels que contém os nomes das variáveis para aquela linha.
                if hasattr(row_data, 'labels'):
                    for var_name in row_data.labels:
                        value = row_data[var_name]
                        row_dict[str(var_name)] = str(value) if value is not None else None
                else: # Fallback se .labels não estiver disponível (menos provável com rdflib atual)
                    # Tenta acessar por índice se for uma tupla simples (improvável com prepareQuery)
                    # Esta parte pode precisar de ajuste se .labels não funcionar
                    flask_logger.warning("row_data não tem 'labels', tentando acesso por índice (pode ser impreciso).")
                    for i, val_item in enumerate(row_data):
                         row_dict[f"var{i+1}"] = str(val_item) if val_item is not None else None
                
                resultados_json_list.append(row_dict)

            if not resultados_json_list:
                resposta_formatada_final = "Nenhum resultado encontrado." # Mantido como string para o frontend
            else:
                # Retorna uma lista de dicionários, cada dicionário representa uma linha
                resposta_formatada_final = json.dumps(resultados_json_list='0.0.0.0', port=local_port, debug=True, use_reloader=True)