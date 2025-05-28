import spacy
import sys
import json
import os
import logging
import re
from difflib import get_close_matches
from datetime import datetime

# --- Configuração do Logging ---
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format, stream=sys.stderr) # Log para stderr
logger = logging.getLogger("PLN_Processor")

# --- Funções Auxiliares (normalizar_texto DEVE ser definida ANTES de ser usada nos carregamentos) ---
def normalizar_texto(texto_input):
    if not texto_input: return ""
    texto_lower = texto_input.lower()
    # Mapa para remover acentos comuns em português e algumas pontuações
    mapa_acentos = str.maketrans(
        "áàâãäéèêëíìîïóòôõöúùûüç", 
        "aaaaaeeeeiiiiooooouuuuc", 
        ".,;:!?()'\"<>[]{}@#$%^&*-+=~`|\\" 
    )
    texto_sem_acentos_pontuacao = texto_lower.translate(mapa_acentos)
    # Remove espaços duplicados e das pontas
    texto_limpo = ' '.join(texto_sem_acentos_pontuacao.split())
    return texto_limpo.strip()

# --- Constantes e Caminhos ---
try:
    # __file__ pode não estar definido em alguns contextos (ex: interpretador interativo)
    # mas para um script sendo executado, deve funcionar.
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError: 
    # Fallback para o diretório de trabalho atual se __file__ não estiver definido
    script_dir = os.getcwd() 
RESOURCES_DIR = script_dir # Assume que pln_processor.py está no diretório de resources
logger.info(f"Diretório base dos resources (RESOURCES_DIR) assumido: {RESOURCES_DIR} (CWD do script: {os.getcwd()})")

SINONIMOS_PATH = os.path.join(RESOURCES_DIR, "resultado_similaridade.txt")
PERGUNTAS_INTERESSE_PATH = os.path.join(RESOURCES_DIR, "perguntas_de_interesse.txt")
MAPA_EMPRESAS_JSON_PATH = os.path.join(RESOURCES_DIR, "empresa_nome_map.json")
SETOR_MAP_JSON_PATH = os.path.join(RESOURCES_DIR, "setor_map.json")

logger.info(f"Caminho sinônimos (valor desejado): {SINONIMOS_PATH}")
logger.info(f"Caminho perguntas interesse (seleção template): {PERGUNTAS_INTERESSE_PATH}")
logger.info(f"Caminho mapa empresas (entidade nome): {MAPA_EMPRESAS_JSON_PATH}")
logger.info(f"Caminho mapa setores (setor): {SETOR_MAP_JSON_PATH}")

# --- Carregamento de Recursos ---
def exit_with_json_error(error_message, template_id_info=None, mapeamentos_info=None, exit_code=1):
    logger.error(f"ERRO CRÍTICO PLN: {error_message}")
    error_payload = {
        "erro": error_message, 
        "template_nome": template_id_info if template_id_info else None, 
        "mapeamentos": mapeamentos_info if mapeamentos_info else {}
    }
    # Imprime para stdout, pois é isso que web_app.py espera capturar
    print(json.dumps(error_payload, ensure_ascii=False))
    sys.exit(exit_code)

nlp = None
try:
    logger.info("Carregando modelo spaCy 'pt_core_news_sm'...")
    nlp = spacy.load("pt_core_news_sm")
    logger.info("Modelo spaCy carregado com sucesso.")
except OSError:
    exit_with_json_error("Configuração crítica: Modelo spaCy 'pt_core_news_sm' não encontrado. Execute: python -m spacy download pt_core_news_sm")
except Exception as e:
    exit_with_json_error(f"Configuração crítica: Erro inesperado ao carregar modelo spaCy: {str(e)}")

empresa_nome_map = {}
try:
    if not os.path.exists(MAPA_EMPRESAS_JSON_PATH):
        exit_with_json_error(f"Configuração crítica: Arquivo de mapa de empresas JSON não encontrado em: {MAPA_EMPRESAS_JSON_PATH}")
    with open(MAPA_EMPRESAS_JSON_PATH, 'r', encoding='utf-8') as f:
        empresa_nome_map_raw = json.load(f)
        empresa_nome_map = {normalizar_texto(k.replace(" ", "")): v for k, v in empresa_nome_map_raw.items()}
    logger.info(f"Mapa de empresas JSON carregado (chaves normalizadas): {len(empresa_nome_map)} mapeamentos.")
    if not empresa_nome_map: logger.warning(f"Mapa de empresas JSON ({MAPA_EMPRESAS_JSON_PATH}) está vazio.")
