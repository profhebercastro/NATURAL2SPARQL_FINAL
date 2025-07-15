package com.example.Programa_heber.service;

import com.example.Programa_heber.model.ProcessamentoDetalhadoResposta;
import com.example.Programa_heber.ontology.Ontology;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
public class SPARQLProcessor {

    private static final Logger logger = LoggerFactory.getLogger(SPARQLProcessor.class);
    
    private final Ontology ontology;
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;
    private final PlaceholderService placeholderService;
    private static final String NLP_SERVICE_URL = "http://localhost:5000/process_question";

    @Autowired
    public SPARQLProcessor(PlaceholderService placeholderService, Ontology ontology) {
        this.httpClient = HttpClient.newHttpClient();
        this.objectMapper = new ObjectMapper();
        this.placeholderService = placeholderService;
        this.ontology = ontology;
    }

    public ProcessamentoDetalhadoResposta generateSparqlQuery(String naturalLanguageQuery) {
        ProcessamentoDetalhadoResposta resposta = new ProcessamentoDetalhadoResposta();
        try {
            String nlpResponseJson = callNlpService(naturalLanguageQuery);
            logger.info("Resposta do NLP: {}", nlpResponseJson);

            JsonNode rootNode = objectMapper.readTree(nlpResponseJson);
            String templateId = rootNode.path("templateId").asText();
            JsonNode entitiesNode = rootNode.path("entities");

            String finalQuery;

            if ("Template_8A".equals(templateId) || "Template_8B".equals(templateId)) {
                finalQuery = buildMultiStepQuery(templateId, entitiesNode);
            } else if ("Template_6A".equals(templateId) || "Template_7A".equals(templateId)) {
                finalQuery = buildCalculationQuery(templateId, entitiesNode);
            } else {
                String templateContent = loadTemplate(templateId);
                finalQuery = replaceSimplePlaceholders(templateContent, entitiesNode);
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

    private String buildMultiStepQuery(String templateId, JsonNode entities) {
        // ETAPA 1: Construir e executar a consulta de ranking.
        ObjectNode rankingEntities = entities.deepCopy();
        rankingEntities.put("CALCULO", entities.get("CALCULO_RANKING").asText());
        rankingEntities.put("ORDEM", entities.get("ORDEM_RANKING").asText());
        rankingEntities.put("LIMITE", entities.get("LIMITE_RANKING").asText());
        
        String rankingQuery = buildCalculationQuery("Template_7A", rankingEntities);
        
        logger.info("Executando consulta de ranking intermediária:\n{}", rankingQuery);
        List<Map<String, String>> rankingResult = ontology.executeQuery(rankingQuery);
        
        if (rankingResult.isEmpty() || !rankingResult.get(0).containsKey("ticker")) {
            return "# Erro: Não foi possível encontrar a ação de referência para a segunda etapa da consulta.";
        }
        
        String targetTicker = rankingResult.get(0).get("ticker");
        logger.info("Ticker alvo encontrado: {}", targetTicker);

        // ETAPA 2: Construir a consulta final
        ObjectNode finalEntities = objectMapper.createObjectNode();
        finalEntities.put("ENTIDADE_NOME", targetTicker);
        finalEntities.set("DATA", entities.get("DATA"));

        String finalTemplateId;
        String finalCalculationKey;

        if ("Template_8A".equals(templateId)) {
            finalTemplateId = "Template_6A";
            finalCalculationKey = entities.path("CALCULO_PRINCIPAL").asText("variacao_abs");
        } else { // Template_8B
            finalTemplateId = "Template_7A";
            finalCalculationKey = entities.path("CALCULO_PRINCIPAL").asText("intervalo_perc");
        }
        finalEntities.put("CALCULO", finalCalculationKey);

        String finalQuery = buildCalculationQuery(finalTemplateId, finalEntities);

        // Remove cláusulas de ranking desnecessárias
        finalQuery = finalQuery.replaceFirst("ORDER BY .*? ", " ");
        finalQuery = finalQuery.replaceFirst("LIMIT .*? ", " ");
        
        return finalQuery;
    }
    
    private String buildCalculationQuery(String templateId, JsonNode entities) {
        String template = loadTemplate(templateId);
        
        String calculoKey = entities.path("CALCULO").asText("");
        String calculoSparql;
        switch (calculoKey) {
            case "variacao_abs": calculoSparql = "(?fechamento - ?abertura)"; break;
            case "variacao_perc": calculoSparql = "((?fechamento - ?abertura) / ?abertura)"; break;
            case "intervalo_abs": calculoSparql = "(?maximo - ?minimo)"; break;
            case "intervalo_perc": calculoSparql = "((?maximo - ?minimo) / ?abertura)"; break;
            case "variacao_abs_abs": calculoSparql = "ABS(?fechamento - ?abertura)"; break;
            default: calculoSparql = "";
        }
        template = template.replace("#CALCULO#", calculoSparql);

        if (entities.has("NOME_SETOR")) {
            JsonNode setorNode = entities.get("NOME_SETOR");
            String setorFilter;
            if (setorNode.isArray()) {
                List<String> setores = objectMapper.convertValue(setorNode, new TypeReference<List<String>>() {});
                String setorList = setores.stream().map(s -> "\"" + s + "\"@pt").collect(Collectors.joining(", "));
                setorFilter = "?S1 P9 ?S4 . \n    ?S4 P7 ?setorLabel . \n    FILTER(?setorLabel IN (" + setorList + "))";
            } else {
                String nomeSetor = setorNode.asText();
                setorFilter = "?S1 P9 ?S4 . \n    ?S4 P7 \"" + nomeSetor + "\"@pt .";
            }
            template = template.replace("#SETOR_FILTER_BLOCK#", setorFilter);
        } else {
            template = template.replace("#SETOR_FILTER_BLOCK#", "?S1 P7 ?label . \n    FILTER(REGEX(STR(?label), \"#ENTIDADE_NOME#\", \"i\"))");
        }
        
        if (entities.has("ENTIDADE_NOME")) template = template.replace("#ENTIDADE_NOME#", entities.get("ENTIDADE_NOME").asText());
        if (entities.has("DATA")) template = template.replace("#DATA#", entities.get("DATA").asText());
        
        template = template.replace("#ORDEM#", entities.path("ORDEM").asText("DESC"));
        template = template.replace("#LIMITE#", entities.path("LIMITE").asText("1"));
        
        return placeholderService.replaceGenericPlaceholders(template);
    }
    
    private String replaceSimplePlaceholders(String template, JsonNode entities) {
        String finalQuery = template;
        Iterator<Map.Entry<String, JsonNode>> fields = entities.fields();
        while (fields.hasNext()) {
            Map.Entry<String, JsonNode> field = fields.next();
            String placeholder = "#" + field.getKey() + "#"; 
            String value = field.getValue().asText();
            if (field.getKey().equals("VALOR_DESEJADO")) {
                String predicadoRDF = placeholderService.getPlaceholderValue(value);
                if (predicadoRDF != null) finalQuery = finalQuery.replace(placeholder, predicadoRDF);
            } else {
                finalQuery = finalQuery.replace(placeholder, value);
            }
        }
        finalQuery = finalQuery.replaceAll("#[A-Z_]+#", "");
        return placeholderService.replaceGenericPlaceholders(finalQuery);
    }
    
    private String callNlpService(String query) throws IOException, InterruptedException {
        String jsonBody = "{\"question\": \"" + query.replace("\"", "\\\"") + "\"}";
        HttpRequest request = HttpRequest.newBuilder().uri(URI.create(NLP_SERVICE_URL)).header("Content-Type", "application/json").POST(HttpRequest.BodyPublishers.ofString(jsonBody)).build();
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) { throw new IOException("Serviço NLP falhou com status " + response.statusCode()); }
        return response.body();
    }
    
    private String loadTemplate(String templateName) {
        String path = "/Templates/" + templateName + ".txt";
        try (InputStream is = SPARQLProcessor.class.getResourceAsStream(path)) {
            if (is == null) throw new IOException("Arquivo de template não encontrado: " + path);
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
                return reader.lines().collect(Collectors.joining(System.lineSeparator()));
            }
        } catch (IOException e) {
            throw new RuntimeException("Falha ao carregar template: " + path, e);
        }
    }
}