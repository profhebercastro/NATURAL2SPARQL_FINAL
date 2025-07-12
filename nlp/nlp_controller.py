import json
import re
import os
import unicodedata # Importa a biblioteca necessária para remover acentos
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
thesaurus = carregar_arquivo_json('synonym_dictionary.json')
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
    """Extrai entidades específicas (empresa, data, setor, etc.) e retorna um dicionário."""
    entidades = {}
    pergunta_sem_acento = remover_acentos(pergunta_lower)

    # Extração de Empresa
    sorted_empresa_keys = sorted(empresa_map.keys(), key=len, reverse=True)
    for key in sorted_empresa_keys:
        if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
            entidades['termo_busca_empresa'] = key
            entidades['entidade_nome'] = empresa_map[key]
            break

    # Extração de Setor (com remoção de acentos para robustez)
    sorted_setor_keys = sorted(setor_map.keys(), key=len, reverse=True)
    for key in sorted_setor_keys:
        if re.search(r'\b' + re.escape(remover_acentos(key.lower())) + r'\b', pergunta_sem_acento):
            entidades['nome_setor'] = setor_map[key]
            break

    # Extração de Data
    match_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', pergunta_lower)
    if match_data:
        dia, mes, ano = match_data.groups()
        entidades['data'] = f"{ano}-{mes}-{dia}"

    # Lógica para o filtro de tipo de ação
    if template_id == 'Template_5B':
        if "ordinária" in pergunta_sem_acento: entidades["regex_pattern"] = "3$"
        elif "preferencial" in pergunta_sem_acento: entidades["regex_pattern"] = "[456]$"
        elif "unit" in pergunta_sem_acento: entidades["regex_pattern"] = "11$"
            
    return entidades

def identificar_metrica_canonico(pergunta_lower):
    """Identifica a métrica na pergunta de forma robusta, usando um mapa interno."""
    mapa_metricas = {
        'preco_maximo': ['preço máximo', 'preco maximo', 'máximo'],
        'preco_minimo': ['preço mínimo', 'preco minimo', 'mínimo'],
        'preco_fechamento': ['preço de fechamento', 'fechamento'],
        'preco_abertura': ['preço de abertura', 'abertura'],
        'preco_medio': ['preço médio', 'preco medio'],
        'quantidade': ['quantidade', 'quantidade de ações', 'total de negocios'],
        'volume': ['volume']
    }
    pergunta_sem_acento = remover_acentos(pergunta_lower)
    for canonico, sinonimos in mapa_metricas.items():
        for s in sinonimos:
            if remover_acentos(s) in pergunta_sem_acento:
                return canonico
    return None

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

    # --- INÍCIO: Bloco de Lógica de Refinamento CORRIGIDO ---
    
    # PRIORIDADE 1 (Mais específica): A pergunta é sobre o VOLUME de um SETOR?
    if "volume" in pergunta_lower and "setor" in pergunta_lower:
        template_id_final = 'Template_4A'
    
    # PRIORIDADE 2: A pergunta contém um TIPO de ação?
    elif "ordinária" in pergunta_lower or "preferencial" in pergunta_lower or "unit" in pergunta_lower:
        template_id_final = 'Template_5B'
    
    # PRIORIDADE 3: A pergunta é sobre QUANTIDADE negociada?
    elif "quantidade" in pergunta_lower and "negociadas" in pergunta_lower:
        template_id_final = 'Template_4B'
        
    # PRIORIDADE 4: A pergunta usa a frase "da ação da"?
    elif "da ação da" in pergunta_lower:
        template_id_final = 'Template_5A'
        
    # Se nenhuma regra específica for acionada, a escolha da similaridade é mantida.
    # --- FIM: Bloco de Lógica de Refinamento ---

    entidades_extraidas = extrair_entidades(pergunta_lower, template_id_final)
    
    metrica_canonico = identificar_metrica_canonico(pergunta_lower)
    if metrica_canonico:
        entidades_extraidas['valor_desejado'] = f'metrica.{metrica_canonico}'

    if 'termo_busca_empresa' in entidades_extraidas:
        entidades_extraidas['entidade_nome'] = entidades_extraidas['termo_busca_empresa']
    elif 'nome_setor' in entidades_extraidas:
        entidades_extraidas['nome_setor'] = entidades_extraidas['nome_setor']

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