except Exception as e:
    exit_with_json_error(f"Configuração crítica: Erro ao carregar mapa de empresas JSON ({MAPA_EMPRESAS_JSON_PATH}): {str(e)}")

sinonimos_map = {} 
try:
    if not os.path.exists(SINONIMOS_PATH):
        logger.warning(f"Arquivo de sinônimos ({SINONIMOS_PATH}) não encontrado. Mapeamento de #VALOR_DESEJADO# pode falhar.")
    else:
        with open(SINONIMOS_PATH, 'r', encoding='utf-8') as f_sin:
            for line_s in f_sin:
                line_s = line_s.strip()
                if not line_s or line_s.startswith('#'): continue
                parts_s = line_s.split(';')
                if len(parts_s) == 2 and parts_s[0].strip() and parts_s[1].strip():
                    sinonimos_map[normalizar_texto(parts_s[0].strip())] = parts_s[1].strip()
        logger.info(f"Dicionário de sinônimos (para #VALOR_DESEJADO#) carregado (chaves normalizadas): {len(sinonimos_map)} chaves.")
        if not sinonimos_map and os.path.exists(SINONIMOS_PATH): logger.warning(f"Dicionário de sinônimos ({SINONIMOS_PATH}) carregado, mas vazio.")
except Exception as e_sin:
    logger.error(f"Erro (não crítico) ao carregar dicionário de sinônimos ({SINONIMOS_PATH}): {str(e_sin)}")

setor_map_global = {} 
try:
    if not os.path.exists(SETOR_MAP_JSON_PATH):
        exit_with_json_error(f"Configuração crítica: Arquivo de mapa de setores JSON não encontrado em: {SETOR_MAP_JSON_PATH}")
    with open(SETOR_MAP_JSON_PATH, 'r', encoding='utf-8') as f_set:
        setor_map_raw = json.load(f_set)
        setor_map_global = {normalizar_texto(k): v for k, v in setor_map_raw.items()} 
    logger.info(f"Mapa de setores JSON carregado (chaves normalizadas, valores originais do JSON): {len(setor_map_global)} mapeamentos.")
    if not setor_map_global: logger.warning(f"Mapa de setores JSON ({SETOR_MAP_JSON_PATH}) está vazio. Mapeamento de #SETOR# falhará.")
except Exception as e_set:
    exit_with_json_error(f"Configuração crítica: Erro ao carregar mapa de setores JSON ({SETOR_MAP_JSON_PATH}): {str(e_set)}")

def extrair_entidades_data(doc_spacy):
    entidades_ner_dict = {"ORG": [], "DATE": [], "LOC": [], "MISC": [], "PER": []}
    keywords_valor_encontradas = [] 
    data_formatada_iso = None
    for ent in spacy.util.filter_spans(doc_spacy.ents): # Usar filter_spans para evitar sobreposição de entidades
        if ent.label_ in entidades_ner_dict and ent.text not in entidades_ner_dict[ent.label_]:
            entidades_ner_dict[ent.label_].append(ent.text)
    
    # Tentar extrair data com regex mais flexível
    match_obj_date = re.compile(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b|\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b').search(doc_spacy.text)
    if match_obj_date:
        date_str = match_obj_date.group(1) or match_obj_date.group(2)
        try:
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts[2]) == 2: # Formato DD/MM/YY
                    dt_obj = datetime.strptime(date_str, '%d/%m/%y')
                else: # Formato DD/MM/YYYY
                    dt_obj = datetime.strptime(date_str, '%d/%m/%Y')
            elif '-' in date_str:
                 dt_obj = datetime.strptime(date_str, '%Y-%m-%d') # Assume YYYY-MM-DD
            data_formatada_iso = dt_obj.strftime('%Y-%m-%d')
        except ValueError as ve:
            logger.warning(f"Não foi possível parsear data '{date_str}': {ve}")
            pass # Data inválida
    
    texto_norm_para_keywords = normalizar_texto(doc_spacy.text)
    for kw_norm_mapa_sinonimos in sorted(sinonimos_map.keys(), key=len, reverse=True): 
         if re.search(r'\b' + re.escape(kw_norm_mapa_sinonimos) + r'\b', texto_norm_para_keywords):
             keywords_valor_encontradas.append(kw_norm_mapa_sinonimos) # Adiciona a chave normalizada
    return entidades_ner_dict, data_formatada_iso, keywords_valor_encontradas

