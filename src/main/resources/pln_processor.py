# -----------------------------------------------------------------
# ARQUIVO: pln_processor.py (VERSÃO ESTRATÉGIA 1 - MODELO spaCy PEQUENO)
# -----------------------------------------------------------------
import sys
import json
import os
import re
import logging
from datetime import datetime
from unidecode import unidecode
import spacy

# --- CONFIGURAÇÃO INICIAL E LOGS ---
# Configura o logging para que possamos ver as saídas no log do Render
logging.basicConfig(level=logging.INFO, format='PLN_PY - %(asctime)s - %(levelname)s - %(message)s', stream=sys.stderr)

logging.info("Iniciando script pln_processor.py")

# --- FUNÇÕES AUXILIARES ---
def normalize_text(text):
    if not text:
        return ""
    return unidecode(str(text)).lower()

def exit_with_error(message):
    logging.error(f"Encerrando com erro: {message}")
    print(json.dumps({"erro": message}, ensure_ascii=False))
    sys.exit(0)

def carregar_recurso(caminho_arquivo, tipo='json'):
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            if tipo == 'json':
                # Normaliza as chaves do JSON para busca
                return {normalize_text(k): v for k, v in json.load(f).items()}
            elif tipo == 'mapa_simples':
                mapa = {}
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split(';', 1)
                        if len(parts) == 2:
                            # Normaliza a chave (pergunta) para busca
                            mapa[normalize_text(parts[0].strip())] = parts[1].strip()
                return mapa
    except Exception as e:
        exit_with_error(f"FALHA CRITICA ao carregar recurso {caminho_arquivo}: {e}")

# --- CARREGAMENTO GLOBAL DE RECURSOS (feito apenas uma vez) ---
try:
    logging.info("Carregando recursos globais...")
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PERGUNTAS_INTERESSE = carregar_recurso(os.path.join(SCRIPT_DIR, "perguntas_de_interesse.txt"), 'mapa_simples')
    SINONIMOS_MAP = carregar_recurso(os.path.join(SCRIPT_DIR, "sinonimos_map.txt"), 'mapa_simples')
    EMPRESA_MAP = carregar_recurso(os.path.join(SCRIPT_DIR, "empresa_nome_map.json"), 'json')
    SETOR_MAP = carregar_recurso(os.path.join(SCRIPT_DIR, "setor_map.json"), 'json')
    logging.info("Recursos de mapas carregados com sucesso.")

    # --- CORREÇÃO DE MEMÓRIA ---
    # Carrega o modelo PEQUENO ('sm') do spaCy, que é muito mais leve.
    logging.info("Carregando modelo spaCy 'pt_core_news_sm'...")
    nlp = spacy.load("pt_core_news_sm")
    logging.info("Modelo spaCy carregado com sucesso.")

except Exception as e:
    exit_with_error(f"Erro fatal durante a inicialização do script: {e}")

# --- LÓGICA DE PROCESSAMENTO ---
def selecionar_template(pergunta_usuario):
    logging.info("Iniciando seleção de template...")
    pergunta_proc = nlp(pergunta_usuario.lower())
    if not pergunta_proc.has_vector:
        logging.warning("Vetor da pergunta do usuário não encontrado. A similaridade pode ser imprecisa.")
        return None

    melhor_score = -1.0
    template_selecionado = None

    for pergunta_modelo, template_id in PERGUNTAS_INTERESSE.items():
        modelo_proc = nlp(pergunta_modelo)
        if not modelo_proc.has_vector:
            logging.warning(f"Vetor do modelo '{pergunta_modelo}' não encontrado.")
            continue
        
        similaridade = pergunta_proc.similarity(modelo_proc)
        logging.info(f"Comparando com '{pergunta_modelo}': Similaridade = {similaridade:.4f}")
        
        if similaridade > melhor_score:
            melhor_score = similaridade
            template_selecionado = template_id
            
    logging.info(f"Melhor score de similaridade: {melhor_score:.4f} para o template '{template_selecionado}'")
    return template_selecionado if melhor_score > 0.75 else None

def extrair_placeholders(pergunta_usuario):
    logging.info("Iniciando extração de placeholders...")
    mapeamentos = {}
    texto_norm = normalize_text(pergunta_usuario)

    # Extração de Data
    match_data = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', texto_norm)
    if match_data:
        try:
            data_str = match_data.group(1).replace('-', '/')
            dt_format = '%d/%m/%Y' if len(data_str.split('/')[-1]) == 4 else '%d/%m/%y'
            mapeamentos["#DATA#"] = datetime.strptime(data_str, dt_format).strftime('%Y-%m-%d')
            logging.info(f"Data extraída: {mapeamentos['#DATA#']}")
        except ValueError:
            logging.warning(f"Formato de data inválido encontrado: {match_data.group(1)}")

    # Extração de Empresa/Ticker
    for chave_norm, valor_final in sorted(EMPRESA_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if chave_norm in texto_norm:
            mapeamentos["#ENTIDADE_NOME#"] = valor_final
            logging.info(f"Entidade extraída: '{valor_final}' (a partir da chave '{chave_norm}')")
            break

    # Extração de Setor
    for chave_norm, valor_final in sorted(SETOR_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if chave_norm in texto_norm:
            mapeamentos["#SETOR#"] = valor_final
            logging.info(f"Setor extraído: '{valor_final}'")
            break
            
    # Extração de Valor/Métrica Desejada
    for chave_norm, valor_final in sorted(SINONIMOS_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if chave_norm in texto_norm:
            mapeamentos["#VALOR_DESEJADO#"] = valor_final
            logging.info(f"Valor/Métrica extraída: '{valor_final}'")
            break

    logging.info(f"Placeholders finais: {mapeamentos}")
    return mapeamentos

def main(pergunta_usuario):
    logging.info(f"Processando a pergunta: '{pergunta_usuario}'")
    template_id = selecionar_template(pergunta_usuario)
    if not template_id:
        exit_with_error("Não foi possível entender a intenção da sua pergunta. Tente ser mais específico.")
    
    placeholders = extrair_placeholders(pergunta_usuario)

    # Validações
    if template_id in ["Template_1A", "Template_1B", "Template_2A"] and not placeholders.get("#ENTIDADE_NOME#"):
        exit_with_error("Não foi possível identificar a empresa ou o ticker na sua pergunta.")
    if template_id in ["Template_1A", "Template_1B", "Template_4A"] and not placeholders.get("#DATA#"):
        exit_with_error("Não foi possível identificar a data. Por favor, use o formato DD/MM/AAAA.")
    if template_id in ["Template_3A", "Template_4A"] and not placeholders.get("#SETOR#"):
        exit_with_error("Para esta pergunta, por favor, especifique um setor.")

    resposta = {"template_nome": template_id, "mapeamentos": placeholders}
    logging.info(f"Processamento concluído. Retornando JSON: {resposta}")
    print(json.dumps(resposta, ensure_ascii=False))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(" ".join(sys.argv[1:]))
    else:
        exit_with_error("Nenhuma pergunta foi fornecida ao script Python.")