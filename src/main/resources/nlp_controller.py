import json
import re
import os
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- CARREGAMENTO E PREPARAÇÃO DOS DADOS (COM CAMINHOS ROBUSTOS) ---

# Descobre o diretório absoluto onde este script está localizado.
# Isso torna o carregamento de arquivos seguro, não importa de onde o script seja chamado.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def carregar_json(nome_arquivo):
    """Função auxiliar para carregar arquivos JSON do mesmo diretório que o script."""
    caminho_completo = os.path.join(SCRIPT_DIR, nome_arquivo)
    with open(caminho_completo, 'r', encoding='utf-8') as f:
        return json.load(f)

# Carrega todos os arquivos de configuração usando o caminho absoluto
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

# Prepara o modelo de similaridade (TF-IDF) com os textos das perguntas de referência
ref_ids = list(reference_templates.keys())
ref_questions = list(reference_templates.values())
vectorizer = TfidfVectorizer()
tfidf_matrix_ref = vectorizer.fit_transform(ref_questions)


# --- FUNÇÕES AUXILIARES DE PROCESSAMENTO DE LINGUAGEM ---

def normalizar_pergunta(pergunta_lower):
    """
    Substitui sinônimos na pergunta pelo seu termo canônico do Thesaurus.
    Esta é a etapa crucial para reduzir a ambiguidade.
    Exemplo: "cotas das companhias" -> "ação das empresa"
    """
    pergunta_normalizada = pergunta_lower
    
    # Itera sobre os conceitos (acao, empresa, setor, etc.)
    # Ordena os sinônimos pelo comprimento para evitar substituições parciais (ex: "ação" antes de "ação ordinária")
    for conceito in thesaurus.get('conceitos', []):
        termo_canonico = conceito['canonico'].replace('_', ' ')
        sorted_sinonimos = sorted(conceito.get('sinonimos', []), key=lambda x: len(x['termo']), reverse=True)
        
        for sinonimo_info in sorted_sinonimos:
            termo_sinonimo = sinonimo_info['termo'].lower()
            # Usa regex com limites de palavra (\b) para substituir apenas a palavra inteira
            pergunta_normalizada = re.sub(r'\b' + re.escape(termo_sinonimo) + r'\b', termo_canonico, pergunta_normalizada)
            
    return pergunta_normalizada

def extrair_entidades(pergunta_lower):
    """Extrai entidades específicas (empresa, ticker, setor, data) da pergunta."""
    entidades = {}
    
    # Extrair Empresa/Ticker: ordena as chaves do mapa pela mais longa primeiro
    sorted_empresa_keys = sorted(empresa_map.keys(), key=len, reverse=True)
    for key in sorted_empresa_keys:
        if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
            value = empresa_map[key]
            if re.match(r'^[A-Z]{4}\d{1,2}$', value):
                entidades['TICKER'] = f'"{value}"' # Adiciona aspas para o literal SPARQL
            else:
                entidades['ENTIDADE_NOME'] = f'"{value}"@pt' # Adiciona aspas e tag de idioma
            break # Pega a primeira e mais longa correspondência

    # Extrair Setor
    sorted_setor_keys = sorted(setor_map.keys(), key=len, reverse=True)
    for key in sorted_setor_keys:
        if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
            entidades['NOME_SETOR'] = f'"{setor_map[key]}"@pt'
            break

    # Extrair Data no formato YYYY-MM-DD
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
                    return conceito['canonico'] # Retorna o nome canônico, ex: "preco_maximo"
    
    # Fallback para caso a pergunta do Template_4A não especifique a métrica explicitamente
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

    # ETAPA 0: NORMALIZAR A PERGUNTA para melhorar a seleção de template
    pergunta_normalizada = normalizar_pergunta(pergunta_lower)
    
    # ETAPA 1: Encontrar o melhor template USANDO A PERGUNTA NORMALIZADA
    tfidf_usuario = vectorizer.transform([pergunta_normalizada])
    similaridades = cosine_similarity(tfidf_usuario, tfidf_matrix_ref).flatten()
    indice_melhor = similaridades.argmax()
    template_id = ref_ids[indice_melhor]

    # ETAPA 2: Extrair todas as entidades da PERGUNTA ORIGINAL
    entidades_extraidas = extrair_entidades(pergunta_lower)

    # ETAPA 3: Identificar a métrica da PERGUNTA ORIGINAL e mapeá-la
    metrica_canonico = identificar_metrica(pergunta_lower)
    if metrica_canonico:
        # A chave no template é #VALOR_DESEJADO#. O valor será a chave que o Java usará 
        # para buscar no placeholders.properties. Ex: "metrica.preco_maximo"
        entidades_extraidas['VALOR_DESEJADO'] = f'metrica.{metrica_canonico}'

    # Montar a resposta final para o serviço Java
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
    # Este bloco é para rodar o script diretamente para testes locais.
    # Em produção (no Render), o Gunicorn será usado para iniciar o 'app'.
    app.run(host='0.0.0.0', port=5000, debug=True)