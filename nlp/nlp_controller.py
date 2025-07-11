import os
import json
import re
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- Configuração Inicial do Flask ---
app = Flask(__name__)

# --- Carregamento dos Modelos e Dicionários (em memória) ---

# Define os caminhos relativos ao script para robustez
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. Carregar Perguntas de Referência e treinar o modelo TF-IDF
try:
    with open(os.path.join(BASE_DIR, 'Reference_questions.txt'), 'r', encoding='utf-8') as f:
        reference_data = [line.strip().split(';') for line in f if line.strip() and not line.startswith('#')]
    
    template_ids = [data[0] for data in reference_data]
    reference_questions = [data[1] for data in reference_data]

    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(reference_questions)
except FileNotFoundError:
    print("ERRO: O arquivo 'Reference_questions.txt' não foi encontrado.")
    template_ids, reference_questions, vectorizer, tfidf_matrix = [], [], None, None

# 2. Carregar dicionários de mapeamento
try:
    with open(os.path.join(BASE_DIR, 'empresa_nome_map.json'), 'r', encoding='utf-8') as f:
        empresa_map = json.load(f)
    with open(os.path.join(BASE_DIR, 'synonym_dictionary.json'), 'r', encoding='utf-8') as f:
        synonym_map = json.load(f)
except FileNotFoundError as e:
    print(f"ERRO: Não foi possível carregar um dos arquivos JSON de mapeamento: {e}")
    empresa_map, synonym_map = {}, {}


# --- Funções de Lógica ---

def find_best_template(user_question):
    """Encontra o template mais similar usando similaridade de cosseno."""
    if not vectorizer:
        return None
    user_tfidf = vectorizer.transform([user_question])
    similarities = cosine_similarity(user_tfidf, tfidf_matrix).flatten()
    best_index = similarities.argmax()
    return template_ids[best_index]

def extract_entities(user_question, template_id):
    """Extrai entidades (empresa, data, métrica, etc.) da pergunta."""
    entidades = {}
    question_lower = user_question.lower()

    # Extrair data (DD/MM/AAAA)
    date_match = re.search(r'\d{2}/\d{2}/\d{4}', user_question)
    if date_match:
        entidades['data'] = date_match.group(0)

    # Extrair nome da empresa
    for key, value in empresa_map.items():
        if key.lower() in question_lower:
            entidades['nome_empresa'] = value
            break
            
    # Extrair métrica
    for key, synonyms in synonym_map.items():
        for synonym in synonyms:
            if synonym.lower() in question_lower:
                entidades['metrica'] = key
                break
        if 'metrica' in entidades:
            break
            
    # --- LÓGICA NOVA: Extrair padrão REGEX para Template 5B ---
    if template_id == 'Template_5B':
        if "ordinária" in question_lower:
            entidades["regex_pattern"] = "3$"
        elif "preferencial" in question_lower:
            entidades["regex_pattern"] = "[456]$"
        elif "unit" in question_lower:
            entidades["regex_pattern"] = "11$"
            
    return entidades


# --- Endpoint da API ---

@app.route('/api/nlp/processar', methods=['POST'])
def process_question_endpoint():
    """Endpoint principal que recebe a pergunta e retorna o payload processado."""
    data = request.get_json()
    if not data or 'pergunta' not in data:
        return jsonify({"erro": "Payload inválido. A chave 'pergunta' é necessária."}), 400

    user_question = data['pergunta']
    
    # 1. Encontrar o melhor template
    best_template_id = find_best_template(user_question)
    if not best_template_id:
        return jsonify({"erro": "Modelo de NLP não inicializado."}), 500

    # 2. Extrair todas as entidades
    extracted_entities = extract_entities(user_question, best_template_id)
    
    # 3. Montar o payload final para o Java
    response_payload = {
        "templateId": best_template_id,
        "entidades": extracted_entities
    }
    
    return jsonify(response_payload)


# --- Bloco de Execução ---

if __name__ == '__main__':
    # Usar '0.0.0.0' para ser acessível dentro do container Docker
    app.run(host='0.0.0.0', port=5000)