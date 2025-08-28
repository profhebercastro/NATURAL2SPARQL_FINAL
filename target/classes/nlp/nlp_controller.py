import json
import re
import os
import unicodedata
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- CARREGAMENTO DOS ARTEFATOS DE CONHECIMENTO ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def carregar_arquivo_json(nome_arquivo):
    caminho_completo = os.path.join(SCRIPT_DIR, nome_arquivo)
    try:
        with open(caminho_completo, 'r', encoding='utf-8') as f: return json.load(f)
    except FileNotFoundError:
        print(f"AVISO: Arquivo {nome_arquivo} não encontrado em {caminho_completo}.")
        return {}

empresa_map = carregar_arquivo_json('Named_entity_dictionary.json')
setor_map = carregar_arquivo_json('sector_map.json')
index_map = carregar_arquivo_json('index_map.json')

reference_templates = {}
try:
    with open(os.path.join(SCRIPT_DIR, 'Reference_questions.txt'), 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and ';' in line and not line.startswith('#'):
                template_id, question_text = [part.strip() for part in line.split(';', 1)]
                if template_id not in reference_templates:
                    reference_templates[template_id] = []
                reference_templates[template_id].append(question_text)
except FileNotFoundError:
    print("AVISO: Arquivo Reference_questions.txt não encontrado.")

ref_questions_flat = [q for questions in reference_templates.values() for q in questions]
ref_ids_flat = [tid for tid, questions in reference_templates.items() for _ in questions]

if ref_questions_flat:
    vectorizer = TfidfVectorizer()
    tfidf_matrix_ref = vectorizer.fit_transform(ref_questions_flat)
else:
    vectorizer, tfidf_matrix_ref = None, None

# --- FUNÇÕES AUXILIARES DE PROCESSAMENTO DE TEXTO ---

def remover_acentos(texto):
    nfkd_form = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def extrair_todas_entidades(pergunta_lower):
    entidades = {}
    texto_restante = ' ' + pergunta_lower + ' '
    
    # 1. Datas
    match_data = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', texto_restante)
    if match_data:
        dia, mes, ano = match_data.groups()
        entidades['data'] = f"{ano}-{mes.zfill(2)}-{dia.zfill(2)}"
        texto_restante = texto_restante.replace(match_data.group(0), " ")

    # 2. Limites numéricos
    limit_match = re.search(r'\b(as|os)?\s*(\d+|cinco|tres|três|duas|dois|quatro)\s+(acoes|ações|papeis|papéis)\b', texto_restante, re.IGNORECASE)
    num_map = {'cinco': '5', 'quatro': '4', 'tres': '3', 'três': '3', 'duas': '2', 'dois': '2'}
    if limit_match:
        num_str = limit_match.group(2).lower()
        entidades['limite'] = num_map.get(num_str, num_str)
    elif re.search(r'\btop\s*(\d+)\b', texto_restante, re.IGNORECASE):
        entidades['limite'] = re.search(r'\btop\s*(\d+)\b', texto_restante, re.IGNORECASE).group(1)
    
    texto_sem_acento = remover_acentos(texto_restante)
    
    # 3. Métricas (com prioridade para ranking)
    mapa_ranking = {
        'variacao_perc': [
            'maior percentual de alta', 'maior alta percentual',
            'maior percentual de baixa', 'maior baixa percentual',
            'menor variacao percentual', 'menor variação percentual',
            'maior variacao percentual', 'maior variação percentual'  # <-- CORREÇÃO APLICADA AQUI
        ],
        'variacao_abs': [
            'maior baixa absoluta', 'menor variacao absoluta',
            'menor variação absoluta', 'maior variacao absoluta',
            'maior variação absoluta'
        ],
        'volume': ['maior volume', 'menor volume'],
    }
    mapa_metricas = {
        'variacao_perc': ['variacao intradiaria percentual', 'variação intradiária percentual'], 'variacao_abs': ['variacao intradiaria absoluta', 'variação intradiária absoluta'],
        'intervalo_perc': ['intervalo intradiario percentual', 'intervalo intradiário percentual'], 'intervalo_abs': ['intervalo intradiario absoluto', 'intervalo intradiário absoluto'],
        'preco_fechamento': ['preco de fechamento', 'preço de fechamento'], 'preco_abertura': ['preco de abertura', 'preço de abertura'],
        'preco_maximo': ['preco maximo', 'preço máximo'], 'preco_minimo': ['preco minimo', 'preço mínimo'], 'preco_medio': ['preco medio', 'preço médio'],
        'volume': ['volume'], 'quantidade': ['quantidade de negocios', 'quantidade de negócios'], 'ticker': ['ticker', 'codigo de negociacao', 'código de negociação', 'simbolo']
    }
    
    for chave, sinonimos in mapa_ranking.items():
        if any(re.search(r'\b' + remover_acentos(s) + r'\b', texto_sem_acento) for s in sinonimos):
            entidades['ranking_calculation'] = chave; break
            
    for chave, sinonimos in mapa_metricas.items():
        if any(re.search(r'\b' + remover_acentos(s) + r'\b', texto_sem_acento) for s in sinonimos):
            if chave.startswith(('variacao', 'intervalo')):
                entidades.setdefault('calculo', chave)
            else:
                entidades.setdefault('valor_desejado', 'metrica.' + chave)
            break

    if 'ranking_calculation' in entidades and not ('calculo' in entidades or 'valor_desejado' in entidades):
        entidades['valor_desejado'] = 'metrica.' + entidades['ranking_calculation']

    # 4. Entidades principais (com lógica de conversão de índice)
    entidade_principal_encontrada = False
    for key, tickers in index_map.items():
        if re.search(r'\b(no|do|da|de|entre as|do indice|acoes do)?\s*' + re.escape(key.lower()) + r'\b', remover_acentos(texto_restante)):
            entidades['lista_tickers'] = tickers
            entidade_principal_encontrada = True
            break
    
    if not entidade_principal_encontrada:
        for key, setor in setor_map.items():
            if re.search(r'\b' + re.escape(remover_acentos(key.lower())) + r'\b', remover_acentos(texto_restante)):
                entidades['nome_setor'] = setor
                entidade_principal_encontrada = True
                break
    
    if not entidade_principal_encontrada:
        ticker_match = re.search(r'\b([A-Z]{4}[0-9]{1,2})\b', texto_restante.upper())
        if ticker_match:
            entidades['entidade_nome'] = ticker_match.group(1); entidades['tipo_entidade'] = 'ticker'
        else:
            for key in sorted(empresa_map.keys(), key=len, reverse=True):
                if re.search(r'\b' + re.escape(key.lower()) + r'\b', remover_acentos(texto_restante)):
                    entidades['entidade_nome'] = key; entidades['tipo_entidade'] = 'nome'; break

    # 5. Filtros e defaults
    pergunta_sem_acento_original = remover_acentos(pergunta_lower)
    if "ordinaria" in pergunta_sem_acento_original: entidades["regex_pattern"] = "3$"
    elif "preferencial" in pergunta_sem_acento_original: entidades["regex_pattern"] = "[456]$"
    elif "unit" in pergunta_sem_acento_original: entidades["regex_pattern"] = "11$"
    
    entidades.setdefault('ordem', 'DESC' if "baixa" not in pergunta_lower and "menor" not in pergunta_lower else "ASC")
    entidades.setdefault('limite', '1')
    return entidades

app = Flask(__name__)
@app.route('/process_question', methods=['POST'])
def process_question():
    data = request.get_json(); pergunta_lower = data.get('question', '').lower()
    if not pergunta_lower.strip(): return jsonify({"error": "A pergunta não pode ser vazia."}), 400
        
    entidades = extrair_todas_entidades(pergunta_lower)
    
    # Flags de decisão para clareza
    has_ranking = 'ranking_calculation' in entidades
    has_calculo = 'calculo' in entidades
    has_entidade_nome = 'entidade_nome' in entidades
    has_filtro_grupo = 'nome_setor' in entidades or 'lista_tickers' in entidades
    has_valor_desejado = 'valor_desejado' in entidades
    is_complex_ranking = has_ranking and has_valor_desejado and entidades['valor_desejado'] != 'metrica.' + entidades['ranking_calculation']
    
    template_id_final = None

    # Lógica de Decisão Hierárquica
    if is_complex_ranking:
        template_id_final = 'Template_6B' if has_filtro_grupo else 'Template_6A'
    elif has_ranking:
        template_id_final = 'Template_5B' if has_filtro_grupo else 'Template_5A'
    elif has_valor_desejado and entidades['valor_desejado'] == 'metrica.ticker':
        template_id_final = 'Template_2'
    elif has_filtro_grupo:
        if 'empresas' in pergunta_lower: template_id_final = 'Template_3B'
        elif has_valor_desejado: template_id_final = 'Template_4'
        else: template_id_final = 'Template_3A'
    elif has_entidade_nome:
        if has_calculo: template_id_final = 'Template_1D' # Nome antigo: Template_6
        elif 'regex_pattern' in entidades: template_id_final = 'Template_1C' # Nome antigo: Template_5
        elif has_valor_desejado:
            template_id_final = 'Template_1B' if entidades.get('tipo_entidade') == 'ticker' else 'Template_1A'
        else:
             template_id_final = 'Template_2' # Default para nome de empresa é buscar o ticker
    
    # Fallback por similaridade se nenhuma regra se aplicar
    if not template_id_final and vectorizer:
        similaridades = cosine_similarity(vectorizer.transform([pergunta_lower]), tfidf_matrix_ref).flatten()
        if similaridades.any() and similaridades.max() > 0.3:
            template_id_final = ref_ids_flat[similaridades.argmax()]

    if not template_id_final: return jsonify({"error": "Não foi possível identificar um template para a pergunta."}), 404
    
    # Ajuste final: garante que 'calculo' seja populado para rankings simples
    if template_id_final in ['Template_5A', 'Template_5B']:
        if 'ranking_calculation' in entidades:
            entidades.setdefault('calculo', entidades['ranking_calculation'])
        elif 'valor_desejado' in entidades:
            entidades.setdefault('calculo', entidades['valor_desejado'].replace('metrica.', ''))
    
    return jsonify({"templateId": template_id_final, "entities": {k.upper(): v for k, v in entidades.items()}})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)