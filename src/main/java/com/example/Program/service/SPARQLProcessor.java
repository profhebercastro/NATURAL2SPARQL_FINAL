package com.example.Program.service;

import com.example.Program.model.ProcessamentoDetalhadoResposta;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
public class SPARQLProcessor {

    private static final Logger logger = LoggerFactory.getLogger(SPARQLProcessor.class);
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;
    private final PlaceholderService placeholderService;
    private final NlpDictionaryService nlpDictionaryService;
    private static final String NLP_SERVICE_URL = "http://localhost:5000/process_question";

    @Autowired
    public SPARQLProcessor(PlaceholderService placeholderService, NlpDictionaryService nlpDictionaryService) {
        this.httpClient = HttpClient.newHttpClient();
        this.objectMapper = new ObjectMapper();
        this.placeholderService = placeholderService;
        this.nlpDictionaryService = nlpDictionaryService;
    }

    public ProcessamentoDetalhadoResposta generateSparqlQuery(String naturalLanguageQuery) {
        ProcessamentoDetalhadoResposta resposta = new ProcessamentoDetalhadoResposta();
        try {
            String nlpResponseJson = callNlpService(naturalLanguageQuery);
            logger.info("Resposta do NLP: {}", nlpResponseJson);
            JsonNode rootNode = objectMapper.readTree(nlpResponseJson);
            String templateId = rootNode.path("templateId").asText();
            JsonNode entitiesNode = rootNode.path("entities");
            if (templateId == null || templateId.isEmpty()) {
                 throw new IOException("NLP não retornou um templateId.");
            }
            String templateContent = loadTemplate(templateId);
            String finalQuery = buildQuery(templateContent, entitiesNode);
            resposta.setSparqlQuery(finalQuery);
            resposta.setTemplateId(templateId);
            if (entitiesNode.has("CALCULO")) {
                resposta.setTipoMetrica(entitiesNode.get("CALCULO").asText());
            } else if (entitiesNode.has("VALOR_DESEJADO")) {
                resposta.setTipoMetrica(entitiesNode.get("VALOR_DESEJADO").asText());
            }
            logger.info("Consulta SPARQL final gerada:\n{}", finalQuery);
            return resposta;
        } catch (Exception e) {
            logger.error("Erro fatal ao gerar query para '{}': {}", naturalLanguageQuery, e.getMessage(), e);
            resposta.setErro("Erro ao processar a pergunta: " + e.getMessage());
            return resposta;
        }
    }
    