def selecionar_template(pergunta_usuario_original, path_perguntas_interesse):
    pergunta_usuario_norm_para_match = normalizar_texto(pergunta_usuario_original)
    map_id_por_exemplo_original = {} 
    lista_exemplos_norm_para_difflib = []
    lista_exemplos_originais = [] # Para debug
    try:
        if not os.path.exists(path_perguntas_interesse):
             logger.error(f"CRÍTICO (selecionar_template): {path_perguntas_interesse} não encontrado.")
             return None, 0.0
        with open(path_perguntas_interesse, 'r', encoding='utf-8') as f_pi:
            for line_pi in f_pi:
                line_pi_strip = line_pi.strip()
                if not line_pi_strip or line_pi_strip.startswith('#'): continue
                parts_pi = line_pi_strip.split(';', 1)
                if len(parts_pi) == 2 and parts_pi[0].strip() and parts_pi[1].strip():
                    template_id_lido = parts_pi[0].strip() # Ex: "Template 1A"
                    pergunta_exemplo_lida = parts_pi[1].strip()
                    
                    map_id_por_exemplo_original[pergunta_exemplo_lida] = template_id_lido
                    pergunta_exemplo_sem_ph = re.sub(r'<[^>]+>', '', pergunta_exemplo_lida) # Remove placeholders como <empresa>
                    lista_exemplos_norm_para_difflib.append(normalizar_texto(pergunta_exemplo_sem_ph))
                    lista_exemplos_originais.append(pergunta_exemplo_lida) # Para encontrar o original
            if not map_id_por_exemplo_original:
                 logger.error(f"ERRO (selecionar_template): Nenhuma pergunta de interesse válida carregada de {path_perguntas_interesse}.")
                 return None, 0.0
    except Exception as e_pi:
         logger.error(f"CRÍTICO (selecionar_template): Erro ao ler perguntas de interesse: {str(e_pi)}")
         return None, 0.0

    matches_difflib = get_close_matches(pergunta_usuario_norm_para_match, lista_exemplos_norm_para_difflib, n=1, cutoff=0.60) 
    if matches_difflib:
        melhor_match_exemplo_norm_sem_ph = matches_difflib[0]
        try:
            idx_match = lista_exemplos_norm_para_difflib.index(melhor_match_exemplo_norm_sem_ph)
            melhor_match_exemplo_original_com_ph = lista_exemplos_originais[idx_match]
            template_id_final_selecionado = map_id_por_exemplo_original[melhor_match_exemplo_original_com_ph] # Ainda com espaço
            
            # Cálculo de similaridade (Jaccard como exemplo, pode ser melhorado)
            set_usuario = set(pergunta_usuario_norm_para_match.split())
            set_exemplo_match_sem_ph = set(melhor_match_exemplo_norm_sem_ph.split())
            intersecao = len(set_usuario.intersection(set_exemplo_match_sem_ph))
            uniao = len(set_usuario.union(set_exemplo_match_sem_ph))
            score_jaccard = intersecao / uniao if uniao > 0 else 0.0
            logger.info(f"Template selecionado (antes de corrigir): '{template_id_final_selecionado}' (Match com: '{melhor_match_exemplo_original_com_ph}', Jaccard Aprox: {score_jaccard:.3f})")
            return template_id_final_selecionado, score_jaccard 
        except ValueError: 
             logger.error(f"Erro interno (selecionar_template): Match '{melhor_match_exemplo_norm_sem_ph}' não encontrado na lista original após difflib.")
             return None, 0.0
    logger.warning(f"Nenhum template similar encontrado para: '{pergunta_usuario_original}' (cutoff=0.60)")
    return None, 0.0

