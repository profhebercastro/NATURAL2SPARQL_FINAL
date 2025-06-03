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
logging.basicConfig(level=logging.INFO, format=log_format, stream=sys.stderr) 
logger = logging.getLogger("PLN_Processor")

# --- Funções Auxiliares ---
def normalizar_texto(texto_input):
    if not texto_input: return ""
    texto_lower = texto_input.lower()
    mapa_acentos = str.maketrans(
        "áàâãäéèêëíìîïóòôõöúùûüç", 
        "aaaaaeeeeiiiiooooouuuuc", 
        ".,;:!?()'\"<>[]{}@#$%^&*-+=~`|\\" 
    )
    texto_sem_acentos_pontuacao = texto_lower.translate(mapa_acentos)
    texto_limpo = ' '.join(texto_sem_acentos_pontuacao.split())
    return texto_limpo.strip()

# --- Constantes e Caminhos ---
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError: 
    script_dir = os.getcwd() 
RESOURCES_DIR = script_dir
logger.info(f"Diretório base dos resources (RESOURCES_DIR) assumido: {RESOURCES_DIR} (CWD do script: {os.getcwd()})")

SINONIMOS_PATH = os.path.join(RESOURCES_DIR, "resultado_similaridade.txt")
PERGUNTAS_INTERESSE_PATH = os.path.join(RESOURCES_DIR, "perguntas_de_interesse.txt")
MAPA_EMPRESAS_JSON_PATH = os.path.join(RESOURCES_DIR, "empresa_nome_map.json")
SETOR_MAP_JSON_PATH = os.path.join(RESOURCES_DIR, "setor_map.json")

logger.info(f"Caminho sinônimos/intenções: {SINONIMOS_PATH}") # Renomeado para refletir duplo uso
logger.info(f"Caminho perguntas interesse: {PERGUNTAS_INTERESSE_PATH}")
logger.info(f"Caminho mapa empresas: {MAPA_EMPRESAS_JSON_PATH}")
logger.info(f"Caminho mapa setores: {SETOR_MAP_JSON_PATH}")

# --- Carregamento de Recursos ---
def exit_with_json_error(error_message, template_id_info=None, mapeamentos_info=None, exit_code=1):
    logger.error(f"ERRO PLN: {error_message}")
    error_payload = {
        "erro": error_message, 
        "template_nome": template_id_info if template_id_info else None, 
        "mapeamentos": mapeamentos_info if mapeamentos_info else {}
    }
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
        empresa_nome_map = {normalizar_texto(k.replace(" ", "")): v 
                            for k, v in empresa_nome_map_raw.items()}
    logger.info(f"Mapa de empresas JSON carregado (chaves normalizadas): {len(empresa_nome_map)} mapeamentos.")
    if not empresa_nome_map: logger.warning(f"Mapa de empresas JSON ({MAPA_EMPRESAS_JSON_PATH}) está vazio.")
except Exception as e:
    exit_with_json_error(f"Configuração crítica: Erro ao carregar mapa de empresas JSON ({MAPA_EMPRESAS_JSON_PATH}): {type(e).__name__} - {str(e)}")

# Este mapa agora é para #VALOR_DESEJADO# e para identificar intenção de "código"
termos_mapeados_map = {} 
try:
    if not os.path.exists(SINONIMOS_PATH):
        logger.warning(f"Arquivo de sinônimos/intenções ({SINONIMOS_PATH}) não encontrado.")
    else:
        with open(SINONIMOS_PATH, 'r', encoding='utf-8') as f_sin:
            for line_s in f_sin:
                line_s = line_s.strip()
                if not line_s or line_s.startswith('#'): continue
                parts_s = line_s.split(';')
                if len(parts_s) == 2 and parts_s[0].strip() and parts_s[1].strip():
                    termos_mapeados_map[normalizar_texto(parts_s[0].strip())] = parts_s[1].strip()
        logger.info(f"Dicionário de termos mapeados carregado: {len(termos_mapeados_map)} chaves.")
        if not termos_mapeados_map and os.path.exists(SINONIMOS_PATH): logger.warning(f"Dicionário de termos mapeados ({SINONIMOS_PATH}) vazio.")