    private String buildQuery(String template, JsonNode entities) {
        String query = template;
        
        if (entities.has("VALOR_DESEJADO") && (query.contains("?valor") || query.contains("?ANS"))) {
            String metricaKey = entities.get("VALOR_DESEJADO").asText().replace("metrica.", "");
            String varName = toCamelCase(metricaKey);
            query = query.replace("?valor", "?" + varName);
            query = query.replace("?ANS", "?" + varName);
        }

        // PREPARA OS BLOCOS DE FILTRO PRIMEIRO
        String entidadeFilter = "";
        if (entities.has("ENTIDADE_NOME")) {
            String entidade = entities.get("ENTIDADE_NOME").asText();
            boolean isKnownAlias = nlpDictionaryService.getEmpresaKeys().contains(entidade.toLowerCase());
            if (entidade.matches("^[A-Z0-9]{5,6}$") && !isKnownAlias) {
                entidadeFilter = "BIND(b3:" + entidade + " AS ?tickerNode) \n    ?empresa b3:temValorMobiliarioNegociado ?tickerNode .";
            } else {
                entidadeFilter = "?empresa rdfs:label ?label . \n    FILTER(REGEX(STR(?label), \"" + entidade + "\", \"i\"))";
            }
        }
        
        String setorFilter = "";
        if (entities.has("NOME_SETOR")) {
            JsonNode setorNode = entities.get("NOME_SETOR");
            if (setorNode.isArray()) {
                List<String> setores = new ArrayList<>();
                for (JsonNode setor : setorNode) {
                    setores.add("\"" + setor.asText() + "\"@pt");
                }
                String inClause = String.join(", ", setores);
                setorFilter = "?empresa b3:atuaEm ?setorUri . \n    ?setorUri rdfs:label ?setorLabel . \n    FILTER(?setorLabel IN (" + inClause + "))";
            } else {
                String nomeSetor = setorNode.asText();
                setorFilter = "?empresa b3:atuaEm ?setorNode . \n    ?setorNode rdfs:label \"" + nomeSetor + "\"@pt .";
            }
        }
        
        // APLICA OS BLOCOS DE FILTRO
        query = query.replace("#FILTER_BLOCK_ENTIDADE#", entidadeFilter);
        query = query.replace("#FILTER_BLOCK_SETOR#", setorFilter);
        if (query.contains("#FILTER_BLOCK#")) {
            String filterBlock = !setorFilter.isEmpty() ? setorFilter : entidadeFilter;
            query = query.replace("#FILTER_BLOCK#", filterBlock);
        }

        // PREENCHE O RESTO DOS PLACEHOLDERS #
        Iterator<Map.Entry<String, JsonNode>> fields = entities.fields();
        while (fields.hasNext()) {
            Map.Entry<String, JsonNode> field = fields.next();
            String placeholder = "#" + field.getKey().toUpperCase() + "#";
            
            if (!placeholder.equals("#FILTER_BLOCK_ENTIDADE#") && !placeholder.equals("#FILTER_BLOCK_SETOR#") && !placeholder.equals("#FILTER_BLOCK#")) {
                String value = field.getValue().asText();
                if (placeholder.equals("#VALOR_DESEJADO#")) {
                    String predicadoRDF = placeholderService.getPlaceholderValue(value);
                    if (predicadoRDF != null) query = query.replace(placeholder, predicadoRDF);

                } else if (placeholder.equals("#CALCULO#")) {
                    String calculoSparql;
                    switch (value) {
                        case "variacao_abs": calculoSparql = "ABS(?fechamento - ?abertura)"; break;
                        case "variacao_perc": calculoSparql = "((?fechamento - ?abertura) / ?abertura) * 100"; break;
                        case "intervalo_abs": calculoSparql = "ABS(?maximo - ?minimo)"; break;
                        case "intervalo_perc": calculoSparql = "((?maximo - ?minimo) / ?abertura) * 100"; break;
                        default: calculoSparql = "0";
                    }
                    query = query.replace(placeholder, calculoSparql);

                } else if (placeholder.equals("#RANKING_CALCULATION#")) {
                    String rankingCalculoSql;
                     switch (value) {
                        case "variacao_abs": rankingCalculoSql = "ABS(?fechamento_rank - ?abertura_rank)"; break;
                        case "variacao_perc": rankingCalculoSql = "((?fechamento_rank - ?abertura_rank) / ?abertura_rank) * 100"; break;
                        case "intervalo_abs": rankingCalculoSql = "ABS(?maximo_rank - ?minimo_rank)"; break;
                        case "intervalo_perc": rankingCalculoSql = "((?maximo_rank - ?minimo_rank) / ?abertura_rank) * 100"; break;
                        case "variacao_abs_abs": rankingCalculoSql = "ABS(?fechamento_rank - ?abertura_rank)"; break;
                        default: rankingCalculoSql = "0";
                    }
                    query = query.replace(placeholder, rankingCalculoSql);

                } else if (placeholder.equals("#REGEX_PATTERN#")) {
                    String regexFilter = "FILTER(REGEX(STR(?ticker), \"" + value + "\"))";
                    query = query.replace("#REGEX_FILTER#", regexFilter);
                    
                } else {
                    query = query.replace(placeholder, value);
                }
            }
        }
        
        // LIMPA PLACEHOLDERS # QUE SOBRARAM
        query = query.replaceAll("#[A-Z_]+#", ""); 

        // SUBSTITUI PLACEHOLDERS GENÉRICOS P* e S*
        query = placeholderService.replaceGenericPlaceholders(query);
        
        // ADICIONA OS PREFIXOS
        String prefixes = placeholderService.getPrefixes();
        
        return prefixes + query; 
    }

    private String toCamelCase(String snakeCase) {
        if (snakeCase == null || snakeCase.isEmpty()) { return ""; }
        StringBuilder camelCase = new StringBuilder();
        boolean nextIsUpper = false;
        for (char c : snakeCase.toCharArray()) {
            if (c == '_') {
                nextIsUpper = true;
            } else {
                if (nextIsUpper) {
                    camelCase.append(Character.toUpperCase(c));
                    nextIsUpper = false;
                } else { camelCase.append(c); }
            }
        }
        return camelCase.toString();
    }
    
    private String callNlpService(String query) throws IOException, InterruptedException {
        String jsonBody = "{\"question\": \"" + query.replace("\"", "\\\"") + "\"}";
        HttpRequest request = HttpRequest.newBuilder().uri(URI.create(NLP_SERVICE_URL)).header("Content-Type", "application/json").POST(HttpRequest.BodyPublishers.ofString(jsonBody)).build();
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) { throw new IOException("Serviço NLP falhou com status " + response.statusCode() + " e corpo: " + response.body()); }
        return response.body();
    }

    private String loadTemplate(String templateName) {
        String path = "/Templates/" + templateName + ".txt";
        try (InputStream is = SPARQLProcessor.class.getResourceAsStream(path)) {
            if (is == null) { throw new IOException("Arquivo de template não encontrado: " + path); }
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
                return reader.lines().collect(Collectors.joining(System.lineSeparator()));
            }
        } catch (IOException e) { throw new RuntimeException("Falha ao carregar template: " + path, e); }
    }
}