def extract_and_normalize_setor(pergunta_original_texto):
    logger.debug(f"Tentando extrair setor da pergunta: '{pergunta_original_texto}'")
    setor_extraido_bruto_norm_para_chave = None 
    pergunta_norm = normalizar_texto(pergunta_original_texto)
    # Regex para capturar texto após "setor de/do/da" ou "ações do setor"
    padroes_regex = [
        r'setor\s+(?:de\s+|do\s+|da\s+)?([a-z0-9\s\-\_]+?)(?:\?|$|\s+com|\s+que|listad[ao]s|na\s+b3|brasileir[ao]s)',
        r'(?:ações|acoes|empresas)\s+do\s+setor\s+([a-z0-9\s\-\_]+?)(?:\?|$)'
    ]
    for pattern in padroes_regex:
        match = re.search(pattern, pergunta_norm)
        if match:
            setor_extraido_bruto_norm_para_chave = match.group(1).strip() # Já é normalizado por 'pergunta_norm'
            logger.info(f"Setor bruto (norm) extraído por regex ('{pattern}'): '{setor_extraido_bruto_norm_para_chave}'")
            break # Usa o primeiro match
    
    # Se regex não pegou, tenta por keywords do mapa de setores
    if not setor_extraido_bruto_norm_para_chave:
        sorted_map_keys_norm = sorted(setor_map_global.keys(), key=len, reverse=True) # Chaves já normalizadas
        for key_norm_mapa_setor in sorted_map_keys_norm:
            # Usar \b para garantir que é uma palavra completa
            if re.search(r'\b' + re.escape(key_norm_mapa_setor) + r'\b', pergunta_norm):
                setor_extraido_bruto_norm_para_chave = key_norm_mapa_setor
                logger.info(f"Setor bruto (norm) encontrado por keyword do setor_map_global: '{setor_extraido_bruto_norm_para_chave}'")
                break
    
    if setor_extraido_bruto_norm_para_chave:
        # setor_extraido_bruto_norm_para_chave é uma CHAVE normalizada do setor_map_global
        setor_final_para_ontologia = setor_map_global.get(setor_extraido_bruto_norm_para_chave)
        if setor_final_para_ontologia:
            logger.info(f"Valor do setor para ontologia (do mapa): '{setor_final_para_ontologia}' (Chave de busca no mapa: '{setor_extraido_bruto_norm_para_chave}')")
            return setor_final_para_ontologia # Retorna o valor como está no JSON (ex: "Elétrico")
        logger.warning(f"Termo de setor '{setor_extraido_bruto_norm_para_chave}' extraído mas não é chave válida em setor_map_global.")
    logger.info(f"Nenhum termo de setor pôde ser extraído ou normalizado de: '{pergunta_original_texto}'")
    return None