except Exception as e_sin:
    logger.error(f"Erro (não crítico) ao carregar dicionário de termos mapeados ({SINONIMOS_PATH}): {str(e_sin)}")

setor_map_global = {} 
try:
    if not os.path.exists(SETOR_MAP_JSON_PATH):
        exit_with_json_error(f"Configuração crítica: Arquivo de mapa de setores JSON não encontrado em: {SETOR_MAP_JSON_PATH}")
    with open(SETOR_MAP_JSON_PATH, 'r', encoding='utf-8') as f_set:
        setor_map_raw = json.load(f_set)
        setor_map_global = {normalizar_texto(k): v for k, v in setor_map_raw.items()} 
    logger.info(f"Mapa de setores JSON carregado: {len(setor_map_global)} mapeamentos.")
    if not setor_map_global: logger.warning(f"Mapa de setores JSON ({SETOR_MAP_JSON_PATH}) vazio.")
except Exception as e_set:
    exit_with_json_error(f"Configuração crítica: Erro ao carregar mapa de setores JSON ({SETOR_MAP_JSON_PATH}): {type(e).__name__} - {str(e_set)}")

def extrair_entidades_data_e_termos(doc_spacy): # Renomeado para clareza
    entidades_ner_dict = {"ORG": [], "DATE": [], "LOC": [], "MISC": [], "PER": []}
    termos_detectados_norm = [] # Para keywords de valor desejado ou intenção de código
    data_formatada_iso = None
    for ent in spacy.util.filter_spans(doc_spacy.ents):
        if ent.label_ in entidades_ner_dict and ent.text not in entidades_ner_dict[ent.label_]:
            entidades_ner_dict[ent.label_].append(ent.text)
    match_obj_date = re.compile(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b|\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b').search(doc_spacy.text)
    if match_obj_date:
        date_str = match_obj_date.group(1) or match_obj_date.group(2)
        try:
            dt_obj = None
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts[2]) == 2: dt_obj = datetime.strptime(date_str, '%d/%m/%y')
                else: dt_obj = datetime.strptime(date_str, '%d/%m/%Y')
            elif '-' in date_str: dt_obj = datetime.strptime(date_str, '%Y-%m-%d')
            if dt_obj: data_formatada_iso = dt_obj.strftime('%Y-%m-%d')
        except ValueError as ve: logger.warning(f"Não foi possível parsear data '{date_str}': {ve}")
    
    texto_norm_para_termos = normalizar_texto(doc_spacy.text)
    # termos_mapeados_map contém tanto #VALOR_DESEJADO# quanto intenção de código
    for termo_norm_mapa in sorted(termos_mapeados_map.keys(), key=len, reverse=True): 
         if re.search(r'\b' + re.escape(termo_norm_mapa) + r'\b', texto_norm_para_termos):
             termos_detectados_norm.append(termo_norm_mapa) # Adiciona a CHAVE normalizada
    return entidades_ner_dict, data_formatada_iso, termos_detectados_norm

def selecionar_template(pergunta_usuario_original, path_perguntas_interesse):
    # ... (nenhuma mudança necessária aqui, ela retorna o template_id com espaço) ...
    pergunta_usuario_norm_para_match = normalizar_texto(pergunta_usuario_original)
    map_id_por_exemplo_original = {} 
    lista_exemplos_norm_para_difflib = []
    lista_exemplos_originais = []
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
                    template_id_lido_com_espaco = parts_pi[0].strip() 
                    pergunta_exemplo_lida = parts_pi[1].strip()
                    map_id_por_exemplo_original[pergunta_exemplo_lida] = template_id_lido_com_espaco
                    pergunta_exemplo_sem_ph = re.sub(r'<[^>]+>', '', pergunta_exemplo_lida)
                    lista_exemplos_norm_para_difflib.append(normalizar_texto(pergunta_exemplo_sem_ph))
                    lista_exemplos_originais.append(pergunta_exemplo_lida)
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
            template_id_final_selecionado_com_espaco = map_id_por_exemplo_original[melhor_match_exemplo_original_com_ph]
            set_usuario = set(pergunta_usuario_norm_para_match.split())
            set_exemplo_match_sem_ph = set(melhor_match_exemplo_norm_sem_ph.split())
            intersecao = len(set_usuario.intersection(set_exemplo_match_sem_ph))
            uniao = len(set_usuario.union(set_exemplo_match_sem_ph))
            score_jaccard = intersecao / uniao if uniao > 0 else 0.0
            return template_id_final_selecionado_com_espaco, score_jaccard 
        except ValueError: 
             logger.error(f"Erro interno (selecionar_template): Match '{melhor_match_exemplo_norm_sem_ph}' não encontrado.")
             return None, 0.0
    logger.warning(f"Nenhum template similar encontrado para: '{pergunta_usuario_original}' (cutoff=0.60)")
    return None, 0.0

