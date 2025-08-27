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
        print(f"AVISO: Arquivo {nome_arquivo} não encontrado em {caminho_completo}.")
        return {}

empresa_map = carregar_arquivo_json('Named_entity_dictionary.json')
setor_map = carregar_arquivo_json('sector_map.json')
index_map = carregar_arquivo_json('index_map.json')

reference_templates = {}
try:
    with open(os.path.join(SCRIPT_DIR, 'Reference_questions.txt'), 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and ';' in line and not line.startswith('#'):
                template_id, question_text = [part.strip() for part in line.split(';', 1)]
                if template_id not in reference_templates:
                    reference_templates[template_id] = []
                reference_templates[template_id].append(question_text)
except FileNotFoundError:
    print("AVISO: Arquivo Reference_questions.txt não encontrado.")
    reference_templates = {}

ref_questions_flat = [q for questions in reference_templates.values() for q in questions]
ref_ids_flat = [tid for tid, questions in reference_templates.items() for _ in questions]

if ref_questions_flat:
    vectorizer = TfidfVectorizer()
    tfidf_matrix_ref = vectorizer.fit_transform(ref_questions_flat)
else:
    vectorizer, tfidf_matrix_ref = None, None

# --- FUNÇÕES AUXILIARES DE PROCESSAMENTO DE TEXTO ---

def remover_acentos(texto):
    nfkd_form = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def extrair_todas_entidades(pergunta_lower):
    """
    Pipeline de extração de entidades com ordem de prioridade para minimizar ambiguidades.
    VERSÃO CORRIGIDA.
    """
    entidades = {}
    texto_restante = ' ' + pergunta_lower + ' '
    
    # 1. Datas
    match_data = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', texto_restante)
    if match_data:
        dia, mes, ano = match_data.groups()
        entidades['data'] = f"{ano}-{mes.zfill(2)}-{dia.zfill(2)}"
        texto_restante = texto_restante.replace(match_data.group(0), " ")

    # 2. Limites numéricos
    limit_match = re.search(r'\b(as|os)?\s*(\d+|cinco|tres|três|duas|dois|quatro)\s+(acoes|ações|papeis|papéis)\b', texto_restante, re.IGNORECASE)
    num_map = {'cinco': '5', 'quatro': '4', 'tres': '3', 'três': '3', 'duas': '2', 'dois': '2'}
    if limit_match:
        num_str = limit_match.group(2).lower()
        entidades['limite'] = num_map.get(num_str, num_str)
        texto_restante = texto_restante.replace(limit_match.group(0), " ")
    elif re.search(r'\btop\s*(\d+)\b', texto_restante, re.IGNORECASE):
        limit_match = re.search(r'\btop\s*(\d+)\b', texto_restante, re.IGNORECASE)
        entidades['limite'] = limit_match.group(1)
    else:
        entidades['limite'] = '1'

    # 3. Métricas
    mapa_ranking = {
        'variacao_perc': ['maior percentual de alta', 'maior alta percentual', 'maior percentual de baixa', 'maior baixa percentual', 'menor variacao percentual', 'menor variação percentual'],
        'variacao_abs': ['menor variacao absoluta', 'menor variação absoluta', 'maior variacao absoluta', 'maior variação absoluta'],
    }
    mapa_metricas = {
        'variacao_perc': ['variacao percentual', 'variação percentual'],
        'variacao_abs': ['variacao absoluta', 'variação absoluta', 'variacao intradiaria absoluta', 'variação intradiária absoluta'],
        'intervalo_perc': ['intervalo intradiario percentual', 'intervalo intradiário percentual'],
        'preco_medio': ['preco medio', 'preço médio', 'valor medio', 'valor médio'],
        'preco_fechamento': ['preco de fechamento', 'fechamento'],
        'preco_abertura': ['preco de abertura', 'abertura'],
        'preco_maximo': ['preco maximo', 'preço máximo'],
        'preco_minimo': ['preco minimo', 'preço mínimo'],
        'codigo_negociacao': ['codigo de negociacao', 'ticker', 'simbolo'],
        'volume': ['volume', 'volume negociado'],
        'quantidade': ['quantidade de acoes', 'quantidade de ações'],
    }
    
    texto_sem_acento = remover_acentos(texto_restante)
    
    # Extrai Ranking primeiro
    for chave, sinonimos in mapa_ranking.items():
        for s in sorted(sinonimos, key=len, reverse=True):
            if re.search(r'\b' + remover_acentos(s) + r'\b', texto_sem_acento):
                entidades['ranking_calculation'] = chave
                texto_sem_acento = re.sub(r'\b' + remover_acentos(s) + r'\b', ' ', texto_sem_acento, flags=re.IGNORECASE)
                break
        if 'ranking_calculation' in entidades: break
    
    # Extrai Métrica principal (cálculo ou valor)
    for chave, sinonimos in mapa_metricas.items():
        for s in sorted(sinonimos, key=len, reverse=True):
            if re.search(r'\b' + remover_acentos(s) + r'\b', texto_sem_acento):
                if chave in ['variacao_abs', 'intervalo_perc', 'variacao_perc']:
                    if 'calculo' not in entidades:
                        entidades['calculo'] = chave
                else:
                    if 'valor_desejado' not in entidades:
                        entidades['valor_desejado'] = 'metrica.' + chave
                texto_sem_acento = re.sub(r'\b' + remover_acentos(s) + r'\b', ' ', texto_sem_acento, flags=re.IGNORECASE)
                # Não usamos break aqui para permitir que outras métricas sejam encontradas se necessário (ex: complex ranking)
    
    if 'ranking_calculation' in entidades and 'calculo' not in entidades and 'valor_desejado' not in entidades:
        entidades['valor_desejado'] = 'metrica.' + entidades['ranking_calculation']

    # 4. Entidades principais
    ticker_match = re.search(r'\b([A-Z]{4}[0-9]{1,2})\b', texto_restante.upper())
    if ticker_match:
        entidades['entidade_nome'] = ticker_match.group(1); entidades['tipo_entidade'] = 'ticker'
    
    for key in sorted(index_map.keys(), key=len, reverse=True):
        if re.search(r'\b(do|da|de|entre as|do indice|acoes do)?\s*' + re.escape(key.lower()) + r'\b', remover_acentos(texto_restante)):
            entidades['nome_indice'] = key; break
            
    if not 'entidade_nome' in entidades:
        for key in sorted(empresa_map.keys(), key=len, reverse=True):
            if re.search(r'\b' + re.escape(key.lower()) + r'\b', remover_acentos(texto_restante)):
                entidades['entidade_nome'] = key; entidades['tipo_entidade'] = 'nome'; break
    
    for key in sorted(setor_map.keys(), key=len, reverse=True):
        if re.search(r'\b' + re.escape(remover_acentos(key.lower())) + r'\b', remover_acentos(texto_restante)):
            entidades['nome_setor'] = setor_map[key]; break

    # 5. Filtros secundários
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
    pergunta_lower = data.get('question', '').lower()
    if not pergunta_lower.strip(): return jsonify({"error": "A pergunta não pode ser vazia."}), 400
        
    entidades = extrair_todas_entidades(pergunta_lower)
    template_id_final = None

    # Flags
    has_ranking = 'ranking_calculation' in entidades
    has_calculo = 'calculo' in entidades
    has_entidade_nome = 'entidade_nome' in entidades
    has_setor = 'nome_setor' in entidades
    has_indice = 'nome_indice' in entidades
    has_valor_desejado = 'valor_desejado' in entidades
    is_complex_ranking = has_ranking and has_valor_desejado and entidades.get('valor_desejado') != 'metrica.' + entidades.get('ranking_calculation')
    pergunta_sem_acento = remover_acentos(pergunta_lower)
    
    # ==========================================================
    # LÓGICA DE DECISÃO HEURÍSTICA FINAL
    # ==========================================================
    
    is_ask_question = (pergunta_lower.strip().startswith(('a ', 'o '))) and has_entidade_nome and has_setor
    if is_ask_question:
        template_id_final = 'Template_3D'
    elif is_complex_ranking:
        template_id_final = 'Template_6B' if has_setor or has_indice else 'Template_6A'
    elif has_ranking:
        template_id_final = 'Template_5B' if has_setor or has_indice else 'Template_5A'
    else:
        if ('setor de atuacao' in pergunta_sem_acento) and has_entidade_nome:
            template_id_final = 'Template_2B'
        elif ('ticker' in pergunta_sem_acento or 'codigo de negociacao' in pergunta_sem_acento or 'simbolo' in pergunta_sem_acento) and has_entidade_nome:
            template_id_final = 'Template_2A'
        elif has_setor or has_indice:
            if 'empresas' in pergunta_lower: template_id_final = 'Template_3B'
            elif has_valor_desejado: template_id_final = 'Template_4'
            else: template_id_final = 'Template_3A'
        elif has_entidade_nome:
            if has_calculo: template_id_final = 'Template_1D'
            elif 'regex_pattern' in entidades: template_id_final = 'Template_1C'
            elif has_valor_desejado:
                template_id_final = 'Template_1B' if entidades.get('tipo_entidade') == 'ticker' else 'Template_1A'
    
    # Fallback
    if not template_id_final and vectorizer:
        tfidf_usuario = vectorizer.transform([pergunta_lower])
        similaridades = cosine_similarity(tfidf_usuario, tfidf_matrix_ref).flatten()
        if similaridades.any() and similaridades.max() > 0.1:
            template_id_final = ref_ids_flat[similaridades.argmax()]

    if not template_id_final: return jsonify({"error": "Não foi possível identificar um template para a pergunta."}), 404
    
    # Ajuste final
    if template_id_final in ['Template_5A', 'Template_5B'] and 'ranking_calculation' in entidades and 'calculo' not in entidades:
        entidades['calculo'] = entidades['ranking_calculation']

    entidades_maiusculas = {k.upper(): v for k, v in entidades.items()}
    return jsonify({"templateId": template_id_final, "entities": entidades_maiusculas})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)