def mapear_placeholders(ent_ner, data_iso, kw_val_detectadas, tid_corrigido, p_orig_txt): # tid_corrigido JÁ VEM COM UNDERSCORE
    maps = {}
    tipo_ent_dbg = "N/A (Placeholder #ENTIDADE_NOME# não preenchido)"
    if data_iso: maps["#DATA#"] = data_iso; logger.info(f"  Placeholder #DATA# => '{data_iso}'")

    ent_nome_final = None
    if ent_ner.get("ORG"):
        org_ner_txt = ent_ner["ORG"][0] # Pega a primeira ORG detectada
        chave_map = normalizar_texto(org_ner_txt).replace(" ", "") # Chave para buscar no mapa de empresas
        logger.debug(f"Processando ORG NER: '{org_ner_txt}' (chave normalizada para mapa: '{chave_map}')")

        if chave_map in empresa_nome_map: # empresa_nome_map tem chaves normalizadas e sem espaços
            val_map_list = empresa_nome_map[chave_map] # Valor pode ser lista
            if isinstance(val_map_list, list) and val_map_list:
                val0 = val_map_list[0] # Pega o primeiro valor da lista do mapa
                
                if tid_corrigido == "Template_2A": # Espera LABEL de empresa
                    if val0.endswith("_LABEL"): # Indicador explícito no valor do mapa
                        ent_nome_final = chave_map.upper() # Usa a chave normalizada como label
                        tipo_ent_dbg = f"LABEL_EMPRESA (de _LABEL, chave: {chave_map})"
                    elif not re.match(r"^[A-Z]{4}\d{1,2}$", val0.upper()): # Se o valor mapeado não é ticker
                        ent_nome_final = val0.upper() # Usa o valor mapeado como label
                        tipo_ent_dbg = f"LABEL_EMPRESA (Mapeado direto para '{val0}')"
                    else: # O valor mapeado é um ticker, mas T2A precisa de label
                        ent_nome_final = chave_map.upper() if not re.match(r"^[A-Z]{4}\d{1,2}$", chave_map.upper()) else val0
                        tipo_ent_dbg = f"LABEL_EMPRESA_FALLBACK (Chave '{chave_map}' usada, pois mapeamento era Ticker '{val0}')"
                        logger.warning(f"T2A: Entidade '{org_ner_txt}' mapeou para Ticker '{val0}'. Usando '{ent_nome_final}' como label.")
                else: # Templates 1A, 1B etc. que esperam TICKER ou nome para ser convertido em TICKER
                    if val0.endswith("_LABEL"): # Se o mapa diz que é um label de empresa
                        # Tenta derivar o ticker preferencial (ex: final 3, 4 ou 11)
                        ticker_derivado = None
                        for sfx in ["3", "4", "11", "5", "6"]: # Ordem de preferência
                            chk_ticker_deriv = chave_map + sfx # Ex: "vale" + "3" -> "vale3"
                            if chk_ticker_deriv in empresa_nome_map and isinstance(empresa_nome_map[chk_ticker_deriv], list) and empresa_nome_map[chk_ticker_deriv]: 
                                ticker_derivado = empresa_nome_map[chk_ticker_deriv][0]; break
                        if ticker_derivado and re.match(r"^[A-Z]{4}\d{1,2}$", ticker_derivado.upper()):
                            ent_nome_final = ticker_derivado.upper()
                            tipo_ent_dbg = f"TICKER (Derivado de Label '{chave_map}' para '{ticker_derivado}')"
                        else:
                            logger.error(f"FALHA derivar Ticker válido para Label '{chave_map}' (de NER '{org_ner_txt}')")
                            ent_nome_final = org_ner_txt # Fallback para o texto NER original
                            tipo_ent_dbg = "FALHA_DERIVAR_TICKER_DE_LABEL"
                    elif re.match(r"^[A-Z]{4}\d{1,2}$", val0.upper()): # Se o valor mapeado já é um ticker
                        ent_nome_final = val0.upper()
                        tipo_ent_dbg = f"TICKER (Mapeado direto de chave '{chave_map}')"
                    else: # Valor mapeado não é _LABEL nem Ticker
                        ent_nome_final = val0; tipo_ent_dbg = f"MAPEADO_NAO_TICKER ('{val0}')"
                        logger.warning(f"Valor '{val0}' para '{chave_map}' não é ticker nem _LABEL para template {tid_corrigido} que pode esperar ticker.")
            else: 
                ent_nome_final = org_ner_txt; tipo_ent_dbg = "NER_ORG (Falha Formato Valor Mapeamento ou Lista Vazia)"
        
        elif re.match(r"^[A-Z]{4}\d{1,2}$", org_ner_txt.upper()): # Se o próprio texto NER ORG já é um ticker
            if tid_corrigido != "Template_2A": # Se não for T2A, usa o ticker
                 ent_nome_final = org_ner_txt.upper()
                 tipo_ent_dbg = "TICKER (NER ORG já era Ticker)"
            else: # Se for T2A, tenta extrair a parte do nome da empresa do ticker
                 ent_nome_final = re.sub(r'\d{1,2}$', '', org_ner_txt.upper()) # Remove os números do final
                 tipo_ent_dbg = f"LABEL_DE_TICKER_NER (NER ORG era Ticker '{org_ner_txt}', usando '{ent_nome_final}' como label para T2A)"
                 logger.info(f"T2A: NER ORG era Ticker '{org_ner_txt}'. Usando '{ent_nome_final}' como possível label.")
        else: # NER ORG não mapeada e não é ticker
            ent_nome_final = org_ner_txt.upper() if tid_corrigido == "Template_2A" else org_ner_txt 
            tipo_ent_dbg = "LABEL_EMPRESA (NER ORG não mapeada)" if tid_corrigido == "Template_2A" else "NER_ORG (Não Mapeado, Não Ticker)"
            if tid_corrigido != "Template_2A": logger.warning(f"ORG '{org_ner_txt}' não mapeada/ticker para {tid_corrigido}")
    
    # Fallback se NER não pegou empresa/ticker, mas há um ticker explícito na pergunta original
    if not ent_nome_final and tid_corrigido != "Template_2A": # Não faz sentido para T2A que busca label
        match_ticker_fallback = re.search(r'\b([A-Z]{4}\d{1,2})\b', p_orig_txt.upper()) # Procura por ticker na pergunta original
        if match_ticker_fallback: 
            ent_nome_final = match_ticker_fallback.group(1)
            tipo_ent_dbg = "TICKER (Regex Fallback da pergunta original)"

    if ent_nome_final: 
        maps["#ENTIDADE_NOME#"] = ent_nome_final
        logger.info(f"  Placeholder #ENTIDADE_NOME# => '{ent_nome_final}' (Tipo Detecção: {tipo_ent_dbg})")
    else:
         logger.warning(f"Placeholder #ENTIDADE_NOME# não pôde ser mapeado para template {tid_corrigido}.")

    if kw_val_detectadas: # kw_val_detectadas são chaves normalizadas do sinonimos_map
        # Pega o primeiro sinônimo encontrado (mais específico, pois foram ordenados por tamanho)
        valor_desejado_para_ontologia = sinonimos_map.get(kw_val_detectadas[0])
        if valor_desejado_para_ontologia: 
            maps["#VALOR_DESEJADO#"] = valor_desejado_para_ontologia
            logger.info(f"  Placeholder #VALOR_DESEJADO# => '{valor_desejado_para_ontologia}' (KW Normalizada: '{kw_val_detectadas[0]}')")

    if tid_corrigido == "Template_3A": # Template que precisa de #SETOR#
        setor_mapeado_para_ontologia = extract_and_normalize_setor(p_orig_txt) # Já retorna o valor final
        if setor_mapeado_para_ontologia: 
            maps["#SETOR#"] = setor_mapeado_para_ontologia
            logger.info(f"  Placeholder #SETOR# => '{setor_mapeado_para_ontologia}'")
    
    logger.debug(f"Mapeamentos placeholders finais: {maps}")
    return maps, tipo_ent_dbg

