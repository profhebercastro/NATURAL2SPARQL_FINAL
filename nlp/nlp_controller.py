import json
import re
import os
import unicodedata
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- CARREGAMENTO E PREPARAÇÃO DOS DADOS ---
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

# --- FUNÇÕES AUXILIARES DE PROCESSAMENTO ---
def remover_acentos(texto):
    nfkd_form = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def extrair_todas_entidades_e_parametros(pergunta_lower):
    """Função ÚNICA e ROBUSTA que extrai todas as entidades e parâmetros."""
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
    
    # 4. Extrai Métricas e Cálculos
    
    # Mapeamento de frases para chaves de cálculo/métrica
    mapa_metricas = {
        'calculo_principal_variacao_abs': ['variacao intradiaria absoluta'],
        'calculo_principal_intervalo_perc': ['intervalo intradiario percentual'],
        'calculo_ranking_variacao_perc_asc': ['baixa percentual', 'percentual de baixa'],
        'calculo_ranking_variacao_perc_desc': ['alta percentual', 'percentual de alta'],
        'calculo_ranking_variacao_abs_abs_asc': ['menor variacao'],
        'metrica.preco_maximo': ['preço máximo', 'preco maximo'],
        'metrica.preco_minimo': ['preço mínimo', 'preco minimo'],
        'metrica.preco_fechamento': ['preço de fechamento', 'fechamento'],
        'metrica.preco_abertura': ['preço de abertura', 'abertura'],
        'metrica.quantidade': ['quantidade', 'total de negocios'],
        'metrica.volume': ['volume']
    }

    for chave, sinonimos in mapa_metricas.items():
        if any(remover_acentos(s) in pergunta_sem_acento for s in sinonimos):
            if chave.startswith('calculo_principal'):
                entidades['calculo_principal'] = chave.split('_')[-1]
            elif chave.startswith('calculo_ranking'):
                parts = chave.split('_')
                entidades['calculo_ranking'] = parts[2]
                entidades['ordem_ranking'] = parts[3].upper()
            else:
                entidades['valor_desejado'] = chave
    
    # 5. Extrai Limite
    if "cinco acoes" in pergunta_sem_acento or "cinco ações" in pergunta_lower:
        entidades['limite_ranking'] = "5"
    else:
        entidades['limite_ranking'] = "1"

    # 6. Extrai Regex para tipo de ação
    if "ordinaria" in pergunta_sem_acento: entidades["regex_pattern"] = "3$"
    elif "preferencial" in pergunta_sem_acento: entidades["regex_pattern"] = "[456]$"
    elif "unit" in pergunta_sem_acento: entidades["regex_pattern"] = "11$"
            
    return entidades

# --- API FLASK ---
app = Flask(__name__)
@app.route('/process_question', methods=['POST'])
def process_question():
    data = request.get_json()
    pergunta_lower = data.get('question', '').lower()
    if not pergunta_lower.strip(): return jsonify({"error": "A pergunta não pode ser vazia."}), 400

    # 1. Classificação por Similaridade (Fallback)
    tfidf_usuario = vectorizer.transform([pergunta_lower])
    similaridades = cosine_similarity(tfidf_usuario, tfidf_matrix_ref).flatten()
    template_id_final = ref_ids[similaridades.argmax()]

    # 2. Extrai tudo que a pergunta pode oferecer
    entidades_extraidas = extrair_todas_entidades_e_parametros(pergunta_lower)
    
    # 3. Converte as chaves para maiúsculas
    entidades_maiusculas = {k.upper(): v for k, v in entidades_extraidas.items()}

    return jsonify({"templateId": template_id_final, "entities": entidades_maiusculas})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)