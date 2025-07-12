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

# Carrega as perguntas de referência do arquivo de texto
reference_templates = {}
caminho_ref_questions = os.path.join(SCRIPT_DIR, 'Reference_questions.txt')
with open(caminho_ref_questions, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        # Ignora linhas em branco ou comentários
        if line and ';' in line and not line.startswith('#'):
            template_id, question_text = line.split(';', 1)
            reference_templates[template_id.strip()] = question_text.strip()

# Prepara o modelo de similaridade TF-IDF
ref_ids = list(reference_templates.keys())
ref_questions = list(reference_templates.values())
vectorizer = TfidfVectorizer()
# Garante que o modelo só seja treinado se houver perguntas de referência
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
    """Extrai entidades específicas (empresa, data, setor, etc.) e retorna um dicionário."""
    entidades = {}
    
    # Extrai Nome da Empresa ou Ticker
    sorted_empresa_keys = sorted(empresa_map.keys(), key=len, reverse=True)
    for key in sorted_empresa_keys:
        if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
            value = empresa_map[key]
            if re.match(r'^[A-Z]{4}\d{1,2}$', value):
                entidades['ticker'] = value
            else:
                entidades['entidade_nome'] = value
            break 
    
    # Extrai Nome do Setor
    sorted_setor_keys = sorted(setor_map.keys(), key=len, reverse=True)
    for key in sorted_setor_keys:
        if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
            entidades['nome_setor'] = setor_map[key]
            break

    # Extrai Data no formato YYYY-MM-DD para compatibilidade com SPARQL xsd:date
    match_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', pergunta_lower)
    if match_data:
        dia, mes, ano = match_data.groups()
        entidades['data'] = f"{ano}-{mes}-{dia}"

    # Lógica para adicionar o padrão REGEX se o template for o que filtra por tipo de ação
    if template_id == 'Template_5B':
        if "ordinária" in pergunta_lower:
            entidades["regex_pattern"] = "3$"
        elif "preferencial" in pergunta_lower:
            entidades["regex_pattern"] = "[456]$"
        elif "unit" in pergunta_lower:
            entidades["regex_pattern"] = "11$"

    return entidades

def identificar_metrica_canonico(pergunta_lower):
    """Identifica o nome canônico da métrica na pergunta (ex: "preco_maximo") a partir do thesaurus."""
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
    if not data or 'question' not in data:
        return jsonify({"error": "O corpo da requisição deve ser um JSON com a chave 'question'."}), 400

    pergunta_usuario_original = data['question']
    pergunta_lower = pergunta_usuario_original.lower()

    if not pergunta_lower.strip():
        return jsonify({"error": "A pergunta não pode ser vazia."}), 400

    if not ref_questions or tfidf_matrix_ref is None:
         return jsonify({"error": "O sistema de NLP não foi inicializado corretamente (verifique Reference_questions.txt)."}), 500

    # 1. O modelo de similaridade faz a primeira tentativa de classificação
    pergunta_normalizada = normalizar_pergunta(pergunta_lower)
    tfidf_usuario = vectorizer.transform([pergunta_normalizada])
    similaridades = cosine_similarity(tfidf_usuario, tfidf_matrix_ref).flatten()
    indice_melhor_similaridade = similaridades.argmax()
    template_id = ref_ids[indice_melhor_similaridade]

    # --- INÍCIO: Bloco de Lógica de Refinamento (Regras de Negócio) ---
    # Este bloco corrige a escolha do modelo de similaridade se encontrar palavras-chave específicas.
    
    # Regra 1 (Mais específica): Se a pergunta contém um tipo de ação, DEVE ser o Template_5B.
    if "ordinária" in pergunta_lower or "preferencial" in pergunta_lower or "unit" in pergunta_lower:
        template_id = 'Template_5B'
    
    # Regra 2: Se a pergunta contém "quantidade" e "negociadas", DEVE ser o Template_4B.
    elif "quantidade" in pergunta_lower and "negociadas" in pergunta_lower:
        template_id = 'Template_4B'
        
    # Regra 3: Se a pergunta contém "da ação da", é muito provável que seja o Template_5A.
    elif "da ação da" in pergunta_lower:
        template_id = 'Template_5A'
    # --- FIM: Bloco de Lógica de Refinamento ---

    # Continua o processamento com o template_id (possivelmente corrigido)
    entidades_extraidas = extrair_entidades(pergunta_lower, template_id)
    
    metrica_canonico = identificar_metrica_canonico(pergunta_lower)
    if metrica_canonico:
        # A chave 'valor_desejado' é convertida para MAIÚSCULA depois
        entidades_extraidas['valor_desejado'] = f'metrica.{metrica_canonico}'

    # Converte todas as chaves para maiúsculas para corresponder aos placeholders do Java (ex: #ENTIDADE_NOME#)
    entidades_maiusculas = {k.upper(): v for k, v in entidades_extraidas.items()}

    # Monta a resposta final
    response = {
        "templateId": template_id,
        "entities": entidades_maiusculas,
        "debugInfo": {
            "perguntaOriginal": pergunta_usuario_original,
            "perguntaNormalizada": pergunta_normalizada,
            "templateEscolhidoPelaSimilaridade": ref_ids[indice_melhor_similaridade],
            "templateFinalAposRegras": template_id,
            "similaridadeScore": float(similaridades[indice_melhor_similaridade])
        }
    }
    return jsonify(response)

# Bloco para executar o servidor Flask
if __name__ == '__main__':
    # Usar '0.0.0.0' para ser acessível dentro do container Docker
    app.run(host='0.0.0.0', port=5000, debug=True)