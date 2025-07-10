import json
import re
import os
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- CARREGAMENTO E PREPARAÇÃO DOS DADOS ---

# Descobre o diretório absoluto onde este script está localizado para carregar arquivos de forma robusta.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def carregar_json(nome_arquivo):
    """Função auxiliar para carregar arquivos JSON do mesmo diretório que o script."""
    caminho_completo = os.path.join(SCRIPT_DIR, nome_arquivo)
    with open(caminho_completo, 'r', encoding='utf-8') as f:
        return json.load(f)

# Carrega todos os arquivos de configuração necessários
thesaurus = carregar_json('Thesaurus.json')
empresa_map = carregar_json('empresa_nome_map.json')
setor_map = carregar_json('setor_map.json')

# Carrega as perguntas de referência do arquivo de texto
reference_templates = {}
caminho_ref_questions = os.path.join(SCRIPT_DIR, 'Reference_questions.txt')
with open(caminho_ref_questions, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and ';' in line:
            template_id, question_text = line.split(';', 1)
            reference_templates[template_id.strip()] = question_text.strip()

# Prepara o modelo de similaridade (TF-IDF)
ref_ids = list(reference_templates.keys())
ref_questions = list(reference_templates.values())
vectorizer = TfidfVectorizer()
tfidf_matrix_ref = vectorizer.fit_transform(ref_questions) if ref_questions else None

# Mapa crucial que traduz o conceito da métrica para a propriedade RDF
METRICAS_MAP = {
    "preco_abertura": "b3:precoAbertura",
    "preco_fechamento": "b3:precoFechamento",
    "preco_maximo": "b3:precoMaximo",
    "preco_minimo": "b3:precoMinimo",
    "preco_medio": "b3:precoMedio",
    "volume": "b3:volumeNegociacao",
    "quantidade": "b3:temQuantidade"
}


# --- FUNÇÕES AUXILIARES DE PROCESSAMENTO DE LINGUAGEM ---

def extrair_entidades(pergunta_lower):
    """Extrai entidades específicas (empresa, ticker, setor, data) da pergunta e retorna os DADOS BRUTOS."""
    entidades = {}
    
    # Extrair Empresa/Ticker: ordena as chaves do mapa pela mais longa primeiro
    sorted_empresa_keys = sorted(empresa_map.keys(), key=len, reverse=True)
    for key in sorted_empresa_keys:
        if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
            value = empresa_map[key]
            # Diferencia se o valor é um Ticker ou um Nome de Empresa
            if re.match(r'^[A-Z]{4}\d{1,2}$', value):
                entidades['TICKER'] = value
            else:
                entidades['ENTIDADE_NOME'] = value
            break 
    
    # Extrair Setor
    sorted_setor_keys = sorted(setor_map.keys(), key=len, reverse=True)
    for key in sorted_setor_keys:
        if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
            entidades['NOME_SETOR'] = setor_map[key]
            break

    # Extrair Data
    match_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', pergunta_lower)
    if match_data:
        dia, mes, ano = match_data.groups()
        entidades['DATA'] = f"{ano}-{mes}-{dia}"

    return entidades

def identificar_metrica_canonico(pergunta_lower):
    """Identifica o nome canônico da métrica na pergunta (ex: "preco_maximo")."""
    for conceito in thesaurus.get('conceitos', []):
        if conceito['canonico'].startswith('preco_') or conceito['canonico'] in ['volume', 'quantidade']:
            sorted_sinonimos = sorted(conceito.get('sinonimos', []), key=lambda x: len(x['termo']), reverse=True)
            for sinonimo in sorted_sinonimos:
                if re.search(r'\b' + re.escape(sinonimo['termo'].lower()) + r'\b', pergunta_lower):
                    return conceito['canonico']
    
    if 'volume' in pergunta_lower: # Fallback para o template 4A
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

    # ***** LÓGICA DE DECISÃO APRIMORADA *****
    
    # 1. Extrai as entidades PRIMEIRO para tomar uma decisão informada.
    entidades_extraidas = extrair_entidades(pergunta_lower)
    
    template_id = None

    # 2. APLICA REGRA DE OURO: Se um Ticker foi encontrado, a intenção é buscar por código.
    #    Isso resolve a ambiguidade entre Template_1A e Template_1B.
    if 'TICKER' in entidades_extraidas and 'DATA' in entidades_extraidas:
        template_id = 'Template_1B'
    
    # 3. FALLBACK: Se nenhuma regra específica foi acionada, usa a similaridade de texto.
    if not template_id:
        # A normalização não é estritamente necessária aqui, mas pode ser reativada para robustez
        # pergunta_normalizada = normalizar_pergunta(pergunta_lower)
        tfidf_usuario = vectorizer.transform([pergunta_lower])
        similaridades = cosine_similarity(tfidf_usuario, tfidf_matrix_ref).flatten()
        indice_melhor = similaridades.argmax()
        template_id = ref_ids[indice_melhor]
    
    # 4. Continua o processo para encontrar a métrica e montar a resposta.
    metrica_canonico = identificar_metrica_canonico(pergunta_lower)
    if metrica_canonico:
        propriedade_rdf = METRICAS_MAP.get(metrica_canonico, "b3:propriedadeDesconhecida")
        entidades_extraidas['VALOR_DESEJADO'] = propriedade_rdf

    response = {
        "templateId": template_id,
        "entities": entidades_extraidas
    }
    
    return jsonify(response)

if __name__ == '__main__':
    # Bloco para rodar o script diretamente para testes locais.
    app.run(host='0.0.0.0', port=5000, debug=True)