def main(pergunta_usuario_java):
    logger.info(f"* INÍCIO Main PLN: '{pergunta_usuario_java}' *")
    if not nlp: exit_with_json_error("PLN Interno: Modelo spaCy não carregado.")

    doc_spacy_obj = nlp(pergunta_usuario_java)
    entidades_ner, data_iso, keywords_valor = extrair_entidades_data(doc_spacy_obj)
    logger.debug(f"  Extraído de entidades_data: NER:{entidades_ner}, Data ISO:{data_iso}, Keywords Valor (norm):{keywords_valor}")

    template_id_com_espaco, similaridade_score = selecionar_template(pergunta_usuario_java, PERGUNTAS_INTERESSE_PATH)
    
    if not template_id_com_espaco: 
        exit_with_json_error(f"Não foi possível selecionar template para: '{pergunta_usuario_java}'", 
                             template_id_info=template_id_com_espaco)

    # ----- INÍCIO DA CORREÇÃO -----
    template_id_corrigido = template_id_com_espaco.replace(" ", "_")
    logger.info(f"Template selecionado (original): '{template_id_com_espaco}', Corrigido para: '{template_id_corrigido}' (Similaridade aprox.: {similaridade_score:.3f})")
    # ----- FIM DA CORREÇÃO -----
    
    # Use template_id_corrigido daqui em diante
    map_placeholders_final, tipo_ent_debug = mapear_placeholders(
        entidades_ner, data_iso, keywords_valor, template_id_corrigido, pergunta_usuario_java
    )
    
    # As chaves aqui agora DEVEM usar o formato com UNDERSCORE para corresponder a template_id_corrigido
    placeholders_essenciais_por_template = {
         "Template_1A": ["#DATA#", "#ENTIDADE_NOME#", "#VALOR_DESEJADO#"],
         "Template_1B": ["#DATA#", "#ENTIDADE_NOME#", "#VALOR_DESEJADO#"],
         "Template_2A": ["#ENTIDADE_NOME#"], 
         "Template_3A": ["#SETOR#"] 
    }
    
    faltando_essenciais_list = []
    if template_id_corrigido in placeholders_essenciais_por_template:
        for ph_req_essencial in placeholders_essenciais_por_template[template_id_corrigido]: 
            if ph_req_essencial not in map_placeholders_final or not map_placeholders_final.get(ph_req_essencial):
                faltando_essenciais_list.append(ph_req_essencial)
    else: 
        logger.warning(f"Template ID '{template_id_corrigido}' não está na config de validação de placeholders. Validação de placeholders essenciais não realizada.")

    if faltando_essenciais_list:
        msg_erro_faltando = f"Informação essencial faltando para template '{template_id_corrigido}': {', '.join(faltando_essenciais_list)}."
        logger.error(msg_erro_faltando)
        # Envia erro estruturado para o web_app.py (que deve retornar HTTP 400 ou similar)
        print(json.dumps({
            "template_nome": template_id_corrigido, 
            "mapeamentos": map_placeholders_final, 
            "erro": msg_erro_faltando, 
            "_debug_info": {
                "pergunta_original_recebida": pergunta_usuario_java, 
                "faltando_essenciais": faltando_essenciais_list, 
                "tipo_entidade_principal_debug": tipo_ent_debug,
                "ner_spacy_detectadas": entidades_ner, "data_iso_detectada": data_iso,
                "keywords_valor_detectadas_mapa": keywords_valor,
                "template_score_similaridade": round(similaridade_score, 3)
            }
        }, ensure_ascii=False))
        sys.exit(0) # Saída 0 porque o PLN processou, mas identificou um erro lógico na pergunta. web_app.py deve tratar.
    
    logger.info(f"Validação de placeholders OK para '{template_id_corrigido}'.")
    resposta_final_obj = {
        "template_nome": template_id_corrigido, 
        "mapeamentos": map_placeholders_final,
        "_debug_info": { # Informações de debug para análise posterior
             "pergunta_original_recebida": pergunta_usuario_java,
             "ner_spacy_detectadas": entidades_ner, "data_iso_detectada": data_iso,
             "keywords_valor_detectadas_mapa": keywords_valor,
             "template_score_similaridade": round(similaridade_score, 3),
             "tipo_entidade_principal_debug": tipo_ent_debug
         }
    }
    print(json.dumps(resposta_final_obj, ensure_ascii=False)) # Saída para stdout
    logger.info(f"* FIM Main PLN: JSON enviado. Status 0. *")
    sys.exit(0) # Saída bem-sucedida

if __name__ == "__main__":
    logger.info(f"--- INICIANDO SCRIPT PLN_PROCESSOR.PY (PID: {os.getpid()}), CWD: {os.getcwd()}, Args: {sys.argv} ---")
    if len(sys.argv) > 1:
        pergunta_completa_usuario = " ".join(sys.argv[1:]) # Concatena todos os argumentos após o nome do script
        try: 
            main(pergunta_completa_usuario)
        except SystemExit: # Permite que sys.exit() funcione como esperado
            raise
        except Exception as e_main: 
            # Captura qualquer exceção não tratada em main e formata como JSON
            exit_with_json_error(f"Erro crítico não tratado na execução principal do PLN: {type(e_main).__name__} - {str(e_main)}")
    else: 
        exit_with_json_error("Nenhuma pergunta fornecida ao script PLN.")