loimport json
import re
import os
import unicodedata
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- CARREGAMENTO ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
def carregar_arquivo_json(nome_arquivo):
    caminho_completo = os.path.join(SCRIPT_DIR, nome_arquivo)
    try:
        with open(caminho_completo, 'r', encoding='utf-8') as f: return json.load(f)
    except FileNotFoundError: return {}

empresa_map = carregar_arquivo_json('Named_entity_dictionary.json')
setor_map = carregar_arquivo_json('setor_map.json')

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

# --- FUNÇÕES AUXILIARES ---
def remover_acentos(texto):
    nfkd_form = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def extrair_todas_entidades(pergunta_lower):
    entidades = {}
    texto_restante = ' ' + pergunta_lower + ' '
    texto_sem_acento = remover_acentos(texto_restante)
    
    # Etapa 1: Extrair Data
    match_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', texto_restante)
    if match_data:
        dia, mes, ano = match_data.groups()
        entidades['data'] = f"{ano}-{mes}-{dia}"
        texto_restante = texto_restante.replace(match_data.group(0), " ")
        texto_sem_acento = texto_sem_acento.replace(match_data.group(0), " ")

    # Etapa 2: Extrair intenções de cálculo
    mapa_ranking = {
        'variacao_perc': ['maior percentual de alta', 'maior alta percentual', 'maior percentual de baixa', 'maior baixa percentual'],
        'variacao_abs_abs': ['menor variacao', 'menor variação', 'menor variacao absoluta'],
    }
    mapa_metricas = {
        'variacao_perc': ['variacao percentual', 'percentual de alta', 'percentual de baixa'],
        'variacao_abs': ['variacao absoluta', 'variacao intradiaria absoluta'],
        'intervalo_abs': ['intervalo intradiario absoluto', 'intervalo absoluto'],
        'intervalo_perc': ['intervalo intradiario percentual', 'intervalo percentual'],
        'preco_maximo': ['preco maximo', 'preço máximo'],
        'preco_minimo': ['preco minimo', 'preço mínimo'],
        'preco_fechamento': ['preco de fechamento', 'fechamento'],
        'preco_abertura': ['preco de abertura', 'abertura'],
        'preco_medio': ['preco medio', 'preço médio'],
        'quantidade': ['quantidade', 'total de negocios'],
        'volume': ['volume'],
    }

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

    # Etapa 3: Tentar extrair SETOR
    setor_encontrado = False
    for key in sorted(setor_map.keys(), key=len, reverse=True):
        if re.search(r'\b' + re.escape(remover_acentos(key.lower())) + r'\b', texto_sem_acento):
            entidades['nome_setor'] = setor_map[key]
            texto_restante = re.sub(r'\b' + re.escape(key.lower()) + r'\b', ' ', texto_restante, flags=re.IGNORECASE)
            setor_encontrado = True
            break
            
    # Etapa 4: Se não for setor, extrair Ticker ou Nome de Empresa
    if not setor_encontrado:
        ticker_match = re.search(r'\b([A-Z0-9]{5,6})\b', texto_restante.upper())
        if ticker_match:
            entidades['entidade_nome'] = ticker_match.group(1)
        else:
            for key in sorted(empresa_map.keys(), key=len, reverse=True):
                if re.search(r'\b' + re.escape(key.lower()) + r'\b', texto_restante):
                    entidades['entidade_nome'] = key
                    break
    
    # Etapa 5: Extrair parâmetros restantes
    pergunta_sem_acento_original = remover_acentos(pergunta_lower)
    if "ordinaria" in pergunta_sem_acento_original: entidades["regex_pattern"] = "3$"
    elif "preferencial" in pergunta_sem_acento_original: entidades["regex_pattern"] = "[456]$"
    elif "unit" in pergunta_sem_acento_original: entidades["regex_pattern"] = "11$"
    
    entidades['ordem'] = "DESC"
    if "baixa" in pergunta_sem_acento_original or "menor" in pergunta_sem_acento_original: entidades['ordem'] = "ASC"
    
    entidades['limite'] = "1"
    if "cinco acoes" in pergunta_sem_acento_original or "cinco ações" in pergunta_lower: entidades['limite'] = "5"
    elif "3 acoes" in pergunta_sem_acento_original or "3 ações" in pergunta_lower: entidades['limite'] = "3"

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
        
    entidades_preliminares = extrair_todas_entidades(pergunta_lower)
    
    template_id_final = None

    is_simple_ranking_list = ('quais' in pergunta_lower or 'liste' in pergunta_lower) and \
                             ('ranking_calculation' in entidades_preliminares and 'calculo' in entidades_preliminares and \
                              entidades_preliminares['ranking_calculation'] == entidades_preliminares['calculo'])

    # Etapa 1: Prioridade para ranking simples (Template 7A/7B) se for uma lista
    if is_simple_ranking_list:
        if 'nome_setor' in entidades_preliminares:
            template_id_final = 'Template_7B'
        else:
            template_id_final = 'Template_7A'
            
    # Etapa 2: Se não for, verificar perguntas complexas de duas intenções (Template 8A/8B)
    if not template_id_final and 'ranking_calculation' in entidades_preliminares and ('calculo' in entidades_preliminares or 'valor_desejado' in entidades_preliminares):
        if 'nome_setor' in entidades_preliminares:
            template_id_final = 'Template_8B'
        else:
            template_id_final = 'Template_8A'
    
    # Etapa 3: Perguntas sobre setores
    if not template_id_final and 'nome_setor' in entidades_preliminares:
        if 'calculo' in entidades_preliminares:
            template_id_final = 'Template_7B'
        elif 'valor_desejado' in entidades_preliminares and ('total' in pergunta_lower or 'volume' in pergunta_lower or 'quantidade' in pergunta_lower):
            template_id_final = 'Template_4C'
        else:
            template_id_final = 'Template_3A'
    
    # Etapa 4: Fallback para similaridade
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

    entidades_maiusculas = {k.upper(): v for k, v in entidades_preliminares.items()}
    return jsonify({"templateId": template_id_final, "entities": entidades_maiusculas})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)