def extract_and_normalize_setor(pergunta_original_texto):
    # ... (nenhuma mudança necessária aqui se setor_map.json estiver correto) ...
    logger.debug(f"--- Iniciando extract_and_normalize_setor para: '{pergunta_original_texto}' ---")
    setor_extraido_bruto_norm_para_chave = None 
    pergunta_norm = normalizar_texto(pergunta_original_texto) 
    logger.debug(f"Pergunta normalizada: '{pergunta_norm}'")
    padroes_regex_setor = [
        r'setor\s+(?:de\s+|do\s+|da\s+)?([a-z0-9\s\-\_]+?)(?:\?|$|\s+com|\s+que|listad[ao]s|na\s+b3|brasileir[ao]s|quais|como|tem|pertencem)',
        r'(?:ações|acoes|empresas)\s+do\s+setor\s+([a-z0-9\s\-\_]+?)(?:\?|$)',
        r'empresas\s+de\s+([a-z0-9\s\-\_]+?)(?:\?|$)',
        r'setor\s+([a-z0-9\s\-\_]+?)(?:\?|$)',
    ]
    for pattern in padroes_regex_setor:
        match = re.search(pattern, pergunta_norm)
        if match:
            termo_regex_extraido = match.group(1).strip()
            logger.info(f"Termo de setor bruto (norm) extraído por regex ('{pattern}'): '{termo_regex_extraido}'")
            if termo_regex_extraido in setor_map_global:
                setor_final_para_ontologia = setor_map_global[termo_regex_extraido]
                logger.info(f"Match direto do termo da regex no mapa: Chave '{termo_regex_extraido}' -> Valor Ontológico '{setor_final_para_ontologia}'")
                return setor_final_para_ontologia
            else:
                setor_extraido_bruto_norm_para_chave = termo_regex_extraido
                logger.debug(f"Termo da regex '{termo_regex_extraido}' não é chave exata. Será usado como candidato principal para keyword.")
                break 
    candidatos_a_chave_norm = []
    if setor_extraido_bruto_norm_para_chave:
        candidatos_a_chave_norm.append(setor_extraido_bruto_norm_para_chave)
    candidatos_a_chave_norm.extend(sorted(setor_map_global.keys(), key=len, reverse=True))
    seen = set()
    candidatos_a_chave_norm_unicos = [x for x in candidatos_a_chave_norm if not (x in seen or seen.add(x))]
    for key_norm_candidata in candidatos_a_chave_norm_unicos:
        if re.search(r'\b' + re.escape(key_norm_candidata) + r'\b', pergunta_norm):
            setor_final_para_ontologia = setor_map_global.get(key_norm_candidata) 
            if setor_final_para_ontologia:
                logger.info(f"Setor encontrado por keyword do setor_map_global: Chave '{key_norm_candidata}' -> Valor Ontológico '{setor_final_para_ontologia}'")
                return setor_final_para_ontologia
            else: 
                logger.warning(f"Keyword '{key_norm_candidata}' encontrada, mas não tem valor no setor_map_global.")
    logger.info(f"Nenhum termo de setor pôde ser extraído ou mapeado de: '{pergunta_original_texto}'")
    return None

