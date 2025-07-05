import json
import re
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- CARREGAMENTO E PREPARAÇÃO DOS DADOS ---
# Como o Gunicorn agora garante o diretório de trabalho com a flag --chdir,
# podemos usar caminhos relativos simples e diretos para carregar os arquivos.

def carregar_json(nome_arquivo):
    """Função auxiliar para carregar arquivos JSON do diretório de trabalho atual."""
    try:
        with open(nome_arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERRO CRÍTICO: Arquivo de configuração '{nome_arquivo}' não encontrado.")
        # Em um cenário real, isso poderia lançar uma exceção para impedir o app de iniciar.
        return {}

# Carrega todos os arquivos de configuração necessários
thesaurus = carregar_json('Thesaurus.json')
empresa_map = carregar_json('empresa_nome_map.json')
setor_map = carregar_json('setor_map.json')

# Carrega as perguntas de referência do arquivo de texto
reference_templates = {}
try:
    with open('Reference_questions.txt', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and ';' in line:
                template_id, question_text = line.split(';', 1)
                reference_templates[template_id.strip()] = question_text.strip()
except FileNotFoundError:
    print("ERRO CRÍTICO: Arquivo 'Reference_questions.txt' não encontrado.")


# Prepara o modelo de similaridade (TF-IDF)
ref_ids = list(reference_templates.keys())
ref_questions = list(reference_templates.values())
vectorizer = TfidfVectorizer()
# Garante que não tentaremos treinar o vetorizador com uma lista vazia
if ref_questions:
    tfidf_matrix_ref = vectorizer.fit_transform(ref_questions)
else:
    tfidf_matrix_ref = None


# --- FUNÇÕES AUXILIARES DE PROCESSAMENTO DE LINGUAGEM ---

def normalizar_pergunta(pergunta_lower):
    """
    Substitui sinônimos na pergunta pelo seu termo canônico do Thesaurus.
    """
    pergunta_normalizada = pergunta_lower
    for conceito in thesaurus.get('conceitos', []):
        termo_canonico = conceito['canonico'].replace('_', ' ')
        sorted_sinonimos = sorted(conceito.get('sinonimos', []), key=lambda x: len(x['termo']), reverse=True)
        for sinonimo_info in sorted_sinonimos:
            termo_sinonimo = sinonimo_info['termo'].lower()
            pergunta_normalizada = re.sub(r'\b' + re.escape(termo_sinonimo) + r'\b', termo_canonico, pergunta_normalizada)
    return pergunta_normalizada

def extrair_entidades(pergunta_lower):
    """Extrai entidades específicas (empresa, ticker, setor, data) da pergunta."""
    entidades = {}
    
    # Extrair Empresa/Ticker
    sorted_empresa_keys = sorted(empresa_map.keys(), key=len, reverse=True)
    for key in sorted_empresa_keys:
        if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
            value = empresa_map[key]
            if re.match(r'^[A-Z]{4}\d{1,2}$', value):
                entidades['TICKER'] = f'"{value}"'
            else:
                entidades['ENTIDADE_NOME'] = f'"{value}"@pt'
            break 
    
    # Extrair Setor
    sorted_setor_keys = sorted(setor_map.keys(), key=len, reverse=True)
    for key in sorted_setor_keys:
        if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
            entidades['NOME_SETOR'] = f'"{setor_map[key]}"@pt'
            break

    # Extrair Data
    match_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', pergunta_lower)
    if match_data:
        dia, mes, ano = match_data.groups()
        entidades['DATA'] = f'"{ano}-{mes}-{dia}"^^xsd:date'

    return entidades

def identificar_metrica(pergunta_lower):
    """Identifica a métrica principal (ex: preço máximo, volume) na pergunta."""
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
         return jsonify({"error": "O sistema de NLP não foi inicializado corretamente (sem perguntas de referência)."}), 500

    # ETAPA 0: NORMALIZAR A PERGUNTA
    pergunta_normalizada = normalizar_pergunta(pergunta_lower)
    
    # ETAPA 1: Encontrar o melhor template
    tfidf_usuario = vectorizer.transform([pergunta_normalizada])
    similaridades = cosine_similarity(tfidf_usuario, tfidf_matrix_ref).flatten()
    indice_melhor = similaridades.argmax()
    template_id = ref_ids[indice_melhor]

    # ETAPA 2: Extrair entidades da pergunta original
    entidades_extraidas = extrair_entidades(pergunta_lower)

    # ETAPA 3: Identificar e mapear a métrica
    metrica_canonico = identificar_metrica(pergunta_lower)
    if metrica_canonico:
        entidades_extraidas['VALOR_DESEJADO'] = f'metrica.{metrica_canonico}'

    # Montar a resposta para o serviço Java
    response = {
        "templateId": template_id,
        "entities": entidades_extraidas,
        "debugInfo": {
            "perguntaOriginal": pergunta_usuario_original,
            "perguntaNormalizada": pergunta_normalizada,
            "templateEscolhido": template_id,
            "similaridadeScore": float(similaridades[indice_melhor])
        }
    }
    
    return jsonify(response)

if __name__ == '__main__':
    # Este bloco permite rodar o script diretamente com `python nlp_controller.py` para testes.
    # Em produção, o Gunicorn (chamado pelo start.sh) será o responsável por iniciar o `app`.
    app.run(host='0.0.0.0', port=5000, debug=True)