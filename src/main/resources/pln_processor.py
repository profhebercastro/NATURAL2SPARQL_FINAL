# Arquivo: pln_processor.py
# Local: src/main/resources/

import spacy
import sys
import json
import os
import logging
import re
from difflib import get_close_matches
from datetime import datetime

# --- Configuração ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - PLN - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger("PLN_Processor")

def exit_with_error(message):
    logger.error(message)
    print(json.dumps({"erro": message}))
    sys.exit(1)

# --- Carregamento de Recursos ---
try:
    # Constrói caminhos a partir do local do próprio script
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    logger.info(f"Diretório do script PLN detectado: {SCRIPT_DIR}")
    
    MAPA_EMPRESAS_PATH = os.path.join(SCRIPT_DIR, "empresa_nome_map.json")
    PERGUNTAS_PATH = os.path.join(SCRIPT_DIR, "perguntas_de_interesse.txt")
    
    # Carregamento do modelo spaCy
    nlp = spacy.load("pt_core_news_sm")
    
    # Carregamento dos mapas e listas
    with open(MAPA_EMPRESAS_PATH, 'r', encoding='utf-8') as f:
        EMPRESA_MAP = json.load(f)
    
    PERGUNTAS_DE_INTERESSE = []
    with open(PERGUNTAS_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                parts = line.strip().split(';', 1)
                if len(parts) == 2:
                    PERGUNTAS_DE_INTERESSE.append({"id": parts[0].strip(), "text": parts[1].strip()})
    
    logger.info("Recursos do PLN carregados com sucesso.")
except FileNotFoundError as e:
    exit_with_error(f"Arquivo de recurso não encontrado: {e}. Verifique o caminho.")
except Exception as e:
    exit_with_error(f"Falha na inicialização do PLN: {e}")

# --- Funções de Processamento ---
def normalizar_texto(texto):
    if not texto: return ""
    texto = texto.lower()
    texto = re.sub(r'[áàâãä]', 'a', texto); texto = re.sub(r'[éèêë]', 'e', texto)
    texto = re.sub(r'[íìîï]', 'i', texto); texto = re.sub(r'[óòôõö]', 'o', texto)
    texto = re.sub(r'[úùûü]', 'u', texto); texto = re.sub(r'ç', 'c', texto)
    texto = re.sub(r'[^a-z0-9\s]', '', texto)
    return ' '.join(texto.split())

def selecionar_template(pergunta_usuario):
    pergunta_norm = normalizar_texto(pergunta_usuario)
    textos_perguntas = [normalizar_texto(p['text']) for p in PERGUNTAS_DE_INTERESSE]
    matches = get_close_matches(pergunta_norm, textos_perguntas, n=1, cutoff=0.6)
    if matches:
        for p in PERGUNTAS_DE_INTERESSE:
            if normalizar_texto(p['text']) == matches[0]:
                return p['id'].replace(" ", "_")
    return None

def extrair_entidades(doc):
    mapeamentos = {}
    
    # Data
    match_data = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', doc.text)
    if match_data:
        try:
            data_str = match_data.group(1).replace('-', '/')
            dt_obj = datetime.strptime(data_str, '%d/%m/%Y') if len(data_str.split('/')[-1]) == 4 else datetime.strptime(data_str, '%d/%m/%y')
            mapeamentos["#DATA#"] = dt_obj.strftime('%Y-%m-%d')
        except ValueError: pass

    # Empresa/Ticker
    nome_empresa_encontrado = None
    # 1. Tenta com NER
    for ent in doc.ents:
        if ent.label_ == 'ORG' and ent.text.upper() in EMPRESA_MAP:
            nome_empresa_encontrado = EMPRESA_MAP[ent.text.upper()]
            break
    # 2. Se não, tenta por keyword
    if not nome_empresa_encontrado:
        for nome_mapa, nome_ontologia in EMPRESA_MAP.items():
            if nome_mapa.lower() in doc.text.lower():
                nome_empresa_encontrado = nome_ontologia
                break
    # 3. Se ainda não, procura por padrão de ticker
    if not nome_empresa_encontrado:
        match_ticker = re.search(r'\b([A-Z]{4}\d{1,2})\b', doc.text.upper())
        if match_ticker: nome_empresa_encontrado = match_ticker.group(1)
    
    if nome_empresa_encontrado:
        mapeamentos["#ENTIDADE_NOME#"] = nome_empresa_encontrado

    # Tipo de Preço
    texto_norm = normalizar_texto(doc.text)
    if 'fechamento' in texto_norm: mapeamentos["#VALOR_DESEJADO#"] = 'b3:precoFechamento'
    elif 'abertura' in texto_norm: mapeamentos["#VALOR_DESEJADO#"] = 'b3:precoAbertura'
    elif 'maximo' in texto_norm or 'maxima' in texto_norm: mapeamentos["#VALOR_DESEJADO#"] = 'b3:precoMaximo'
    elif 'minimo' in texto_norm or 'minima' in texto_norm: mapeamentos["#VALOR_DESEJADO#"] = 'b3:precoMinimo'

    # Setor
    if 'setor' in texto_norm:
        match_setor = re.search(r'setor\s+(?:de\s+|do\s+|da\s+)?([\w\s]+)', texto_norm)
        if match_setor:
            mapeamentos["#SETOR#"] = match_setor.group(1).strip().title()

    return mapeamentos

def main(pergunta_usuario):
    doc = nlp(pergunta_usuario)
    template_id = selecionar_template(pergunta_usuario)
    if not template_id: exit_with_error("Não foi possível entender a intenção da pergunta.")
    
    mapeamentos = extrair_entidades(doc)
    if not mapeamentos: exit_with_error("Não foi possível extrair informações da pergunta.")

    resposta = {"template_nome": template_id, "mapeamentos": mapeamentos}
    print(json.dumps(resposta, ensure_ascii=False))
    logger.info("Processamento PLN concluído.")

# --- Ponto de Entrada ---
if __name__ == "__main__":
    if len(sys.argv) < 2: exit_with_error("Nenhuma pergunta fornecida.")
    main(" ".join(sys.argv[1:]))