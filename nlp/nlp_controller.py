import json
import re
import os
import unicodedata
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- LOADING ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
def load_json_file(filename):
    path = os.path.join(SCRIPT_DIR, filename)
    try:
        with open(path, 'r', encoding='utf-8') as f: return json.load(f)
    except FileNotFoundError: return {}

empresa_map = load_json_file('Named_entity_dictionary.json')
setor_map = load_json_file('setor_map.json')

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

# --- HELPER FUNCTIONS ---
def remove_accents(text):
    nfkd_form = unicodedata.normalize('NFKD', text)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def extract_entities(question_lower):
    entities = {}
    question_no_accents = remove_accents(question_lower)

    # 1. Extract Date
    date_match = re.search(r'(\d{2})/(\d{2})/(\d{4})', question_lower)
    if date_match:
        day, month, year = date_match.groups()
        entities['data'] = f"{year}-{month}-{day}"

    # 2. Extract Ticker (Highest Priority Entity)
    ticker_match = re.search(r'\b([A-Z0-9]{5,6})\b', question_lower.upper())
    if ticker_match:
        entities['entidade_nome'] = ticker_match.group(1)
    
    # 3. Extract Sector
    # Order keys by length to match longer phrases first (e.g., "petroleo e gas" before "gas")
    sorted_sector_keys = sorted(setor_map.keys(), key=len, reverse=True)
    for key in sorted_sector_keys:
        if re.search(r'\b' + re.escape(remove_accents(key.lower())) + r'\b', question_no_accents):
            entities['nome_setor'] = setor_map[key]
            break

    # 4. Extract Company Name (only if a Ticker was NOT found)
    if 'entidade_nome' not in entities:
        sorted_empresa_keys = sorted(empresa_map.keys(), key=len, reverse=True)
        for key in sorted_empresa_keys:
            if re.search(r'\b' + re.escape(key.lower()) + r'\b', question_lower):
                entities['entidade_nome'] = key
                break
                
    return entities

def identify_dynamic_params(question_lower):
    params = {}
    question_no_accents = remove_accents(question_lower)

    metric_map = {
        'calculo_variacao_abs': ['variacao intradiaria absoluta', 'variacao absoluta'],
        'calculo_variacao_perc': ['variacao intradiaria percentual', 'variacao percentual'],
        'calculo_intervalo_perc': ['intervalo intradiario percentual', 'intervalo percentual'],
        'calculo_intervalo_abs': ['intervalo intradiario absoluto', 'intervalo absoluto'],
        'metrica.preco_maximo': ['preco maximo', 'preço máximo'],
        'metrica.preco_minimo': ['preco minimo', 'preço mínimo'],
        'metrica.preco_fechamento': ['preco de fechamento', 'fechamento'],
        'metrica.preco_abertura': ['preco de abertura', 'abertura'],
        'metrica.preco_medio': ['preco medio', 'preço médio'],
        'metrica.quantidade': ['quantidade', 'total de negocios'],
        'metrica.volume': ['volume'],
    }

    for key, synonyms in metric_map.items():
        for s in synonyms:
            if re.search(r'\b' + remove_accents(s) + r'\b', question_no_accents):
                if key.startswith('calculo_'):
                    params['calculo'] = key.replace('calculo_', '')
                else:
                    params['valor_desejado'] = key
                break
        if 'calculo' in params or 'valor_desejado' in params:
            break

    if "ordinaria" in question_no_accents: params["regex_pattern"] = "3$"
    elif "preferencial" in question_no_accents: params["regex_pattern"] = "[456]$"
    elif "unit" in question_no_accents: params["regex_pattern"] = "11$"
    
    params['ordem'] = "DESC"
    if "baixa" in question_no_accents or "menor" in question_no_accents: params['ordem'] = "ASC"
        
    params['limite'] = "1"
    if "cinco acoes" in question_no_accents or "cinco ações" in question_lower: params['limite'] = "5"
        
    return params

# --- FLASK API ---
app = Flask(__name__)
@app.route('/process_question', methods=['POST'])
def process_question():
    data = request.get_json()
    if not data or 'question' not in data:
        return jsonify({"error": "Invalid payload"}), 400
    
    question_lower = data.get('question', '').lower()
    if not question_lower.strip(): 
        return jsonify({"error": "Question cannot be empty"}), 400

    # Template matching
    if tfidf_matrix_ref is not None and len(ref_questions_flat) > 0:
        user_tfidf = vectorizer.transform([question_lower])
        similarities = cosine_similarity(user_tfidf, tfidf_matrix_ref).flatten()
        if similarities.any():
            final_template_id = ref_ids_flat[similarities.argmax()]
        else:
            return jsonify({"error": "Could not find a similarity"}), 404
    else:
        return jsonify({"error": "No reference templates loaded"}), 500

    if not final_template_id:
        return jsonify({"error": "Could not identify a template for the question"}), 404

    # Entity and Parameter Extraction
    extracted_entities = extract_entities(question_lower)
    dynamic_params = identify_dynamic_params(question_lower)
    extracted_entities.update(dynamic_params)
    
    # Final response formatting
    uppercase_entities = {k.upper(): v for k, v in extracted_entities.items()}
    return jsonify({"templateId": final_template_id, "entities": uppercase_entities})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)