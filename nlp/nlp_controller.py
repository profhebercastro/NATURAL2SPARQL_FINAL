import json
import re
import os
import unicodedata
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- CARREGAMENTO ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
def carregar_arquivo_json(nome_arquivo):
    caminho_completo = os.path.join(SCRIPT_DIR, nome_arquivo)
    try:
        with open(caminho_completo, 'r', encoding='utf-8') as f: return json.load(f)
    except FileNotFoundError: return {}

empresa_map = carregar_arquivo_json('Named_entity_dictionary.json')

reference_templates = {}
try:
    with open(os.path.join(SCRIPT_DIR, 'Reference_questions.txt'), 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() and ';' in line and not line.strip().startswith('#'):
                parts = line.split(';', 1)
                if len(parts) == 2:
                    template_id, question_text = parts
                    if template_id.strip() not in reference_templates:
                        reference_templates[template_id.strip()] = []
                    reference_templates[template_id.strip()].append(question_text.strip())
except FileNotFoundError:
    reference_templates = {}

ref_questions_flat = []
ref_ids_flat = []
for template_id, questions in reference_templates.items():
    for q in questions:
        ref_questions_flat.append(q)
        ref_ids_flat.append(template_id)

if ref_questions_flat:
    vectorizer = TfidfVectorizer()
    tfidf_matrix_ref = vectorizer.fit_transform(ref_questions_flat)
else:
    vectorizer = None
    tfidf_matrix_ref = None

# --- FUNÇÕES AUXILIARES ---
def remover_acentos(texto):
    nfkd_form = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def extrair_entidades_fixas(pergunta_lower):
    entidades = {}
    pergunta_sem_acento = remover_acentos(pergunta_lower)
    
    ticker_match = re.search(r'\b([a-zA-Z]{4}\d{1,2})\b', pergunta_lower)
    if ticker_match:
        entidades['entidade_nome'] = ticker_match.group(1).upper()
    else:
        sorted_empresa_keys = sorted(empresa_map.keys(), key=len, reverse=True)
        for key in sorted_empresa_keys:
            if re.search(r'\b' + re.escape(key.lower()) + r'\b', pergunta_lower):
                entidades['entidade_nome'] = key
                break
    
    setores_conhecidos = [
        "Bens Industriais", "Comunicações", "Consumo não Cíclico", "Consumo Cíclico", 
        "Financeiro", "Materiais Básicos", "Outros", "Petróleo. Gás e Biocombustíveis", 
        "Saúde", "Tecnologia da Informação", "Utilidade Pública", "Agropecuária", 
        "Água e Saneamento", "Alimentos Processados", "Automóveis e Motocicletas", 
        "Bebidas", "Comércio", "Comércio e Distribuição", "Computadores e Equipamentos", 
        "Construção Civil", "Construção e Engenharia", "Diversos", "Embalagens", 
        "Energia Elétrica", "Equipamentos", "Exploração de Imóveis", "Gás", 
        "Holdings Diversificadas", "Hoteis e Restaurantes", "Intermediários Financeiros", 
        "Madeira e Papel", "Materiais Diversos", "Material de Transporte", 
        "Medicamentos e Outros Produtos", "Mídia", "Mineração", "Petróleo. Gás e Biocombustíveis", 
        "Previdência e Seguros", "Produtos de Uso Pessoal e de Limpeza", 
        "Programas e Serviços", "Químicos", "Serv.Méd.Hospit..Análises e Diagnósticos", 
        "Serviços", "Serviços Financeiros Diversos", "Viagens e Lazer", 
        "Tecidos. Vestuário e Calçados", "Transporte", "Siderurgia e Metalurgia", 
        "Telecomunicações", "Utilidades Domésticas", "Acessórios", "Açucar e Alcool", 
        "Agricultura", "Alimentos", "Alimentos Diversos", "Aluguel de carros", 
        "Armas e Munições", "Artefatos de Ferro e Aço", "Artefatos de Cobre", "Bancos", 
        "Bicicletas", "Atividades Esportivas", "Calçados", "Brinquedos e Jogos", 
        "Cervejas e Refrigerantes", "Carnes e Derivados", "Construção Pesada", 
        "Corretoras de Seguros e Resseguros", "Eletrodomésticos", "Engenharia Consultiva", 
        "Equipamentos e Serviços", "Exploração. Refino e Distribuição", 
        "Exploração de Rodovias", "Hotelaria", "Incorporações", "Intermediação Imobiliária", 
        "Fios e Tecidos", "Fertilizantes e Defensivos", "Gestão de Recursos e Investimentos", 
        "Transporte Aéreo", "Viagens e Turismo", "Transporte Hidroviário", 
        "Utensílios Domésticos", "Transporte Rodoviário", "Transporte Ferroviário", 
        "Vestuário", "Produção de Eventos e Shows", "Serviços Diversos", 
        "Produtos Diversos", "Serviços Educacionais", "Seguradoras", 
        "Produtos de Limpeza", "Minerais Metálicos", "Petroquímicos", "Químicos Diversos", 
        "Siderurgia", "Produtos para Construção", "Resseguradoras", 
        "Motores . Compressores e Outros", "Serviços de Apoio e Armazenagem", 
        "Papel e Celulose", "Móveis", "Restaurante e Similares"
    ]
    
    setores_conhecidos.sort(key=len, reverse=True)
    for setor in setores_conhecidos:
        if re.search(r'\b' + re.escape(remover_acentos(setor.lower())) + r'\b', pergunta_sem_acento):
            entidades['nome_setor'] = setor
            break
    
    match_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', pergunta_lower)
    if match_data:
        dia, mes, ano = match_data.groups()
        entidades['data'] = f"{ano}-{mes}-{dia}"
            
    return entidades

def identificar_parametros_dinamicos(pergunta_lower):
    dados = {}
    pergunta_sem_acento = remover_acentos(pergunta_lower)
    mapa_metricas = {
        'calculo_intervalo_perc': ['intervalo intradiario percentual'],
        'calculo_variacao_abs': ['variacao intradiaria absoluta'],
        'calculo_variacao_perc': ['alta percentual', 'baixa percentual', 'percentual de alta', 'percentual de baixa'],
        'calculo_variacao_abs_abs': ['menor variacao'],
        'metrica.preco_maximo': ['preco maximo', 'preço máximo'],
        'metrica.preco_minimo': ['preco minimo', 'preço mínimo'],
        'metrica.preco_fechamento': ['preco de fechamento', 'fechamento'],
        'metrica.preco_abertura': ['preco de abertura', 'abertura'],
        'metrica.preco_medio': ['preco medio', 'preço médio'],
        'metrica.quantidade': ['quantidade', 'total de negocios'],
        'metrica.volume': ['volume'],
    }
    for chave, sinonimos in mapa_metricas.items():
        if 'calculo' in dados or 'valor_desejado' in dados: break
        for s in sinonimos:
            if remover_acentos(s) in pergunta_sem_acento:
                if chave.startswith('calculo_'): dados['calculo'] = chave.replace('calculo_', '')
                else: dados['valor_desejado'] = chave
                break 
    if "ordinaria" in pergunta_sem_acento: dados["regex_pattern"] = "3$"
    elif "preferencial" in pergunta_sem_acento: dados["regex_pattern"] = "[456]$"
    elif "unit" in pergunta_sem_acento: dados["regex_pattern"] = "11$"
    dados['ordem'] = "DESC"
    if "baixa" in pergunta_sem_acento or "menor" in pergunta_sem_acento: dados['ordem'] = "ASC"
    dados['limite'] = "1"
    if "cinco acoes" in pergunta_sem_acento or "cinco ações" in pergunta_lower: dados['limite'] = "5"
    return dados

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
    if tfidf_matrix_ref is not None and len(ref_questions_flat) > 0:
        tfidf_usuario = vectorizer.transform([pergunta_lower])
        similaridades = cosine_similarity(tfidf_usuario, tfidf_matrix_ref).flatten()
        if similaridades.any(): template_id_final = ref_ids_flat[similaridades.argmax()]
        else: return jsonify({"error": "Não foi possível encontrar similaridade."}), 404
    else:
        return jsonify({"error": "Nenhum template de referência carregado."}), 500
    if not template_id_final:
        return jsonify({"error": "Não foi possível identificar um template para a pergunta."}), 404
    entidades_extraidas = extrair_entidades_fixas(pergunta_lower)
    parametros_dinamicos = identificar_parametros_dinamicos(pergunta_lower)
    entidades_extraidas.update(parametros_dinamicos)
    entidades_maiusculas = {k.upper(): v for k, v in entidades_extraidas.items()}
    return jsonify({"templateId": template_id_final, "entities": entidades_maiusculas})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)