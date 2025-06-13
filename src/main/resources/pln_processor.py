# Arquivo: pln_processor.py
# Versão completa e funcional, integrando todas as correções.

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
    """Encerra o script e imprime um erro formatado em JSON."""
    print(json.dumps({"erro": message}))
    sys.exit(1)

# --- 2. CARREGAMENTO DE RECURSOS ---
try:
    # Caminhos baseados na localização do script, para robustez em contêineres
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # Carrega o modelo de linguagem
    nlp = spacy.load("pt_core_news_sm")
    
    # Carrega o mapa de nomes de empresas
    with open(os.path.join(SCRIPT_DIR, "empresa_nome_map.json"), 'r', encoding='utf-8') as f:
        EMPRESA_MAP = json.load(f)
    
    # Carrega as perguntas de interesse para a seleção de templates
    PERGUNTAS_INTERESSE = []
    with open(os.path.join(SCRIPT_DIR, "perguntas_de_interesse.txt"), 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                parts = line.strip().split(';', 1)
                if len(parts) == 2:
                    PERGUNTAS_INTERESSE.append({"id": parts[0].strip(), "text": parts[1].strip()})
    
    # MAPEAMENTO INTERNO E CORRETO DE SETORES
    # Este dicionário é a fonte da verdade para mapear keywords para URIs da ontologia.
    # Ele substitui a necessidade do 'setor_map.json'.
    SETOR_URI_MAP = {
        "eletrico": "stock:Setor_energia_eletrica",
        "elétrico": "stock:Setor_energia_eletrica",
        "bancos": "stock:Setor_bancos",
        "bancario": "stock:Setor_bancos",
        "bancário": "stock:Setor_bancos",
        "financeiro": "stock:Setor_financeiro",
        "industrial": "stock:Setor_industrial"
        # Adicione novos setores aqui conforme necessário.
        # Ex: "saude": "stock:Setor_saude"
    }
    logger.info("Recursos do PLN carregados com sucesso.")

except FileNotFoundError as e:
    exit_with_error(f"Arquivo de recurso não encontrado: {e}. Verifique se todos os JSON e TXT estão presentes.")
except Exception as e:
    exit_with_error(f"Erro crítico ao carregar recursos do PLN: {e}")

# --- 3. FUNÇÕES DE PROCESSAMENTO ---

def selecionar_template(pergunta_usuario):
    """Usa similaridade de string para encontrar o template mais provável."""
    pergunta_norm = pergunta_usuario.lower()
    textos_perguntas = [p['text'].lower() for p in PERGUNTAS_INTERESSE]
    matches = get_close_matches(pergunta_norm, textos_perguntas, n=1, cutoff=0.55) # Um cutoff razoável
    
    if matches:
        # Encontra o ID do template correspondente ao melhor match
        for p in PERGUNTAS_INTERESSE:
            if p['text'].lower() == matches[0]:
                logger.info(f"Pergunta similar encontrada: '{matches[0]}'. Selecionando template ID: '{p['id']}'")
                return p['id'].replace(" ", "_") # Converte "Template 3A" para "Template_3A"
    
    logger.warning(f"Nenhum template similar encontrado para a pergunta: '{pergunta_usuario}'")
    return None

def extrair_entidades(doc):
    """Extrai todas as entidades relevantes (data, empresa, setor, etc.) da pergunta."""
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
            logger.warning(f"Formato de data encontrado, mas não foi possível parsear: {match_data.group(1)}")

    # Extração de Empresa/Ticker
    nome_empresa = None
    # Prioridade 1: Ticker explícito (ex: PETR4)
    match_ticker = re.search(r'\b([A-Z]{4}\d{1,2})\b', doc.text.upper())
    if match_ticker:
        nome_empresa = match_ticker.group(1)
    else:
        # Prioridade 2: Nome da empresa por keyword do mapa
        # Ordena por comprimento para encontrar "banco do brasil" antes de "brasil"
        for nome_mapa in sorted(EMPRESA_MAP.keys(), key=len, reverse=True):
            if nome_mapa.lower() in texto_lower:
                nome_empresa = EMPRESA_MAP[nome_mapa]
                logger.info(f"Empresa encontrada por keyword: '{nome_mapa}' -> '{nome_empresa}'")
                break
    if nome_empresa:
        mapeamentos["#ENTIDADE_NOME#"] = nome_empresa

    # Extração de Tipo de Preço (para #VALOR_DESEJADO#)
    if 'fechamento' in texto_lower: mapeamentos["#VALOR_DESEJADO#"] = 'precoFechamento'
    elif 'abertura' in texto_lower: mapeamentos["#VALOR_DESEJADO#"] = 'precoAbertura'
    
    # Extração de Setor (usando o mapa de URIs interno)
    if 'setor' in texto_lower:
        for keyword, setor_uri in SETOR_URI_MAP.items():
            if keyword in texto_lower:
                mapeamentos["#SETOR_URI#"] = setor_uri
                logger.info(f"Setor encontrado e mapeado: '{keyword}' -> '{setor_uri}'")
                break # Usa o primeiro que encontrar

    return mapeamentos

def main(pergunta_usuario):
    """Função principal que orquestra todo o processo de PLN."""
    logger.info(f"Processando pergunta: '{pergunta_usuario}'")
    
    # 1. Seleciona o template mais provável
    template_nome = selecionar_template(pergunta_usuario)
    if not template_nome:
        exit_with_error("Não foi possível entender a intenção da pergunta (nenhum template similar encontrado).")
    
    # 2. Processa o texto com spaCy para extração de entidades
    doc = nlp(pergunta_usuario)
    
    # 3. Extrai as entidades e as mapeia para os placeholders
    mapeamentos = extrair_entidades(doc)
    
    # 4. Validação final
    if template_nome == "Template_3A" and "#SETOR_URI#" not in mapeamentos:
        exit_with_error("A pergunta parece ser sobre um setor, mas não consegui identificar um setor válido (ex: elétrico, bancos).")
    if not mapeamentos:
        exit_with_error("Não foi possível extrair nenhuma informação (empresa, data, setor, etc.) da pergunta.")
    
    # 5. Prepara a resposta JSON para o web_app.py
    resposta_final = {
        "template_nome": template_nome, 
        "mapeamentos": mapeamentos
    }
    
    print(json.dumps(resposta_final, ensure_ascii=False))
    logger.info(f"Processamento PLN concluído. Template: {template_nome}, Mapeamentos: {mapeamentos}")

# --- PONTO DE ENTRADA DO SCRIPT ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        exit_with_error("Nenhuma pergunta fornecida como argumento.")
    
    # Junta todos os argumentos para formar a pergunta completa
    pergunta_completa = " ".join(sys.argv[1:])
    main(pergunta_completa)