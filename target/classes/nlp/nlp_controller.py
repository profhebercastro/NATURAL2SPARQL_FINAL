import json
import re
import os
import unicodedata
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- CARREGAMENTO DOS ARTEFATOS DE CONHECIMENTO ---

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
def carregar_arquivo_json(nome_arquivo):
    caminho_completo = os.path.join(SCRIPT_DIR, nome_arquivo)
    try:
        with open(caminho_completo, 'r', encoding='utf-8') as f: return json.load(f)
    except FileNotFoundError:
        print(f"AVISO: Arquivo {nome_arquivo} não encontrado.")
        return {}

empresa_map = carregar_arquivo_json('Named_entity_dictionary.json')
setor_map = carregar_arquivo_json('sector_map.json')
index_map = carregar_arquivo_json('index_map.json')
reference_templates = {}
try:
    with open(os.path.join(SCRIPT_DIR, 'Reference_questions.txt'), 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() and ';' in line and not line.strip().startswith('#'):
                parts = line.split(';', 1)
                if len(parts) == 2:
                    template_id, question_text = parts
                    if template_id.strip() not in reference_templates:
                        reference_templates[template_id.strip()] = []
                    reference_templates[template_id.strip()].append(question_text.strip())
except FileNotFoundError:
    reference_templates = {}

# Prepara os dados para o cálculo de similaridade
ref_questions_flat = []
ref_ids_flat = []
for template_id, questions in reference_templates.items():
    for q in questions:
        ref_questions_flat.append(q)
        ref_ids_flat.append(template_id)

if ref_questions_flat:
    vectorizer = TfidfVectorizer()
    tfidf_matrix_ref = vectorizer.fit_transform(ref_questions_flat)
else:
    vectorizer = None
    tfidf_matrix_ref = None

# --- FUNÇÕES AUXILIARES DE PROCESSAMENTO DE TEXTO ---

def remover_acentos(texto):
    nfkd_form = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def extrair_todas_entidades(pergunta_lower):
    """
    Pipeline de extração de entidades com ordem de prioridade para minimizar ambiguidades.
    """
    entidades = {}
    texto_restante = ' ' + pergunta_lower + ' '
    
    # 1. Extrai datas
    match_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', texto_restante)
    if match_data:
        dia, mes, ano = match_data.groups()
        entidades['data'] = f"{ano}-{mes}-{dia}"
        texto_restante = texto_restante.replace(match_data.group(0), " ")

    # 2. Extrai limites numéricos (ex: "as 5 ações", "top 2")
    limit_match = re.search(r'\b(as|os)?\s*(\d+|cinco|tres|três|duas|dois)\s+(acoes|ações|papeis|papéis)\b', texto_restante, flags=re.IGNORECASE)
    if limit_match:
        num_str = limit_match.group(2)
        if num_str.lower() == 'cinco': entidades['limite'] = '5'
        elif num_str.lower() in ['tres', 'três']: entidades['limite'] = '3'
        elif num_str.lower() in ['duas', 'dois']: entidades['limite'] = '2'
        else: entidades['limite'] = num_str
        texto_restante = texto_restante.replace(limit_match.group(0), " ")
    elif re.search(r'\btop\s*(\d+)\b', texto_restante, flags=re.IGNORECASE):
        limit_match = re.search(r'\btop\s*(\d+)\b', texto_restante, flags=re.IGNORECASE)
        entidades['limite'] = limit_match.group(1)
    else:
        entidades['limite'] = '1'

    # 3. Extrai métricas de ranking e de resultado
    mapa_ranking = {
        'variacao_perc': ['maior percentual de alta', 'maior alta percentual', 'maior percentual de baixa', 'maior baixa percentual', 'maiores altas', 'maiores baixas', 'mais subiu percentualmente'],
        'variacao_abs_abs': ['menor variacao', 'menor variação', 'menor variacao absoluta'],
    }
    mapa_metricas = {
        'variacao_perc': ['variacao percentual', 'percentual de alta', 'percentual de baixa'],
        'variacao_abs': ['variacao absoluta', 'variacao intradiaria absoluta', 'variou em reais', 'variação em reais'],
        'intervalo_abs': ['intervalo intradiario absoluto', 'intervalo absoluto'],
        'intervalo_perc': ['intervalo intradiario percentual', 'intervalo percentual'],
        'preco_maximo': ['preco maximo', 'preço máximo', 'valor maximo', 'valor máximo'],
        'preco_minimo': ['preco minimo', 'preço mínimo', 'valor minimo', 'valor mínimo'],
        'preco_fechamento': ['preco de fechamento', 'fechamento', 'cotação de fechamento', 'fechou'],
        'preco_abertura': ['preco de abertura', 'abertura'],
        'preco_medio': ['preco medio', 'preço médio', 'valor medio', 'valor médio'],
        'quantidade': ['quantidade', 'total de negocios', 'quantidade de negocios'],
        'volume': ['volume', 'volume negociado', 'volume total'],
    }
    
    texto_sem_acento = remover_acentos(texto_restante)
    
    for chave, sinonimos in mapa_ranking.items():
        for s in sorted(sinonimos, key=len, reverse=True):
            if re.search(r'\b' + remover_acentos(s) + r'\b', texto_sem_acento):
                entidades['ranking_calculation'] = chave
                texto_sem_acento = re.sub(r'\b' + remover_acentos(s) + r'\b', ' ', texto_sem_acento, flags=re.IGNORECASE)
                break
        if 'ranking_calculation' in entidades:
            break

    for chave, sinonimos in mapa_metricas.items():
        for s in sorted(sinonimos, key=len, reverse=True):
            if re.search(r'\b' + remover_acentos(s) + r'\b', texto_sem_acento):
                if chave.startswith('variacao_') or chave.startswith('intervalo_'):
                    entidades['calculo'] = chave
                else:
                    entidades['valor_desejado'] = 'metrica.' + chave
                break
        if 'calculo' in entidades or 'valor_desejado' in entidades:
            break

    if 'ranking_calculation' in entidades and 'calculo' not in entidades and 'valor_desejado' not in entidades:
        entidades['calculo'] = entidades['ranking_calculation']
    if 'calculo' in entidades and 'ranking_calculation' not in entidades:
        entidades['ranking_calculation'] = entidades['calculo']

    # 4. Extrai entidades principais (Ticker > Índice > Setor > Nome de Empresa)
    entidade_principal_encontrada = False
    
    ticker_match = re.search(r'\b([A-Z]{4}[0-9]{1,2})\b', texto_restante.upper())
    if ticker_match:
        entidades['entidade_nome'] = ticker_match.group(1)
        entidades['tipo_entidade'] = 'ticker'
        entidade_principal_encontrada = True

    if not entidade_principal_encontrada:
        for key in sorted(index_map.keys(), key=len, reverse=True):
            if re.search(r'\b(do|da|de|entre as|do indice|acoes do)?\s*' + re.escape(key.lower()) + r'\b', remover_acentos(texto_restante)):
                entidades['lista_tickers'] = index_map[key]
                entidade_principal_encontrada = True
                break

    if not entidade_principal_encontrada:
        for key in sorted(setor_map.keys(), key=len, reverse=True):
            if re.search(r'\b' + re.escape(remover_acentos(key.lower())) + r'\b', remover_acentos(texto_restante)):
                entidades['nome_setor'] = setor_map[key]
                entidade_principal_encontrada = True
                break
    
    if not entidade_principal_encontrada:
        for key in sorted(empresa_map.keys(), key=len, reverse=True):
            if re.search(r'\b' + re.escape(key.lower()) + r'\b', remover_acentos(texto_restante)):
                entidades['entidade_nome'] = key
                entidades['tipo_entidade'] = 'nome'
                break

    # 5. Extrai filtros secundários (Tipo de ação, Ordem)
    pergunta_sem_acento_original = remover_acentos(pergunta_lower)
    if "ordinaria" in pergunta_sem_acento_original: entidades["regex_pattern"] = "3$"
    elif "preferencial" in pergunta_sem_acento_original: entidades["regex_pattern"] = "[456]$"
    elif "unit" in pergunta_sem_acento_original: entidades["regex_pattern"] = "11$"
    
    if "baixa" in pergunta_sem_acento_original or "menor" in pergunta_sem_acento_original: entidades['ordem'] = "ASC"
    else: entidades['ordem'] = "DESC"

    return entidades

# --- API FLASK ---
app = Flask(__name__)
@app.route('/process_question', methods=['POST'])
def process_question():
    data = request.get_json()
    if not data or 'question' not in data:
        return jsonify({"error": "Payload inválido."}), 400
    pergunta_lower = data.get('question', '').lower()
    if not pergunta_lower.strip(): 
        return jsonify({"error": "A pergunta não pode ser vazia."}), 400
        
    entidades = extrair_todas_entidades(pergunta_lower)
    
    template_id_final = None

    # Verifica a presença das entidades chave para facilitar a lógica
    has_ranking = 'ranking_calculation' in entidades
    has_calculo = 'calculo' in entidades
    has_entidade_especifica = 'entidade_nome' in entidades
    has_setor_ou_indice = 'nome_setor' in entidades or 'lista_tickers' in entidades
    # CORREÇÃO: A condição para ser uma consulta complexa é mais estrita.
    # Só é complexa se a métrica de ranking for DIFERENTE da métrica de resultado.
    is_complex_ranking = has_ranking and (has_calculo or 'valor_desejado' in entidades) and entidades.get('calculo') != entidades.get('ranking_calculation')
    
    # ==========================================================
    # LÓGICA DE DECISÃO HEURÍSTICA REFINADA E REORDENADA
    # ==========================================================

    # Regra 1: Prioridade Máxima para cálculo em entidade específica (não é ranking).
    if has_calculo and has_entidade_especifica and not has_ranking:
        template_id_final = 'Template_6A'
    
    # Regra 2: Pergunta Complexa (Ranking com métrica de resultado diferente).
    elif is_complex_ranking:
        if has_setor_ou_indice:
            template_id_final = 'Template_8B'
        else:
            template_id_final = 'Template_8A'
    
    # Regra 3: Pergunta de Ranking Simples (lista TOP N ou busca de 1).
    elif has_ranking:
        if has_setor_ou_indice:
            template_id_final = 'Template_7B'
        else:
            template_id_final = 'Template_7A'

    # Regra 4: Outras perguntas com entidade específica (buscas pontuais de valor).
    elif has_entidade_especifica:
        if entidades.get('tipo_entidade') == 'ticker':
            template_id_final = 'Template_1B'
        else: # tipo_entidade == 'nome'
            if 'regex_pattern' in entidades: template_id_final = 'Template_5A'
            elif 'total' in pergunta_lower or 'some' in pergunta_lower: template_id_final = 'Template_4A'
            elif 'valor_desejado' in entidades: template_id_final = 'Template_1A'
            else: template_id_final = 'Template_2A'

    # Regra 5: Outras perguntas sobre setor ou índice.
    elif has_setor_ou_indice:
        if 'valor_desejado' in entidades: template_id_final = 'Template_4A'
        else: template_id_final = 'Template_3A'
    
    # Regra 6: Fallback final para similaridade de texto.
    if not template_id_final:
        if tfidf_matrix_ref is not None and len(ref_questions_flat) > 0:
            tfidf_usuario = vectorizer.transform([pergunta_lower])
            similaridades = cosine_similarity(tfidf_usuario, tfidf_matrix_ref).flatten()
            if similaridades.any():
                template_id_final = ref_ids_flat[similaridades.argmax()]
            else:
                return jsonify({"error": "Não foi possível encontrar similaridade."}), 404
        else:
            return jsonify({"error": "Nenhum template de referência carregado."}), 500

    if not template_id_final:
        return jsonify({"error": "Não foi possível identificar um template para a pergunta."}), 404

    entidades_maiusculas = {k.upper(): v for k, v in entidades.items()}
    return jsonify({"templateId": template_id_final, "entities": entidades_maiusculas})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)