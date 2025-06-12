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

# --- Configuração do Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - PLN - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger("PLN_Processor")

def exit_with_error(message):
    """Função centralizada para encerrar o script com um erro JSON."""
    logger.error(message)
    print(json.dumps({"error": message}))
    sys.exit(1)

# --- Carregamento de Recursos (Usando Caminhos Absolutos) ---
try:
    # Descobre o diretório onde este script (pln_processor.py) está.
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    logger.info(f"Diretório do script PLN detectado: {SCRIPT_DIR}")
    
    # Constrói os caminhos a partir do diretório do script
    MAPA_EMPRESAS_PATH = os.path.join(SCRIPT_DIR, "empresa_nome_map.json")
    PERGUNTAS_PATH = os.path.join(SCRIPT_DIR, "perguntas_de_interesse.txt")
    
    # Carregamento do modelo spaCy (assume que foi pré-baixado pelo Build Command)
    nlp = spacy.load("pt_core_news_sm")
    logger.info("Modelo spaCy 'pt_core_news_sm' carregado.")

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
    exit_with_error(f"Arquivo de recurso não encontrado: {e}. Verifique os caminhos e o CWD.")
except Exception as e:
    exit_with_error(f"Falha crítica na inicialização do PLN: {e}")

# --- Funções de Processamento ---
def normalizar_texto(texto):
    if not texto: return ""
    texto = texto.lower()
    # Mantenha sua lógica completa de normalização aqui se necessário
    texto = re.sub(r'[áàâãä]', 'a', texto)
    texto = re.sub(r'[éèêë]', 'e', texto)
    texto = re.sub(r'[íìîï]', 'i', texto)
    texto = re.sub(r'[óòôõö]', 'o', texto)
    texto = re.sub(r'[úùûü]', 'u', texto)
    texto = re.sub(r'ç', 'c', texto)
    texto = re.sub(r'[^a-z0-9\s]', '', texto)
    return ' '.join(texto.split())

def selecionar_template(pergunta_usuario):
    pergunta_norm = normalizar_texto(pergunta_usuario)
    textos_perguntas = [normalizar_texto(p['text']) for p in PERGUNTAS_DE_INTERESSE]
    matches = get_close_matches(pergunta_norm, textos_perguntas, n=1, cutoff=0.6)
    if matches:
        for p in PERGUNTAS_DE_INTERESSE:
            if normalizar_texto(p['text']) == matches[0]: return p['id']
    return None

def extrair_entidades(doc):
    entidades = {}
    # Extrair Data
    match_data = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', doc.text)
    if match_data:
        try:
            data_str = match_data.group(1).replace('-', '/')
            dt_obj = datetime.strptime(data_str, '%d/%m/%Y') if len(data_str.split('/')[-1]) == 4 else datetime.strptime(data_str, '%d/%m/%y')
            entidades['date'] = dt_obj.strftime('%Y-%m-%d')
        except ValueError:
            logger.warning(f"Formato de data não reconhecido: '{match_data.group(1)}'")

    # Extrair Empresa (simplificado para robustez)
    nome_empresa_encontrado = None
    # 1. Tenta com NER
    for ent in doc.ents:
        if ent.label_ == 'ORG' and ent.text.upper() in EMPRESA_MAP:
            nome_empresa_encontrado = EMPRESA_MAP[ent.text.upper()]
            break
    # 2. Se não achou, tenta com keyword
    if not nome_empresa_encontrado:
        for nome_mapa, nome_ontologia in EMPRESA_MAP.items():
            if nome_mapa.lower() in doc.text.lower():
                nome_empresa_encontrado = nome_ontologia
                break
    # 3. Se ainda não achou, procura por padrão de ticker
    if not nome_empresa_encontrado:
        match_ticker = re.search(r'\b([A-Z]{4}\d{1,2})\b', doc.text.upper())
        if match_ticker:
             nome_empresa_encontrado = match_ticker.group(1)
    
    if nome_empresa_encontrado:
        entidades['company'] = nome_empresa_encontrado

    return entidades

def main(pergunta_usuario):
    """Função principal que orquestra o processo de PLN."""
    logger.info(f"Iniciando processamento para: '{pergunta_usuario}'")
    doc = nlp(pergunta_usuario)
    
    template_id = selecionar_template(pergunta_usuario)
    if not template_id:
        exit_with_error("Não foi possível entender a intenção da sua pergunta.")
        
    entidades = extrair_entidades(doc)
    
    # Validação simples para garantir que as entidades necessárias foram encontradas
    if template_id == "Template_1A" and not all(k in entidades for k in ['company', 'date']):
        exit_with_error("Para essa pergunta, são necessários um nome de empresa e uma data.")

    if not entidades:
        exit_with_error("Não foi possível extrair nenhuma informação útil da pergunta.")

    resposta = {"template_id": template_id, "entities": entidades}
    print(json.dumps(resposta, ensure_ascii=False))
    logger.info("Processamento PLN concluído com sucesso.")

# --- Ponto de Entrada do Script ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        exit_with_error("Nenhuma pergunta fornecida como argumento.")
    
    pergunta_completa = " ".join(sys.argv[1:])
    main(pergunta_completa)