# Arquivo: pln_processor.py
# Local: src/main/resources/

import spacy
import sys
import json
import os
import logging
import re
from datetime import datetime

# --- 1. CONFIGURAÇÃO ---
# Log para stderr para que os logs do servidor web (Gunicorn) possam capturá-los
logging.basicConfig(level=logging.INFO, format='%(asctime)s - PLN - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger("PLN_Processor")

# Função para sair com um erro formatado em JSON, que pode ser lido pelo processo pai
def exit_with_error(message):
    error_response = json.dumps({"erro": message})
    logger.error(f"Encerrando PLN com erro: {message}")
    print(error_response)
    sys.exit(1)

# --- 2. CARREGAMENTO DE RECURSOS (Executado apenas uma vez na inicialização do script) ---
try:
    logger.info("Iniciando carregamento de recursos do PLN...")
    # Constrói os caminhos a partir do local do próprio script para robustez
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    MAPA_EMPRESAS_PATH = os.path.join(SCRIPT_DIR, "empresa_nome_map.json")
    
    # Carregamento do modelo de linguagem do spaCy
    nlp = spacy.load("pt_core_news_sm")
    
    # Carregamento do mapa que associa nomes comuns de empresas a seus nomes formais
    with open(MAPA_EMPRESAS_PATH, 'r', encoding='utf-8') as f:
        EMPRESA_MAP = json.load(f)
    
    logger.info("Recursos do PLN carregados com sucesso.")
except Exception as e:
    exit_with_error(f"Falha crítica na inicialização do PLN. Verifique os caminhos e arquivos. Erro: {e}")

# --- 3. FUNÇÕES DE PROCESSAMENTO ---

def extrair_entidades(doc):
    """Extrai todas as entidades e intenções relevantes de um texto processado pelo spaCy."""
    mapeamentos = {}
    texto_lower = doc.text.lower()

    # Extração de Data
    match_data = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', doc.text)
    if match_data:
        try:
            data_str = match_data.group(1).replace('-', '/')
            dt_format = '%d/%m/%Y' if len(data_str.split('/')[-1]) == 4 else '%d/%m/%y'
            dt_obj = datetime.strptime(data_str, dt_format)
            mapeamentos["#DATA#"] = dt_obj.strftime('%Y-%m-%d')
        except ValueError:
            logger.warning(f"Formato de data inválido encontrado e ignorado: {match_data.group(1)}")

    # Extração de Empresa / Ticker (para o placeholder #ENTIDADE_NOME#)
    nome_empresa_encontrado = None
    # Prioridade 1: Ticker explícito (ex: PETR4, VALE3)
    match_ticker = re.search(r'\b([A-Z]{4}\d{1,2})\b', doc.text.upper())
    if match_ticker:
        # Mapeia o ticker para o nome completo, se disponível, senão usa o próprio ticker
        ticker = match_ticker.group(1)
        nome_empresa_encontrado = EMPRESA_MAP.get(ticker, ticker)
    else:
        # Prioridade 2: Nome da empresa presente no mapa
        for nome_mapa, nome_ontologia in EMPRESA_MAP.items():
            if nome_mapa.lower() in texto_lower:
                nome_empresa_encontrado = nome_ontologia
                break
    if nome_empresa_encontrado:
        mapeamentos["#ENTIDADE_NOME#"] = nome_empresa_encontrado

    # Extração do Valor Desejado (para o placeholder #VALOR_DESEJADO#)
    # Note que retornamos APENAS o nome da propriedade, pois o prefixo "b3:" já está no template.
    if 'fechamento' in texto_lower: mapeamentos["#VALOR_DESEJADO#"] = 'precoFechamento'
    elif 'abertura' in texto_lower: mapeamentos["#VALOR_DESEJADO#"] = 'precoAbertura'
    elif 'máximo' in texto_lower or 'maximo' in texto_lower: mapeamentos["#VALOR_DESEJADO#"] = 'precoMaximo'
    elif 'mínimo' in texto_lower or 'minimo' in texto_lower: mapeamentos["#VALOR_DESEJADO#"] = 'precoMinimo'

    # Extração de Intenção para desambiguação de templates
    if 'código de negociação' in texto_lower or 'codigo da acao' in texto_lower:
        mapeamentos["#INTENCAO#"] = "buscar_codigo"

    if 'setor' in texto_lower:
        mapeamentos["#INTENCAO#"] = "listar_por_setor"
        match_setor = re.search(r'setor\s+(?:de\s+|do\s+|da\s+)?([\w\s]+)', texto_lower)
        if match_setor:
            setor_bruto = match_setor.group(1).strip()
            mapeamentos["#SETOR#"] = setor_bruto.title()
            
    return mapeamentos

def selecionar_template_por_regras(mapeamentos):
    """Seleciona o template com base nas entidades encontradas, usando regras lógicas."""
    entidades = set(mapeamentos.keys())
    
    # Regra para templates de consulta de preço (ex: Template_1A, Template_1B)
    if {"#ENTIDADE_NOME#", "#DATA#", "#VALOR_DESEJADO#"} <= entidades:
        return "Template_1A"

    # Regra para template de busca de código (ex: Template_2A)
    if {"#ENTIDADE_NOME#", "#INTENCAO#"} <= entidades and mapeamentos["#INTENCAO#"] == "buscar_codigo":
        return "Template_2A"

    # Regra para template de listagem por setor (ex: Template_3A)
    if {"#SETOR#", "#INTENCAO#"} <= entidades and mapeamentos["#INTENCAO#"] == "listar_por_setor":
        return "Template_3A"

    return None

def main(pergunta_usuario):
    """Função principal que orquestra o processo de PLN."""
    logger.info(f"Processando pergunta: '{pergunta_usuario}'")
    doc = nlp(pergunta_usuario)
    
    mapeamentos = extrair_entidades(doc)
    if not mapeamentos:
        exit_with_error("Não foi possível extrair nenhuma informação útil da pergunta.")
    
    template_nome = selecionar_template_por_regras(mapeamentos)
    if not template_nome:
        exit_with_error("A combinação de informações extraídas não corresponde a nenhuma ação conhecida.")

    resposta = {"template_nome": template_nome, "mapeamentos": mapeamentos}
    print(json.dumps(resposta, ensure_ascii=False))
    logger.info("Processamento PLN concluído com sucesso.")

# --- 4. PONTO DE ENTRADA DO SCRIPT ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        exit_with_error("Nenhuma pergunta fornecida como argumento de linha de comando.")
    
    pergunta_completa = " ".join(sys.argv[1:])
    main(pergunta_completa)