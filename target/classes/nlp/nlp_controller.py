import json
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
    
    # --- PARÂMETROS DINÂMICOS (ORDEM, LIMITE, TIPO DE AÇÃO) ---
    pergunta_sem_acento = remover_acentos(pergunta_lower)
    if "ordinaria" in pergunta_sem_acento: entidades["regex_pattern"] = "3$"
    elif "preferencial" in pergunta_sem_acento: entidades["regex_pattern"] = "[456]$"
    elif "unit" in pergunta_sem_acento: entidades["regex_pattern"] = "11$"
    entidades['ordem'] = "DESC"
    if "baixa" in pergunta_sem_acento or "menor" in pergunta_sem_acento: entidades['ordem'] = "ASC"
    entidades['limite'] = "1"
    if "cinco acoes" in pergunta_sem_acento or "cinco ações" in pergunta_lower: entidades['limite'] = "5"
    elif "3 acoes" in pergunta_sem_acento or "3 ações" in pergunta_lower: entidades['limite'] = "3"

    # --- ENTIDADES FIXAS (DATA, MÉTRICA, CÁLCULO, SETOR, EMPRESA) ---
    # Extrai Data
    match_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', pergunta_lower)
    if match_data:
        dia, mes, ano = match_data.groups()
        entidades['data'] = f"{ano}-{mes}-{dia}"

    # Extrai Métricas e Cálculos
    mapa_metricas = {
        'calculo_variacao_perc': ['percentual de alta', 'percentual de baixa', 'variacao intradiaria percentual', 'variacao percentual'],
        'calculo_variacao_abs': ['variacao intradiaria absoluta', 'variacao absoluta'],
        'calculo_intervalo_perc': ['intervalo intradiario percentual', 'intervalo percentual'],
        'calculo_intervalo_abs': ['intervalo intradiario absoluto', 'intervalo absoluto'],
        'metrica.preco_maximo': ['preco maximo', 'preço máximo'], 'metrica.preco_minimo': ['preco minimo', 'preço mínimo'],
        'metrica.preco_fechamento': ['preco de fechamento', 'fechamento'], 'metrica.preco_abertura': ['preco de abertura', 'abertura'],
        'metrica.preco_medio': ['preco medio', 'preço médio'], 'metrica.quantidade': ['quantidade', 'total de negocios'],
        'metrica.volume': ['volume'],
    }
    for chave in sorted(mapa_metricas.keys(), key=lambda k: not k.startswith('calculo_')):
        for s in mapa_metricas[chave]:
            if re.search(r'\b' + remover_acentos(s) + r'\b', pergunta_sem_acento):
                if chave.startswith('calculo_'): entidades['calculo'] = chave.replace('calculo_', '')
                else: entidades['valor_desejado'] = chave
                break
        if 'calculo' in entidades or 'valor_desejado' in entidades: break

    # Extrai Ticker
    ticker_match = re.search(r'\b([A-Z0-9]{5,6})\b', pergunta_lower.upper())
    if ticker_match:
        entidades['entidade_nome'] = ticker_match.group(1)
    
    # Extrai Setor
    sorted_setor_keys = sorted(setor_map.keys(), key=len, reverse=True)
    for key in sorted_setor_keys:
        if re.search(r'\b' + re.escape(remover_acentos(key.lower())) + r'\b', pergunta_sem_acento):
            entidades['nome_setor'] = setor_map[key]
            break

    # Extrai Nome da Empresa (se Ticker não foi encontrado)
    if 'entidade_nome' not in entidades:
        sorted_empresa_keys = sorted(empresa_map.keys(), key=len, reverse=True)
        for key in sorted_empresa_keys:
            if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
                entidades['entidade_nome'] = key
                break
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
        
    entidades_extraidas = extrair_todas_entidades(pergunta_lower)
    
    # Lógica de seleção de template
    if 'nome_setor' in entidades_extraidas:
        if 'calculo' in entidades_extraidas: template_id_final = 'Template_7B'
        elif 'valor_desejado' in entidades_extraidas: template_id_final = 'Template_4C'
        else: template_id_final = 'Template_3A'
    else:
        if tfidf_matrix_ref is not None and len(ref_questions_flat) > 0:
            tfidf_usuario = vectorizer.transform([pergunta_lower])
            similaridades = cosine_similarity(tfidf_usuario, tfidf_matrix_ref).flatten()
            if similaridades.any(): template_id_final = ref_ids_flat[similaridades.argmax()]
            else: return jsonify({"error": "Não foi possível encontrar similaridade."}), 404
        else:
            return jsonify({"error": "Nenhum template de referência carregado."}), 500

    if not template_id_final:
        return jsonify({"error": "Não foi possível identificar um template para a pergunta."}), 404

    entidades_maiusculas = {k.upper(): v for k, v in entidades_extraidas.items()}
    return jsonify({"templateId": template_id_final, "entities": entidades_maiusculas})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)