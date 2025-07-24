import json
import re
import os
import unicodedata
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- CARREGAMENTO ---
# ... (código de carregamento sem alterações) ...

# --- FUNÇÕES AUXILIARES ---
def remover_acentos(texto):
    nfkd_form = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def extrair_todas_entidades(pergunta_lower):
    entidades = {}
    texto_restante = ' ' + pergunta_lower + ' '
    
    # Etapa 1: Extrair Data e remover da string de trabalho
    match_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', texto_restante)
    if match_data:
        dia, mes, ano = match_data.groups()
        entidades['data'] = f"{ano}-{mes}-{dia}"
        texto_restante = texto_restante.replace(match_data.group(0), "")

    # Etapa 2: Extrair Métricas e Cálculos e remover da string de trabalho
    mapa_metricas = {
        'calculo_variacao_perc': ['percentual de alta', 'percentual de baixa', 'variacao intradiaria percentual', 'variacao percentual'],
        'calculo_variacao_abs': ['variacao intradiaria absoluta', 'variacao absoluta'],
        'calculo_intervalo_perc': ['intervalo intradiaria percentual', 'intervalo percentual'],
        'calculo_intervalo_abs': ['intervalo intradiario absoluto', 'intervalo absoluto'],
        'calculo_variacao_abs_abs': ['menor variacao'],
        'metrica.preco_maximo': ['preco maximo', 'preço máximo'],
        'metrica.preco_minimo': ['preco minimo', 'preço mínimo'],
        'metrica.preco_fechamento': ['preco de fechamento', 'fechamento'],
        'metrica.preco_abertura': ['preco de abertura', 'abertura'],
        'metrica.preco_medio': ['preco medio', 'preço médio'],
        'metrica.quantidade': ['quantidade', 'total de negocios'],
        'metrica.volume': ['volume'],
    }
    
    texto_sem_acento = remover_acentos(texto_restante)
    # Prioriza a busca por termos de cálculo
    for chave in sorted(mapa_metricas.keys(), key=lambda k: not k.startswith('calculo_')):
        sinonimos = mapa_metricas[chave]
        for s in sinonimos:
            if re.search(r'\b' + remover_acentos(s) + r'\b', texto_sem_acento):
                if chave.startswith('calculo_'):
                    entidades['calculo'] = chave.replace('calculo_', '')
                else:
                    entidades['valor_desejado'] = chave
                # Remove a primeira palavra do sinônimo para evitar que seja confundida com uma entidade
                texto_restante = re.sub(r'\b' + s.split()[0] + r'\b', '', texto_restante, flags=re.IGNORECASE)
                break
        if 'calculo' in entidades or 'valor_desejado' in entidades:
            break

    # Etapa 3: Extrair Ticker (se houver) e remover
    ticker_match = re.search(r'\b([A-Z0-9]{5,6})\b', texto_restante.upper())
    if ticker_match:
        entidades['entidade_nome'] = ticker_match.group(1)
        texto_restante = re.sub(r'\b' + ticker_match.group(1) + r'\b', '', texto_restante, flags=re.IGNORECASE)

    # Etapa 4: Extrair Setor e remover
    sorted_setor_keys = sorted(setor_map.keys(), key=len, reverse=True)
    for key in sorted_setor_keys:
        if re.search(r'\b' + re.escape(remover_acentos(key.lower())) + r'\b', remover_acentos(texto_restante)):
            entidades['nome_setor'] = setor_map[key]
            texto_restante = re.sub(r'\b' + re.escape(key.lower()) + r'\b', '', texto_restante, flags=re.IGNORECASE)
            break
            
    # Etapa 5: Extrair Nome da Empresa do que sobrou (se Ticker não foi encontrado)
    if 'entidade_nome' not in entidades:
        sorted_empresa_keys = sorted(empresa_map.keys(), key=len, reverse=True)
        for key in sorted_empresa_keys:
            if re.search(r'\b' + re.escape(key.lower()) + r'\b', texto_restante):
                entidades['entidade_nome'] = key
                break
                
    # Etapa 6: Extrair parâmetros restantes da pergunta original
    pergunta_sem_acento_original = remover_acentos(pergunta_lower)
    if "ordinaria" in pergunta_sem_acento_original: entidades["regex_pattern"] = "3$"
    elif "preferencial" in pergunta_sem_acento_original: entidades["regex_pattern"] = "[456]$"
    elif "unit" in pergunta_sem_acento_original: entidades["regex_pattern"] = "11$"
    
    entidades['ordem'] = "DESC"
    if "baixa" in pergunta_sem_acento_original or "menor" in pergunta_sem_acento_original: entidades['ordem'] = "ASC"
    
    entidades['limite'] = "1"
    if "cinco acoes" in pergunta_sem_acento_original or "cinco ações" in pergunta_lower: entidades['limite'] = "5"
    elif "3 acoes" in pergunta_sem_acento_original or "3 ações" in pergunta_lower: entidades['limite'] = "3"

    return entidades

# --- API FLASK ---
app = Flask(__name__)
@app.route('/process_question', methods=['POST'])
def process_question():
    data = request.get_json()
    if not data or 'question' not in data:
        return jsonify({"error": "Payload inválido."}), 400
    pergunta_lower = data.get('question', '').lower()
    if not pergunta_lower.strip(): 
        return jsonify({"error": "A pergunta não pode ser vazia."}), 400
        
    # =======================================================
    #  !!! LÓGICA DE SELEÇÃO DE TEMPLATE CORRIGIDA !!!
    # =======================================================
    entidades_preliminares = extrair_todas_entidades(pergunta_lower)

    # Lógica customizada para escolher o template certo
    if 'nome_setor' in entidades_preliminares and 'valor_desejado' in entidades_preliminares:
        template_id_final = 'Template_4C' # Agregação por setor
    else: # Usa a lógica de similaridade para os outros casos
        if tfidf_matrix_ref is not None and len(ref_questions_flat) > 0:
            tfidf_usuario = vectorizer.transform([pergunta_lower])
            similaridades = cosine_similarity(tfidf_usuario, tfidf_matrix_ref).flatten()
            if similaridades.any(): 
                template_id_final = ref_ids_flat[similaridades.argmax()]
            else: 
                return jsonify({"error": "Não foi possível encontrar similaridade."}), 404
        else:
            return jsonify({"error": "Nenhum template de referência carregado."}), 500

    if not template_id_final:
        return jsonify({"error": "Não foi possível identificar um template para a pergunta."}), 404

    entidades_maiusculas = {k.upper(): v for k, v in entidades_preliminares.items()}
    return jsonify({"templateId": template_id_final, "entities": entidades_maiusculas})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)