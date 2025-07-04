import json
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re

# --- CARREGAMENTO E PREPARAÇÃO DOS DADOS (feito uma vez na inicialização) ---

# 1. Carregar o Thesaurus unificado
try:
    with open('src/main/resources/Thesaurus.json', 'r', encoding='utf-8') as f:
        thesaurus = json.load(f)
except FileNotFoundError:
    # Fallback para caso o script seja executado de um diretório diferente
    with open('Thesaurus.json', 'r', encoding='utf-8') as f:
        thesaurus = json.load(f)


# 2. Carregar as perguntas de interesse (que definem as intenções gerais)
try:
    with open('src/main/resources/perguntas_de_interesse.txt', 'r', encoding='utf-8') as f:
        perguntas_interesse = [line.strip() for line in f.readlines()]
except FileNotFoundError:
    with open('perguntas_de_interesse.txt', 'r', encoding='utf-8') as f:
        perguntas_interesse = [line.strip() for line in f.readlines()]

# 3. Preparar o modelo de similaridade (TF-IDF)
vectorizer = TfidfVectorizer()
tfidf_matrix_interesse = vectorizer.fit_transform(perguntas_interesse)


# --- FUNÇÕES AUXILIARES ---

def extrair_entidades(pergunta_usuario):
    """
    Extrai todas as entidades que encontra: empresa, código, setor, data.
    """
    entidades = {}
    pergunta_lower = pergunta_usuario.lower()
    
    # Itera sobre os tipos de entidade no thesaurus (Empresa, Ticker, Setor)
    for tipo_entidade, mapeamentos in thesaurus['entidades'].items():
        for nome_canonico, sinonimos in mapeamentos.items():
            for s in sinonimos:
                # Usamos limites de palavra (\b) para evitar correspondências parciais (ex: 'vale' em 'equivalente')
                if re.search(r'\b' + re.escape(s.lower()) + r'\b', pergunta_lower):
                    chave_template = tipo_entidade.lower() # 'empresa', 'ticker', 'setor'
                    entidades[chave_template] = nome_canonico
                    break # Para de procurar sinônimos para esta entidade canônica
            if nome_canonico in entidades.values():
                break # Para de procurar outras entidades do mesmo tipo se já achou uma

    # Extração de Data
    match_data = re.search(r'(\d{2}/\d{2}/\d{4})', pergunta_usuario)
    if match_data:
        data_str = match_data.group(1)
        dia, mes, ano = data_str.split('/')
        entidades['data'] = f"{ano}-{mes}-{dia}"
        
    return entidades

def identificar_metrica(pergunta_usuario):
    """
    Encontra a métrica solicitada na pergunta (ex: preço mínimo, volume).
    """
    pergunta_lower = pergunta_usuario.lower()
    
    # Itera sobre os conceitos do thesaurus
    for conceito_info in thesaurus['conceitos']:
        # Foca apenas nos conceitos que definimos como métricas
        if conceito_info['canonico'].startswith('metrica_'):
            for sinonimo_info in conceito_info['sinonimos']:
                if re.search(r'\b' + re.escape(sinonimo_info['termo'].lower()) + r'\b', pergunta_lower):
                    return conceito_info['canonico'] # Retorna a chave, ex: "metrica_preco_minimo"
    return None


# --- CONFIGURAÇÃO DA API FLASK E LÓGICA PRINCIPAL ---

app = Flask(__name__)

@app.route('/process_question', methods=['POST'])
def process_question():
    data = request.get_json()
    if not data or 'question' not in data:
        return jsonify({"error": "Pergunta não encontrada"}), 400
        
    pergunta_usuario = data['question']

    # ETAPA 1: Extrair todas as entidades da pergunta original
    entidades = extrair_entidades(pergunta_usuario)

    # ETAPA 2: Identificar a intenção GERAL da pergunta
    tfidf_usuario = vectorizer.transform([pergunta_usuario.lower()])
    similaridades = cosine_similarity(tfidf_usuario, tfidf_matrix_interesse)
    indice_intencao = similaridades.argmax()

    nome_template = 'template_desconhecido'

    # ETAPA 3: LÓGICA DE DECISÃO INTELIGENTE PARA ESCOLHER O TEMPLATE
    
    # INTENÇÃO 0: Buscar uma métrica de uma ação específica
    if indice_intencao == 0:
        metrica_identificada = identificar_metrica(pergunta_usuario)
        
        if metrica_identificada:
            # Mapeia a métrica para o nome do template estático correspondente
            mapa_metricas_template = {
                'metrica_preco_fechamento': 'Template_1A',
                'metrica_preco_abertura':   'Template_1B',
                'metrica_preco_maximo':     'Template_1C',
                'metrica_preco_minimo':     'Template_1D',
                'metrica_preco_medio':      'Template_1E',
                'metrica_volume':           'Template_1F',
                'metrica_quantidade':       'Template_1G'
            }
            nome_template = mapa_metricas_template.get(metrica_identificada)
    
    # OUTRAS INTENÇÕES
    else:
        # Mapeia os outros índices para os templates correspondentes
        mapa_outras_intencoes = {
            1: 'Template_2A', # "Qual o código..."
            2: 'Template_3A', # "Quais são as ações..."
            3: 'Template_4A'  # "Qual foi o volume do setor..."
        }
        nome_template = mapa_outras_intencoes.get(indice_intencao)

    # MONTAGEM FINAL DA RESPOSTA PARA O JAVA
    response = {
        "template": nome_template,
        "entities": entidades
    }
    
    return jsonify(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)