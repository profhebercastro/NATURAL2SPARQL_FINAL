import json
import re
import os
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- CARREGAMENTO E PREPARAÇÃO DOS DADOS (Inicialização) ---

# Descobre o diretório absoluto onde este script está localizado para carregar arquivos de forma robusta.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def carregar_arquivo_json(nome_arquivo):
    """Função auxiliar para carregar arquivos JSON do mesmo diretório que o script."""
    caminho_completo = os.path.join(SCRIPT_DIR, nome_arquivo)
    with open(caminho_completo, 'r', encoding='utf-8') as f:
        return json.load(f)

# Carrega todos os arquivos de configuração
thesaurus = carregar_arquivo_json('synonym_dictionary.json')
empresa_map = carregar_arquivo_json('empresa_nome_map.json')
setor_map = carregar_arquivo_json('setor_map.json')

# Carrega as perguntas de referência
reference_templates = {}
caminho_ref_questions = os.path.join(SCRIPT_DIR, 'Reference_questions.txt')
with open(caminho_ref_questions, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and ';' in line and not line.startswith('#'):
            template_id, question_text = line.split(';', 1)
            reference_templates[template_id.strip()] = question_text.strip()

# Prepara o modelo de similaridade
ref_ids = list(reference_templates.keys())
ref_questions = list(reference_templates.values())
vectorizer = TfidfVectorizer()
tfidf_matrix_ref = vectorizer.fit_transform(ref_questions) if ref_questions else None


# --- FUNÇÕES AUXILIARES DE PROCESSAMENTO ---

def normalizar_pergunta(pergunta_lower):
    """Substitui sinônimos na pergunta pelo seu termo canônico do synonym_dictionary.json."""
    pergunta_normalizada = pergunta_lower
    for conceito in thesaurus.get('conceitos', []):
        termo_canonico = conceito['canonico'].replace('_', ' ')
        sorted_sinonimos = sorted(conceito.get('sinonimos', []), key=lambda x: len(x['termo']), reverse=True)
        for sinonimo_info in sorted_sinonimos:
            termo_sinonimo = sinonimo_info['termo'].lower()
            pergunta_normalizada = re.sub(r'\b' + re.escape(termo_sinonimo) + r'\b', termo_canonico, pergunta_normalizada)
    return pergunta_normalizada

def extrair_entidades(pergunta_lower, template_id):
    """Extrai entidades específicas e retorna um dicionário."""
    entidades = {}
    
    # Extrair Empresa/Ticker
    sorted_empresa_keys = sorted(empresa_map.keys(), key=len, reverse=True)
    for key in sorted_empresa_keys:
        if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
            value = empresa_map[key]
            # Diferencia se o valor é um ticker ou um nome completo
            if re.match(r'^[A-Z]{4}\d{1,2}$', value):
                entidades['ticker'] = value
            else:
                entidades['entidade_nome'] = value
            break 
    
    # Extrair Setor
    sorted_setor_keys = sorted(setor_map.keys(), key=len, reverse=True)
    for key in sorted_setor_keys:
        if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
            entidades['nome_setor'] = setor_map[key]
            break

    # Extrair Data no formato YYYY-MM-DD
    match_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', pergunta_lower)
    if match_data:
        dia, mes, ano = match_data.groups()
        entidades['data'] = f"{ano}-{mes}-{dia}"

    # --- NOVO BLOCO DE LÓGICA ---
    # Adiciona o padrão REGEX se o template for o que filtra por tipo de ação.
    if template_id == 'Template_5B':
        if "ordinária" in pergunta_lower:
            entidades["regex_pattern"] = "3$"
        elif "preferencial" in pergunta_lower:
            entidades["regex_pattern"] = "[456]$"
        elif "unit" in pergunta_lower:
            entidades["regex_pattern"] = "11$"
    # --- FIM DO NOVO BLOCO ---

    return entidades

def identificar_metrica_canonico(pergunta_lower):
    """Identifica o nome canônico da métrica na pergunta (ex: "preco_maximo")."""
    for conceito in thesaurus.get('conceitos', []):
        if conceito['canonico'].startswith('preco_') or conceito['canonico'] in ['volume', 'quantidade']:
            sorted_sinonimos = sorted(conceito.get('sinonimos', []), key=lambda x: len(x['termo']), reverse=True)
            for sinonimo in sorted_sinonimos:
                if re.search(r'\b' + re.escape(sinonimo['termo'].lower()) + r'\b', pergunta_lower):
                    return conceito['canonico']
    if 'volume' in pergunta_lower and 'setor' in pergunta_lower:
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
         return jsonify({"error": "O sistema de NLP não foi inicializado corretamente."}), 500

    # Lógica de processamento
    pergunta_normalizada = normalizar_pergunta(pergunta_lower)
    tfidf_usuario = vectorizer.transform([pergunta_normalizada])
    similaridades = cosine_similarity(tfidf_usuario, tfidf_matrix_ref).flatten()
    indice_melhor = similaridades.argmax()
    template_id = ref_ids[indice_melhor]

    # Passamos o template_id para a função de extração
    entidades_extraidas = extrair_entidades(pergunta_lower, template_id)
    
    metrica_canonico = identificar_metrica_canonico(pergunta_lower)
    if metrica_canonico:
        entidades_extraidas['valor_desejado'] = f'metrica.{metrica_canonico}'

    # --- NOVO ---
    # Converte as chaves do dicionário para maiúsculas para corresponder aos placeholders #NOME#
    entidades_maiusculas = {k.upper(): v for k, v in entidades_extraidas.items()}

    response = {
        "templateId": template_id,
        "entities": entidades_maiusculas, # Enviamos o dicionário com chaves em maiúsculas
        "debugInfo": {
            "perguntaOriginal": pergunta_usuario_original,
            "perguntaNormalizada": pergunta_normalizada,
            "templateEscolhido": template_id,
            "similaridadeScore": float(similaridades[indice_melhor])
        }
    }
    return jsonify(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)