def mapear_placeholders(ent_ner, data_iso, termos_detectados_norm, tid_corrigido, p_orig_txt):
    maps = {}
    tipo_ent_dbg = "N/A" 
    ent_nome_final = None

    if data_iso: 
        maps["#DATA#"] = data_iso
        logger.info(f"  Placeholder #DATA# => '{data_iso}'")

    org_detectada_ner = ent_ner.get("ORG")[0] if ent_ner.get("ORG") else None
    
    if org_detectada_ner:
        chave_map_empresa = normalizar_texto(org_detectada_ner).replace(" ", "")
        logger.debug(f"Processando ORG NER: '{org_detectada_ner}' (chave normalizada para mapa: '{chave_map_empresa}')")
        valor_mapeado_empresa_str = empresa_nome_map.get(chave_map_empresa) 

        if valor_mapeado_empresa_str: 
            logger.info(f"Chave '{chave_map_empresa}' encontrada no mapa. Valor: '{valor_mapeado_empresa_str}'")
            is_ticker_mapeado = isinstance(valor_mapeado_empresa_str, str) and \
                                re.match(r"^[A-Z]{4}\d{1,2}$", valor_mapeado_empresa_str.upper())

            if tid_corrigido == "Template_1A" or tid_corrigido == "Template_2A": 
                if not is_ticker_mapeado and isinstance(valor_mapeado_empresa_str, str): 
                    ent_nome_final = valor_mapeado_empresa_str
                    tipo_ent_dbg = f"LABEL_EMPRESA (Do mapa '{chave_map_empresa}'->'{valor_mapeado_empresa_str}' para {tid_corrigido})"
                else: 
                    logger.warning(f"{tid_corrigido}: Chave '{chave_map_empresa}' mapeou para TICKER/Outro ('{valor_mapeado_empresa_str}'), mas esperava LABEL. Usando NER ORG '{org_detectada_ner}' como fallback.")
                    ent_nome_final = org_detectada_ner 
                    tipo_ent_dbg = f"LABEL_EMPRESA_FALLBACK_NER (De NER '{org_detectada_ner}' para {tid_corrigido})"
            
            elif tid_corrigido == "Template_1B": 
                if is_ticker_mapeado: 
                    ent_nome_final = valor_mapeado_empresa_str.upper()
                    tipo_ent_dbg = f"TICKER (Do mapa '{chave_map_empresa}'->'{valor_mapeado_empresa_str}' para T1B)"
                else: 
                    logger.warning(f"T1B: Chave '{chave_map_empresa}' mapeou para LABEL/Outro ('{valor_mapeado_empresa_str}'), mas esperava TICKER.")
                    if isinstance(org_detectada_ner, str) and re.match(r"^[A-Z]{4}\d{1,2}$", org_detectada_ner.upper()):
                        ent_nome_final = org_detectada_ner.upper()
                        tipo_ent_dbg = f"TICKER_FALLBACK_NER (De NER '{org_detectada_ner}' para T1B)"
                    else:
                        tipo_ent_dbg = f"ERRO_TIPO_T1B (Mapa deu '{valor_mapeado_empresa_str}', NER ORG '{org_detectada_ner}' não é ticker)"
                        logger.error(f"T1B: Não foi possível obter ticker para '{org_detectada_ner}'.")
        else: 
            logger.info(f"Chave '{chave_map_empresa}' (de NER '{org_detectada_ner}') NÃO encontrada no mapa de empresas.")
            if isinstance(org_detectada_ner, str):
                if tid_corrigido == "Template_1B" and re.match(r"^[A-Z]{4}\d{1,2}$", org_detectada_ner.upper()):
                    ent_nome_final = org_detectada_ner.upper()
                    tipo_ent_dbg = f"TICKER (De NER '{org_detectada_ner}' diretamente, para T1B)"
                elif tid_corrigido == "Template_1A" or tid_corrigido == "Template_2A":
                    ent_nome_final = org_detectada_ner
                    tipo_ent_dbg = f"LABEL_EMPRESA (De NER '{org_detectada_ner}' diretamente, para {tid_corrigido})"
                else:
                    tipo_ent_dbg = f"ENTIDADE_NAO_MAPEADA_E_NAO_TICKER_PARA_T1B (NER '{org_detectada_ner}' para {tid_corrigido})"
            else:
                tipo_ent_dbg = "NER_ORG_INVALIDO_OU_AUSENTE"
                logger.warning(f"NER ORG não detectou uma string válida para processamento: {org_detectada_ner}")

    if not ent_nome_final and tid_corrigido == "Template_1B":
        match_ticker_fallback_txt = re.search(r'\b([A-Z]{4}\d{1,2})\b', p_orig_txt.upper())
        if match_ticker_fallback_txt:
            ent_nome_final = match_ticker_fallback_txt.group(1)
            tipo_ent_dbg = f"TICKER (Regex Fallback da pergunta original para T1B)"
            logger.info(f"Usando ticker de fallback da pergunta original: '{ent_nome_final}'")

    if ent_nome_final: 
        maps["#ENTIDADE_NOME#"] = ent_nome_final
        logger.info(f"  Placeholder #ENTIDADE_NOME# => '{ent_nome_final}' (Tipo Detecção: {tipo_ent_dbg})")
    # Não logar warning aqui se não preenchido, a validação no main() cuidará disso.

    # --- Lógica para #VALOR_DESEJADO# usando termos_detectados_norm e termos_mapeados_map ---
    valor_desejado_final = None
    if termos_detectados_norm:
        # Priorizar termos mais específicos para #VALOR_DESEJADO#
        term_priority_order = ["preco medio", "media de preco", "medio", 
                               "total negocios", "quantidade de acoes", "quantidade negociada", "numero de negocios", "negocios realizados",
                               "volume financeiro", "volume negociado", "volume de acoes (financeiro)", "volume total", "volume"]
        
        # Adiciona os outros termos detectados que não estão na lista de prioridade,
        # mas que estão no termos_mapeados_map e não são 'type_codigo'
        for term in kw_val_detectadas_norm: # kw_val_detectadas_norm é o nome antigo de termos_detectados_norm
            if term not in term_priority_order and termos_mapeados_map.get(term) != 'type_codigo':
                term_priority_order.append(term)

        for term_key_norm in term_priority_order:
            if term_key_norm in termos_detectados_norm: # Verifica se o termo priorizado foi detectado
                mapped_value = termos_mapeados_map.get(term_key_norm)
                if mapped_value and mapped_value != 'type_codigo':
                    valor_desejado_final = mapped_value
                    logger.info(f"  Placeholder #VALOR_DESEJADO# => '{valor_desejado_final}' (Termo prioritário: '{term_key_norm}')")
                    break # Encontrou o mais prioritário
        
        if not valor_desejado_final and termos_detectados_norm[0] in termos_mapeados_map: # Fallback para o primeiro detectado
            mapped_value = termos_mapeados_map.get(termos_detectados_norm[0])
            if mapped_value and mapped_value != 'type_codigo':
                 valor_desejado_final = mapped_value
                 logger.info(f"  Placeholder #VALOR_DESEJADO# (fallback) => '{valor_desejado_final}' (Termo: '{termos_detectados_norm[0]}')")
        
        if valor_desejado_final:
            maps["#VALOR_DESEJADO#"] = valor_desejado_final
        else:
            # Se ainda não tem #VALOR_DESEJADO# mas o template é 1A ou 1B, pode ser um problema
            # A validação no main() pegará se for essencial.
            logger.warning(f"Nenhum termo mapeado para #VALOR_DESEJADO# (excluindo type_codigo). Termos detectados: {termos_detectados_norm}")

    if tid_corrigido == "Template_3A":
        setor_mapeado_ontologia = extract_and_normalize_setor(p_orig_txt)
        if setor_mapeado_ontologia: 
            maps["#SETOR#"] = setor_mapeado_ontologia
            logger.info(f"  Placeholder #SETOR# => '{setor_mapeado_ontologia}'")
    
    logger.debug(f"Mapeamentos placeholders finais: {maps}")
    return maps, tipo_ent_dbg

