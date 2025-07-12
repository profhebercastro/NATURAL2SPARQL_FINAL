import json
import re
import os
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- CARREGAMENTO E PREPARAÇÃO DOS DADOS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def carregar_arquivo_json(nome_arquivo):
    caminho_completo = os.path.join(SCRIPT_DIR, nome_arquivo)
    try:
        with open(caminho_completo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError: return {}

empresa_map = carregar_arquivo_json('empresa_nome_map.json')

reference_templates = {}
try:
    caminho_ref_questions = os.path.join(SCRIPT_DIR, 'Reference_questions.txt')
    with open(caminho_ref_questions, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and ';' in line and not line.startswith('#'):
                template_id, question_text = line.split(';', 1)
                reference_templates[template_id.strip()] = question_text.strip()
except FileNotFoundError: pass

ref_ids = list(reference_templates.keys())
ref_questions = list(reference_templates.values())
vectorizer = TfidfVectorizer()
tfidf_matrix_ref = vectorizer.fit_transform(ref_questions) if ref_questions else None

# --- FUNÇÕES AUXILIARES DE PROCESSAMENTO ---

# --- CORREÇÃO 1: LÓGICA DE EXTRAÇÃO MELHORADA ---
def extrair_entidades(pergunta_lower, template_id):
    entidades = {}
    
    # Extrai o NOME DA EMPRESA e o TERMO DE BUSCA ORIGINAL
    sorted_empresa_keys = sorted(empresa_map.keys(), key=len, reverse=True)
    for key in sorted_empresa_keys:
        if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
            entidades['entidade_nome'] = empresa_map[key]  # Nome formal, ex: "VALE S.A."
            entidades['termo_busca_empresa'] = key        # Termo original, ex: "Vale"
            break
    
    match_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', pergunta_lower)
    if match_data:
        dia, mes, ano = match_data.groups()
        entidades['data'] = f"{ano}-{mes}-{dia}"

    if template_id == 'Template_5B':
        if "ordinária" in pergunta_lower: entidades["regex_pattern"] = "3$"
        elif "preferencial" in pergunta_lower: entidades["regex_pattern"] = "[456]$"
        elif "unit" in pergunta_lower: entidades["regex_pattern"] = "11$"
            
    return entidades

# --- CORREÇÃO 2: IDENTIFICAÇÃO DE MÉTRICA ROBUSTA ---
def identificar_metrica_canonico(pergunta_lower):
    """Identifica a métrica na pergunta de forma robusta, usando um mapa interno."""
    mapa_metricas = {
        'preco_maximo': ['preço máximo', 'preco maximo', 'máximo'],
        'preco_minimo': ['preço mínimo', 'preco minimo', 'mínimo'],
        'preco_fechamento': ['preço de fechamento', 'fechamento'],
        'preco_abertura': ['preço de abertura', 'abertura'],
        'preco_medio': ['preço médio', 'preco medio'],
        'quantidade': ['quantidade', 'quantidade de ações', 'total de negocios'],
        'volume': ['volume']
    }
    for canonico, sinonimos in mapa_metricas.items():
        for s in sinonimos:
            if s in pergunta_lower:
                return canonico
    return None

# --- API FLASK ---
app = Flask(__name__)

@app.route('/process_question', methods=['POST'])
def process_question():
    data = request.get_json()
    pergunta_usuario_original = data.get('question', '')
    pergunta_lower = pergunta_usuario_original.lower()

    if not pergunta_lower.strip(): return jsonify({"error": "Pergunta não pode ser vazia"}), 400
    if not ref_questions: return jsonify({"error": "Sistema de NLP não inicializado."}), 500

    tfidf_usuario = vectorizer.transform([pergunta_lower])
    similaridades = cosine_similarity(tfidf_usuario, tfidf_matrix_ref).flatten()
    indice_melhor_similaridade = similaridades.argmax()
    template_id = ref_ids[indice_melhor_similaridade]

    # Bloco de Lógica de Refinamento
    if "ordinária" in pergunta_lower or "preferencial" in pergunta_lower or "unit" in pergunta_lower:
        template_id = 'Template_5B'
    elif "quantidade" in pergunta_lower and "negociadas" in pergunta_lower:
        template_id = 'Template_4B'
    elif "da ação da" in pergunta_lower:
        template_id = 'Template_5A'

    entidades_extraidas = extrair_entidades(pergunta_lower, template_id)
    metrica_canonico = identificar_metrica_canonico(pergunta_lower)
    if metrica_canonico:
        entidades_extraidas['valor_desejado'] = f'metrica.{metrica_canonico}'

    # Usa o termo de busca para o REGEX, se existir, senão usa o nome formal.
    if 'termo_busca_empresa' in entidades_extraidas:
        entidades_extraidas['entidade_nome'] = entidades_extraidas['termo_busca_empresa']
    
    entidades_maiusculas = {k.upper(): v for k, v in entidades_extraidas.items()}

    return jsonify({"templateId": template_id, "entities": entidades_maiusculas})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)