# Arquivo: pln_processor.py
# Versão simplificada e corrigida, baseada no seu script original

import spacy
import sys
import json
import os
import logging
import re
from difflib import get_close_matches
from datetime import datetime

# --- 1. CONFIGURAÇÃO ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - PLN - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger("PLN_Processor")

def exit_with_error(message):
    print(json.dumps({"erro": message}))
    sys.exit(1)

# --- 2. CARREGAMENTO DE RECURSOS ---
try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    nlp = spacy.load("pt_core_news_sm")
    
    with open(os.path.join(SCRIPT_DIR, "empresa_nome_map.json"), 'r', encoding='utf-8') as f:
        EMPRESA_MAP = json.load(f)
    
    PERGUNTAS_INTERESSE = []
    with open(os.path.join(SCRIPT_DIR, "perguntas_de_interesse.txt"), 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                parts = line.strip().split(';', 1)
                if len(parts) == 2:
                    PERGUNTAS_INTERESSE.append({"id": parts[0].strip(), "text": parts[1].strip()})

except Exception as e:
    exit_with_error(f"Erro crítico ao carregar recursos do PLN: {e}")

# --- 3. FUNÇÕES DE PROCESSAMENTO ---

def selecionar_template(pergunta_usuario):
    """Usa get_close_matches para encontrar o template mais similar."""
    pergunta_norm = pergunta_usuario.lower()
    textos_perguntas = [p['text'].lower() for p in PERGUNTAS_INTERESSE]
    matches = get_close_matches(pergunta_norm, textos_perguntas, n=1, cutoff=0.6)
    
    if matches:
        for p in PERGUNTAS_INTERESSE:
            if p['text'].lower() == matches[0]:
                return p['id'].replace(" ", "_")
    return None

def extrair_entidades(doc):
    """Extrai as entidades da pergunta de forma mais direta."""
    mapeamentos = {}
    texto_lower = doc.text.lower()

    # Data
    match_data = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', doc.text)
    if match_data:
        try:
            data_str = match_data.group(1).replace('-', '/')
            dt_obj = datetime.strptime(data_str, '%d/%m/%Y' if len(data_str.split('/')[-1]) == 4 else '%d/%m/%y')
            mapeamentos["#DATA#"] = dt_obj.strftime('%Y-%m-%d')
        except ValueError: pass

    # Empresa (Prioriza ticker, depois busca por nome)
    nome_empresa = None
    match_ticker = re.search(r'\b([A-Z]{4}\d{1,2})\b', doc.text.upper())
    if match_ticker:
        nome_empresa = match_ticker.group(1)
    else:
        for nome_mapa, nome_ontologia in EMPRESA_MAP.items():
            if nome_mapa.lower() in texto_lower:
                nome_empresa = nome_ontologia
                break
    if nome_empresa:
        mapeamentos["#ENTIDADE_NOME#"] = nome_empresa

    # Tipo de Preço (Valor Desejado)
    if 'fechamento' in texto_lower: mapeamentos["#VALOR_DESEJADO#"] = 'precoFechamento'
    elif 'abertura' in texto_lower: mapeamentos["#VALOR_DESEJADO#"] = 'precoAbertura'
    elif 'máximo' in texto_lower or 'maximo' in texto_lower: mapeamentos["#VALOR_DESEJADO#"] = 'precoMaximo'
    elif 'mínimo' in texto_lower or 'minimo' in texto_lower: mapeamentos["#VALOR_DESEJADO#"] = 'precoMinimo'

    # Setor
    if 'setor' in texto_lower:
        match_setor = re.search(r'setor\s+(?:de\s+|do\s+|da\s+)?([\w\s]+)', texto_lower)
        if match_setor:
            mapeamentos["#SETOR#"] = match_setor.group(1).strip().title()

    return mapeamentos

def main(pergunta_usuario):
    """Orquestra o processo de PLN."""
    template_nome = selecionar_template(pergunta_usuario)
    if not template_nome:
        exit_with_error("Não foi possível entender a intenção da pergunta.")
    
    doc = nlp(pergunta_usuario)
    mapeamentos = extrair_entidades(doc)
    if not mapeamentos:
        exit_with_error("Não foi possível extrair informações suficientes da pergunta.")

    # A saída é um JSON que o web_app.py pode ler
    print(json.dumps({"template_nome": template_nome, "mapeamentos": mapeamentos}, ensure_ascii=False))

# --- PONTO DE ENTRADA ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        exit_with_error("Nenhuma pergunta fornecida.")
    main(" ".join(sys.argv[1:]))