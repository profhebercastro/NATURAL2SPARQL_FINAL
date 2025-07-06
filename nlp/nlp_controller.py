import json
import re
import os
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- CARREGAMENTO E PREPARAÇÃO ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def carregar_json(nome_arquivo):
    caminho_completo = os.path.join(SCRIPT_DIR, nome_arquivo)
    with open(caminho_completo, 'r', encoding='utf-8') as f:
        return json.load(f)

thesaurus = carregar_json('Thesaurus.json')
empresa_map = carregar_json('empresa_nome_map.json')
setor_map = carregar_json('setor_map.json')

reference_templates = {}
caminho_ref_questions = os.path.join(SCRIPT_DIR, 'Reference_questions.txt')
with open(caminho_ref_questions, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and ';' in line:
            template_id, question_text = line.split(';', 1)
            reference_templates[template_id.strip()] = question_text.strip()

ref_ids = list(reference_templates.keys())
ref_questions = list(reference_templates.values())
vectorizer = TfidfVectorizer()
tfidf_matrix_ref = vectorizer.fit_transform(ref_questions) if ref_questions else None

# --- MAPA DE MÉTRICAS PARA PROPRIEDADES RDF (COM A CORREÇÃO) ---
METRICAS_MAP = {
    "preco_abertura": "b3:precoAbertura",
    "preco_fechamento": "b3:precoFechamento",
    "preco_maximo": "b3:precoMaximo",
    "preco_minimo": "b3:precoMinimo",
    "preco_medio": "b3:precoMedio", # <-- CORRIGIDO AQUI
    "volume": "b3:volumeNegociacao",
    "quantidade": "b3:temQuantidade" # Conferir se este está correto na sua ontologia
}

# --- FUNÇÕES AUXILIARES ---
def extrair_entidades(pergunta_lower):
    entidades = {}
    sorted_empresa_keys = sorted(empresa_map.keys(), key=len, reverse=True)
    for key in sorted_empresa_keys:
        if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
            value = empresa_map[key]
            if re.match(r'^[A-Z]{4}\d{1,2}$', value):
                entidades['TICKER'] = value
            else:
                entidades['ENTIDADE_NOME'] = value
            break
    sorted_setor_keys = sorted(setor_map.keys(), key=len, reverse=True)
    for key in sorted_setor_keys:
        if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
            entidades['NOME_SETOR'] = setor_map[key]
            break
    match_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', pergunta_lower)
    if match_data:
        dia, mes, ano = match_data.groups()
        entidades['DATA'] = f"{ano}-{mes}-{dia}"
    return entidades

def identificar_metrica_canonico(pergunta_lower):
    for conceito in thesaurus.get('conceitos', []):
        if conceito['canonico'].startswith('preco_') or conceito['canonico'] in ['volume', 'quantidade']:
            for sinonimo in conceito.get('sinonimos', []):
                if re.search(r'\b' + re.escape(sinonimo['termo'].lower()) + r'\b', pergunta_lower):
                    return conceito['canonico']
    if 'volume' in pergunta_lower:
        return 'volume'
    return None

# --- API FLASK ---
app = Flask(__name__)

@app.route('/process_question', methods=['POST'])
def process_question():
    data = request.get_json()
    pergunta_usuario_original = data.get('question', '')
    pergunta_lower = pergunta_usuario_original.lower()

    if not pergunta_lower:
        return jsonify({"error": "Pergunta não pode ser vazia"}), 400

    if not ref_questions or tfidf_matrix_ref is None:
         return jsonify({"error": "O sistema de NLP não foi inicializado corretamente (sem perguntas de referência)."}), 500

    tfidf_usuario = vectorizer.transform([pergunta_lower])
    similaridades = cosine_similarity(tfidf_usuario, tfidf_matrix_ref).flatten()
    indice_melhor = similaridades.argmax()
    template_id = ref_ids[indice_melhor]

    entidades_extraidas = extrair_entidades(pergunta_lower)
    metrica_canonico = identificar_metrica_canonico(pergunta_lower)

    if metrica_canonico:
        propriedade_rdf = METRICAS_MAP.get(metrica_canonico, "b3:propriedadeDesconhecida")
        entidades_extraidas['VALOR_DESEJADO'] = propriedade_rdf

    response = {"templateId": template_id, "entities": entidades_extraidas}
    return jsonify(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)