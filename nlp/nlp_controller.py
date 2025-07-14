import json
import re
import os
import unicodedata
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- CARREGAMENTO E PREPARAÇÃO DOS DADOS (Inicialização) ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def carregar_arquivo_json(nome_arquivo):
    """Função auxiliar para carregar arquivos JSON do mesmo diretório que o script."""
    caminho_completo = os.path.join(SCRIPT_DIR, nome_arquivo)
    try:
        with open(caminho_completo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"AVISO: Arquivo {nome_arquivo} não foi encontrado.")
        return {}

# Carrega todos os arquivos de configuração
empresa_map = carregar_arquivo_json('empresa_nome_map.json')
setor_map = carregar_arquivo_json('setor_map.json')

# Carrega as perguntas de referência do arquivo de texto
reference_templates = {}
try:
    caminho_ref_questions = os.path.join(SCRIPT_DIR, 'Reference_questions.txt')
    with open(caminho_ref_questions, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and ';' in line and not line.startswith('#'):
                template_id, question_text = line.split(';', 1)
                reference_templates[template_id.strip()] = question_text.strip()
except FileNotFoundError:
    print("AVISO: Arquivo Reference_questions.txt não encontrado.")

# Prepara o modelo de similaridade TF-IDF
ref_ids = list(reference_templates.keys())
ref_questions = list(reference_templates.values())
vectorizer = TfidfVectorizer()
tfidf_matrix_ref = vectorizer.fit_transform(ref_questions) if ref_questions else None


# --- FUNÇÕES AUXILIARES DE PROCESSAMENTO ---

def remover_acentos(texto):
    """Remove acentos e caracteres diacríticos de uma string. Ex: 'elétrico' -> 'eletrico'."""
    nfkd_form = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def extrair_entidades(pergunta_lower, template_id):
    """Extrai entidades fixas como empresa, data e setor."""
    entidades = {}
    pergunta_sem_acento = remover_acentos(pergunta_lower)

    # Extrai Nome da Empresa e o Termo de Busca Original
    sorted_empresa_keys = sorted(empresa_map.keys(), key=len, reverse=True)
    for key in sorted_empresa_keys:
        if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
            entidades['termo_busca_empresa'] = key
            entidades['entidade_nome'] = empresa_map[key]
            break

    # Extrai Nome do Setor
    sorted_setor_keys = sorted(setor_map.keys(), key=len, reverse=True)
    for key in sorted_setor_keys:
        if re.search(r'\b' + re.escape(remover_acentos(key.lower())) + r'\b', pergunta_sem_acento):
            entidades['nome_setor'] = setor_map[key]
            break

    # Extrai Data
    match_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', pergunta_lower)
    if match_data:
        dia, mes, ano = match_data.groups()
        entidades['data'] = f"{ano}-{mes}-{dia}"
            
    return entidades

def identificar_parametros_dinamicos(pergunta_lower):
    """Identifica qual propriedade buscar (seja de preço ou variação) e os parâmetros de ranking."""
    dados = {}
    pergunta_sem_acento = remover_acentos(pergunta_lower)
    
    # Mapeia palavras-chave para a chave do .properties
    mapa_metricas = {
        'metrica.variacao_abs': ['variacao intradiaria absoluta'],
        'metrica.variacao_perc': ['alta percentual', 'baixa percentual', 'variacao intradiaria percentual', 'percentual de alta', 'percentual de baixa'],
        'metrica.intervalo_abs': ['intervalo intradiario absoluto'],
        'metrica.intervalo_perc': ['intervalo intradiario percentual'],
        'metrica.variacao_abs_abs': ['menor variacao'],
        'metrica.preco_maximo': ['preço máximo', 'preco maximo'],
        'metrica.preco_minimo': ['preço mínimo', 'preco minimo'],
        'metrica.preco_fechamento': ['preço de fechamento', 'fechamento'],
        'metrica.preco_abertura': ['preço de abertura', 'abertura'],
        'metrica.preco_medio': ['preço médio', 'preco medio'],
        'metrica.quantidade': ['quantidade', 'total de negocios'],
        'metrica.volume': ['volume']
    }

    for chave_prop, sinonimos in mapa_metricas.items():
        for s in sinonimos:
            if remover_acentos(s) in pergunta_sem_acento:
                dados['valor_desejado'] = chave_prop
                break
        if 'valor_desejado' in dados:
            break

    # Detecção de Ordem
    dados['ordem'] = "DESC" # Padrão para "maior"
    if "baixa" in pergunta_sem_acento or "menor" in pergunta_sem_acento:
        dados['ordem'] = "ASC"
        
    # Detecção de Limite
    dados['limite'] = "1"
    if "cinco acoes" in pergunta_sem_acento or "cinco ações" in pergunta_lower:
        dados['limite'] = "5"
        
    return dados

# --- API FLASK ---
app = Flask(__name__)

@app.route('/process_question', methods=['POST'])
def process_question():
    data = request.get_json()
    pergunta_usuario_original = data.get('question', '')
    pergunta_lower = pergunta_usuario_original.lower()

    if not pergunta_lower.strip(): return jsonify({"error": "A pergunta não pode ser vazia."}), 400
    if not ref_questions: return jsonify({"error": "Sistema de NLP não inicializado."}), 500

    tfidf_usuario = vectorizer.transform([pergunta_lower])
    similaridades = cosine_similarity(tfidf_usuario, tfidf_matrix_ref).flatten()
    indice_melhor_similaridade = similaridades.argmax()
    template_id_final = ref_ids[indice_melhor_similaridade]

    # Bloco de Lógica de Refinamento
    ranking_keywords = ["qual ação", "maior alta", "maior baixa", "menor variacao", "cinco ações"]
    if any(keyword in pergunta_lower for keyword in ranking_keywords):
        template_id_final = 'Template_7A'
    elif "variacao intradiaria absoluta" in remover_acentos(pergunta_lower):
        template_id_final = 'Template_6A'

    # Extrai todas as entidades e parâmetros
    entidades_extraidas = extrair_entidades(pergunta_lower, template_id_final)
    parametros_dinamicos = identificar_parametros_dinamicos(pergunta_lower)
    entidades_extraidas.update(parametros_dinamicos) # Combina os dois dicionários

    # Prepara o payload final
    if 'termo_busca_empresa' in entidades_extraidas:
        entidades_extraidas['entidade_nome'] = entidades_extraidas['termo_busca_empresa']
    elif 'nome_setor' in entidades_extraidas:
        entidades_extraidas['nome_setor_busca'] = entidades_extraidas['nome_setor']

    entidades_maiusculas = {k.upper(): v for k, v in entidades_extraidas.items()}

    return jsonify({
        "templateId": template_id_final,
        "entities": entidades_maiusculas,
        "debugInfo": {
            "perguntaOriginal": pergunta_usuario_original,
            "templateEscolhidoPelaSimilaridade": ref_ids[indice_melhor_similaridade],
            "templateFinalAposRegras": template_id_final,
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)