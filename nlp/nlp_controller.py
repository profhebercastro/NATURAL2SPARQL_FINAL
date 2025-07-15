import json
import re
import os
import unicodedata
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- Carregamento de Dados ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
def carregar_arquivo_json(nome_arquivo):
    caminho_completo = os.path.join(SCRIPT_DIR, nome_arquivo)
    try:
        with open(caminho_completo, 'r', encoding='utf-8') as f: return json.load(f)
    except FileNotFoundError: return {}

empresa_map = carregar_arquivo_json('empresa_nome_map.json')
setor_map = carregar_arquivo_json('setor_map.json')

reference_templates = {}
try:
    with open(os.path.join(SCRIPT_DIR, 'Reference_questions.txt'), 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() and ';' in line and not line.startswith('#'):
                template_id, question_text = line.split(';', 1)
                reference_templates[template_id.strip()] = question_text.strip()
except FileNotFoundError: pass

ref_ids = list(reference_templates.keys())
ref_questions = list(reference_templates.values())
vectorizer = TfidfVectorizer()
tfidf_matrix_ref = vectorizer.fit_transform(ref_questions) if ref_questions else None

# --- Funções Auxiliares ---
def remover_acentos(texto):
    nfkd_form = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def extrair_todas_entidades(pergunta_lower):
    """Extrai TODAS as possíveis entidades e parâmetros de uma vez."""
    entidades = {}
    pergunta_sem_acento = remover_acentos(pergunta_lower)

    # 1. Extrai Ticker OU Nome de Empresa
    ticker_match = re.search(r'\b([a-zA-Z]{4}\d{1,2})\b', pergunta_lower)
    if ticker_match:
        entidades['entidade_nome'] = ticker_match.group(1).upper()
    else:
        sorted_empresa_keys = sorted(empresa_map.keys(), key=len, reverse=True)
        for key in sorted_empresa_keys:
            if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
                entidades['entidade_nome'] = key; break
    
    # 2. Extrai Setor
    sorted_setor_keys = sorted(setor_map.keys(), key=len, reverse=True)
    for key in sorted_setor_keys:
        if re.search(r'\b' + re.escape(remover_acentos(key.lower())) + r'\b', pergunta_sem_acento):
            entidades['nome_setor'] = setor_map[key]; break

    # 3. Extrai Data
    match_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', pergunta_lower)
    if match_data:
        dia, mes, ano = match_data.groups(); entidades['data'] = f"{ano}-{mes}-{dia}"
    
    # 4. Extrai Métrica ou Cálculo
    if "variacao intradiaria absoluta" in pergunta_sem_acento:
        entidades['calculo'] = 'variacao_abs'
    elif any(s in pergunta_sem_acento for s in ["alta percentual", "baixa percentual", "percentual de alta", "percentual de baixa"]):
        entidades['calculo'] = 'variacao_perc'
    elif "menor variacao" in pergunta_sem_acento:
        entidades['calculo'] = 'variacao_abs_abs'
    else:
        mapa_metricas = {'metrica.preco_maximo': ['preço máximo', 'preco maximo'],'metrica.preco_minimo': ['preço mínimo', 'preco minimo'],'metrica.preco_fechamento': ['preço de fechamento', 'fechamento'],'metrica.preco_abertura': ['preço de abertura', 'abertura'],'metrica.quantidade': ['quantidade', 'total de negocios'], 'metrica.volume': ['volume']}
        for chave, sinonimos in mapa_metricas.items():
            if any(remover_acentos(s) in pergunta_sem_acento for s in sinonimos):
                entidades['valor_desejado'] = chave; break
    
    # 5. Extrai Parâmetros de Ranking
    if "ordinaria" in pergunta_sem_acento: entidades["regex_pattern"] = "3$"
    elif "preferencial" in pergunta_sem_acento: entidades["regex_pattern"] = "[456]$"
    elif "unit" in pergunta_sem_acento: entidades["regex_pattern"] = "11$"
    
    entidades['ordem'] = "DESC"
    if "baixa" in pergunta_sem_acento or "menor" in pergunta_sem_acento:
        entidades['ordem'] = "ASC"
        
    entidades['limite'] = "1"
    if "cinco acoes" in pergunta_sem_acento or "cinco ações" in pergunta_lower:
        entidades['limite'] = "5"
            
    return entidades

# --- API FLASK ---
app = Flask(__name__)
@app.route('/process_question', methods=['POST'])
def process_question():
    data = request.get_json()
    pergunta_lower = data.get('question', '').lower()
    if not pergunta_lower.strip(): return jsonify({"error": "A pergunta não pode ser vazia."}), 400

    # Classificação por Regras + Fallback
    pergunta_sem_acento = remover_acentos(pergunta_lower)
    template_id_final = None

    ranking_keywords = ["qual ação", "maior alta", "maior baixa", "menor variacao", "cinco ações"]
    if any(keyword in pergunta_lower for keyword in ranking_keywords):
        template_id_final = 'Template_7A'
    elif "variacao intradiaria absoluta" in pergunta_sem_acento:
        template_id_final = 'Template_6A'
    elif "ordinária" in pergunta_lower or "preferencial" in pergunta_lower or "unit" in pergunta_lower or "ordinaria" in pergunta_sem_acento:
        template_id_final = 'Template_5B'
    elif re.search(r'\b([a-zA-Z]{4}\d{1,2})\b', pergunta_lower):
        template_id_final = 'Template_1B'
    elif "quantidade" in pergunta_lower and "negociadas" in pergunta_lower:
        template_id_final = 'Template_4B'
    elif "volume" in pergunta_lower and "setor" in pergunta_lower:
        template_id_final = 'Template_4A'
    else:
        tfidf_usuario = vectorizer.transform([pergunta_lower])
        similaridades = cosine_similarity(tfidf_usuario, tfidf_matrix_ref).flatten()
        template_id_final = ref_ids[similaridades.argmax()]

    # Extrai tudo que a pergunta pode oferecer
    entidades_extraidas = extrair_todas_entidades(pergunta_lower)
    
    entidades_maiusculas = {k.upper(): v for k, v in entidades_extraidas.items()}
    return jsonify({"templateId": template_id_final, "entities": entidades_maiusculas})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)