def main(pergunta_usuario_java):
    logger.info(f"* INÍCIO Main PLN: '{pergunta_usuario_java}' *")
    if not nlp: exit_with_json_error("PLN Interno: Modelo spaCy não carregado.")

    doc_spacy_obj = nlp(pergunta_usuario_java)
    entidades_ner, data_iso, termos_detectados_norm = extrair_entidades_data_e_termos(doc_spacy_obj)
    logger.debug(f"  Extraído: NER:{entidades_ner}, Data ISO:{data_iso}, Termos (norm):{termos_detectados_norm}")

    template_id_com_espaco, similaridade_score = selecionar_template(pergunta_usuario_java, PERGUNTAS_INTERESSE_PATH)
    
    if not template_id_com_espaco: 
        logger.error(f"Não foi possível selecionar template para: '{pergunta_usuario_java}'")
        print(json.dumps({
            "erro": f"Não foi possível selecionar um template adequado para a pergunta.",
            "template_nome": None, "mapeamentos": {}
        }, ensure_ascii=False))
        sys.exit(0) 

    template_id_corrigido = template_id_com_espaco.replace(" ", "_")
    logger.info(f"Template selecionado (original): '{template_id_com_espaco}', Corrigido para: '{template_id_corrigido}' (Similaridade aprox.: {similaridade_score:.3f})")
    
    # Verifica se a intenção é buscar código ANTES de mapear placeholders
    # Se Template_2A é selecionado, a intenção de "código" já está implícita pelo template.
    # A lógica de keywords_valor_detectadas_mapa para "type_codigo" pode ser removida se a seleção de T2A for robusta.
    # Por enquanto, vamos assumir que T2A é selecionado corretamente e não precisamos de "type_codigo" no #VALOR_DESEJADO#.
    
    map_placeholders_final, tipo_ent_debug = mapear_placeholders(
        entidades_ner, data_iso, termos_detectados_norm, template_id_corrigido, pergunta_usuario_java
    )
    
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
        logger.warning(f"Template ID '{template_id_corrigido}' não na config de validação. Validação não realizada.")

    _debug_info_completo = {
        "pergunta_original_recebida": pergunta_usuario_java,
        "ner_spacy_detectadas": entidades_ner, "data_iso_detectada": data_iso,
        "keywords_valor_detectadas_mapa": termos_detectados_norm, # Renomeado para consistência
        "template_score_similaridade": round(similaridade_score, 3),
        "tipo_entidade_principal_debug": tipo_ent_debug
    }

    if faltando_essenciais_list:
        msg_erro_faltando = f"Informação essencial faltando para template '{template_id_corrigido}': {', '.join(faltando_essenciais_list)}."
        logger.error(msg_erro_faltando)
        _debug_info_completo["faltando_essenciais"] = faltando_essenciais_list
        print(json.dumps({
            "template_nome": template_id_corrigido, 
            "mapeamentos": map_placeholders_final, 
            "erro": msg_erro_faltando, 
            "_debug_info": _debug_info_completo
        }, ensure_ascii=False))
        sys.exit(0) 
    
    logger.info(f"Validação de placeholders OK para '{template_id_corrigido}'.")
    resposta_final_obj = {
        "template_nome": template_id_corrigido, 
        "mapeamentos": map_placeholders_final,
        "_debug_info": _debug_info_completo
    }
    print(json.dumps(resposta_final_obj, ensure_ascii=False))
    logger.info(f"* FIM Main PLN: JSON enviado. Status 0. *")
    sys.exit(0)

if __name__ == "__main__":
    logger.info(f"--- INICIANDO SCRIPT PLN_PROCESSOR.PY (PID: {os.getpid()}), CWD: {os.getcwd()}, Args: {sys.argv} ---")
    if len(sys.argv) > 1:
        pergunta_completa_usuario = " ".join(sys.argv[1:])
        try: 
            main(pergunta_completa_usuario)
        except SystemExit as se:
            if se.code != 0 : 
                 logger.error(f"Script PLN encerrado com código: {se.code}")
            pass 
        except Exception as e_main: 
            exit_with_json_error(f"Erro crítico não tratado na execução principal do PLN: {type(e_main).__name__} - {str(e_main)}")
    else: 
        exit_with_json_error("Nenhuma pergunta fornecida ao script PLN.")