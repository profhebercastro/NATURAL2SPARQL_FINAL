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
        with open(caminho_completo, 'r', encoding='utf-8') as f: return json.load(f)
    except FileNotFoundError: return {}

empresa_map = carregar_arquivo_json('empresa_nome_map.json')
setor_map = carregar_arquivo_json('setor_map.json')

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

def extrair_entidades(pergunta_lower, pergunta_original, template_id):
    entidades = {}
    
    ticker_match = re.search(r'\b([A-Z]{4}\d{1,2})\b', pergunta_original)
    if ticker_match:
        entidades['ticker'] = ticker_match.group(1)

    sorted_empresa_keys = sorted(empresa_map.keys(), key=len, reverse=True)
    for key in sorted_empresa_keys:
        if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
            entidades['termo_busca_empresa'] = key
            break
            
    for key, value in setor_map.items():
        if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
            entidades['nome_setor'] = value
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

def identificar_metrica_canonico(pergunta_lower):
    mapa_metricas = {
        'preco_maximo': ['preço máximo', 'preco maximo', 'máximo'],
        'preco_minimo': ['preço mínimo', 'preco minimo', 'mínimo', 'mínima'],
        'preco_fechamento': ['preço de fechamento', 'fechamento'],
        'preco_abertura': ['preço de abertura', 'abertura'],
        'preco_medio': ['preço médio', 'preco medio'],
        'quantidade': ['quantidade', 'quantidade de ações', 'total de negocios'],
        'volume': ['volume', 'volume negociado']
    }
    for canonico, sinonimos in mapa_metricas.items():
        for s in sinonimos:
            if s in pergunta_lower:
                return canonico
    return None

# --- API FLASK ---
app = Flask(__name__)
pergunta_usuario_original = "" # Variável global para ser acessível

@app.route('/process_question', methods=['POST'])
def process_question():
    global pergunta_usuario_original
    data = request.get_json()
    pergunta_usuario_original = data.get('question', '')
    pergunta_lower = pergunta_usuario_original.lower()

    if not pergunta_lower.strip(): return jsonify({"error": "Pergunta não pode ser vazia"}), 400
    if not ref_questions: return jsonify({"error": "Sistema de NLP não inicializado."}), 500

    # Lógica de Classificação Híbrida
    template_id_final = None

    # Etapa 1: Regras para casos específicos e inequívocos
    if re.search(r'\b([A-Z]{4}\d{1,2})\b', pergunta_usuario_original):
        template_id_final = 'Template_1B'
    elif "ordinária" in pergunta_lower or "preferencial" in pergunta_lower or "unit" in pergunta_lower:
        template_id_final = 'Template_5B'
    elif "código de negociação" in pergunta_lower:
        template_id_final = 'Template_2A'
    elif "ações do setor" in pergunta_lower:
         template_id_final = 'Template_3A'
    elif "volume negociado" in pergunta_lower and "setor" in pergunta_lower:
         template_id_final = 'Template_4A'
    elif "quantidade" in pergunta_lower and "negociadas" in pergunta_lower:
        template_id_final = 'Template_4B'

    # Etapa 2: Se nenhuma regra funcionou, usa a similaridade
    if not template_id_final:
        tfidf_usuario = vectorizer.transform([pergunta_lower])
        similaridades = cosine_similarity(tfidf_usuario, tfidf_matrix_ref).flatten()
        indice_melhor_similaridade = similaridades.argmax()
        template_id_final = ref_ids[indice_melhor_similaridade]

    entidades_extraidas = extrair_entidades(pergunta_lower, pergunta_usuario_original, template_id_final)
    metrica_canonico = identificar_metrica_canonico(pergunta_lower)
    if metrica_canonico:
        entidades_extraidas['valor_desejado'] = f'metrica.{metrica_canonico}'

    if 'termo_busca_empresa' in entidades_extraidas:
        entidades_extraidas['entidade_nome'] = entidades_extraidas['termo_busca_empresa']
    
    entidades_maiusculas = {k.upper(): v for k, v in entidades_extraidas.items()}
    return jsonify({"templateId": template_id_final, "entities": entidades_maiusculas})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)