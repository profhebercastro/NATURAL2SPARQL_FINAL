package com.example.Programa_heber.service;

import com.example.Programa_heber.model.ProcessamentoDetalhadoResposta;
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
    private static final String NLP_SERVICE_URL = "http://localhost:5000/process_question";

    @Autowired
    public SPARQLProcessor(PlaceholderService placeholderService) {
        this.httpClient = HttpClient.newHttpClient();
        this.objectMapper = new ObjectMapper();
        this.placeholderService = placeholderService;
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
            
            String finalQuery;
            // Roteamento explícito para os métodos de construção
            if ("Template_5B".equals(templateId)) {
                finalQuery = buildTypeFilteredQuery(templateContent, entitiesNode);
            } else if (templateId.startsWith("Template_6") || templateId.startsWith("Template_7") || templateId.startsWith("Template_8")) {
                finalQuery = buildCalculationQuery(templateContent, entitiesNode);
            } else {
                finalQuery = buildSimpleQuery(templateContent, entitiesNode);
            }

            resposta.setSparqlQuery(finalQuery);
            resposta.setTemplateId(templateId);
            logger.info("Consulta SPARQL final gerada:\n{}", finalQuery);

            return resposta;

        } catch (Exception e) {
            logger.error("Erro fatal ao gerar query para '{}': {}", naturalLanguageQuery, e.getMessage(), e);
            resposta.setErro("Erro ao processar a pergunta: " + e.getMessage());
            return resposta;
        }
    }

    private String buildSimpleQuery(String template, JsonNode entities) {
        String query = placeholderService.replaceGenericPlaceholders(template);
        return replaceSimplePlaceholders(query, entities);
    }
    
    private String buildTypeFilteredQuery(String template, JsonNode entities) {
        String query = template;

        if (entities.has("ENTIDADE_NOME")) {
            String nomeEntidade = entities.get("ENTIDADE_NOME").asText();
            String entidadeFilter = "?S1 rdfs:label ?label . \n    FILTER(REGEX(STR(?label), \"" + nomeEntidade + "\", \"i\"))";
            query = query.replace("#FILTER_BLOCK_ENTIDADE#", entidadeFilter);
        } else {
            query = query.replace("#FILTER_BLOCK_ENTIDADE#", "");
        }
        
        if (entities.has("REGEX_PATTERN")) {
            String regexPattern = entities.get("REGEX_PATTERN").asText();
            String regexFilter = "FILTER(REGEX(STR(?ticker), \"" + regexPattern + "\"))";
            query = query.replace("#REGEX_FILTER#", regexFilter);
        } else {
            query = query.replace("#REGEX_FILTER#", "");
        }
        
        query = placeholderService.replaceGenericPlaceholders(query);

        if (entities.has("VALOR_DESEJADO")) {
            String metrica = entities.get("VALOR_DESEJADO").asText();
            query = query.replace("#VALOR_DESEJADO#", placeholderService.getPlaceholderValue(metrica));
        }

        if (entities.has("DATA")) {
            query = query.replace("#DATA#", entities.get("DATA").asText());
        }
        
        return query;
    }

    private String buildCalculationQuery(String template, JsonNode entities) {
        String query = template;
        
        // Substitui os filtros ANTES dos placeholders genéricos
        if (entities.has("NOME_SETOR")) {
            JsonNode setorNode = entities.get("NOME_SETOR");
            String setorFilter = "    ?S1 b3:atuaEm ?setor . \n    ?setor rdfs:label ?label .";
            
            if (setorNode.isArray()) {
                List<String> setores = new ArrayList<>();
                for (JsonNode setor : setorNode) {
                    setores.add("\"" + setor.asText() + "\"@pt");
                }
                String inClause = String.join(", ", setores);
                setorFilter += "\n    FILTER(?label IN (" + inClause + "))";
            } else {
                String nomeSetor = setorNode.asText();
                setorFilter += "\n    FILTER(?label = \"" + nomeSetor + "\"@pt)";
            }
            query = query.replace("#FILTER_BLOCK_SETOR#", setorFilter);
        } else {
            query = query.replace("#FILTER_BLOCK_SETOR#", "");
        }
        
        if (entities.has("ENTIDADE_NOME")) {
            String nomeEntidade = entities.get("ENTIDADE_NOME").asText();
            String entidadeFilter = "?S1 rdfs:label ?label . \n    FILTER(REGEX(STR(?label), \"" + nomeEntidade + "\", \"i\"))";
            query = query.replace("#FILTER_BLOCK_ENTIDADE#", entidadeFilter);
        } else {
            query = query.replace("#FILTER_BLOCK_ENTIDADE#", "");
        }
        
        // AGORA substitui os placeholders genéricos (P*, S*)
        query = placeholderService.replaceGenericPlaceholders(query);
        
        // Substitui a fórmula de cálculo
        String calculoKey = entities.path("CALCULO").asText("");
        String calculoSparql;
        switch (calculoKey) {
            case "variacao_abs":   calculoSparql = "(?fechamento - ?abertura)"; break;
            case "variacao_perc":  calculoSparql = "((?fechamento - ?abertura) / ?abertura)"; break;
            case "intervalo_abs":  calculoSparql = "(?maximo - ?minimo)"; break;
            case "intervalo_perc": calculoSparql = "((?maximo - ?minimo) / ?abertura)"; break;
            case "variacao_abs_abs": calculoSparql = "ABS(?fechamento - ?abertura)"; break;
            default: calculoSparql = "0";
        }
        query = query.replace("#CALCULO#", calculoSparql);

        // Substituições finais
        if (entities.has("DATA")) query = query.replace("#DATA#", entities.get("DATA").asText());
        query = query.replace("#ORDEM#", entities.path("ORDEM").asText("DESC"));
        query = query.replace("#LIMITE#", entities.path("LIMITE").asText("1"));
        
        return query;
    }

    private String replaceSimplePlaceholders(String template, JsonNode entities) {
        String finalQuery = template;
        Iterator<Map.Entry<String, JsonNode>> fields = entities.fields();
        while (fields.hasNext()) {
            Map.Entry<String, JsonNode> field = fields.next();
            String placeholder = "#" + field.getKey() + "#";
            String value = field.getValue().asText();
            finalQuery = finalQuery.replace(placeholder, value);
        }
        return finalQuery;
    }

    private String callNlpService(String query) throws IOException, InterruptedException {
        String jsonBody = "{\"question\": \"" + query.replace("\"", "\\\"") + "\"}";
        HttpRequest request = HttpRequest.newBuilder().uri(URI.create(NLP_SERVICE_URL)).header("Content-Type", "application/json").POST(HttpRequest.BodyPublishers.ofString(jsonBody)).build();
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) {
            throw new IOException("Serviço NLP falhou com status " + response.statusCode() + " e corpo: " + response.body());
        }
        return response.body();
    }

    private String loadTemplate(String templateName) {
        String path = "/Templates/" + templateName + ".txt";
        try (InputStream is = SPARQLProcessor.class.getResourceAsStream(path)) {
            if (is == null) {
                throw new IOException("Arquivo de template não encontrado: " + path);
            }
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
                return reader.lines()
                             .collect(Collectors.joining(System.lineSeparator()));
            }
        } catch (IOException e) {
            throw new RuntimeException("Falha ao carregar template: " + path, e);
        }
    }
}