package com.example.Programa_heber.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Iterator;
import java.util.Map;

@Service
public class SPARQLProcessor {

    private static final Logger logger = LoggerFactory.getLogger(SPARQLProcessor.class);
    
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;
    private final PlaceholderService placeholderService; // Injetando o novo serviço

    private static final String NLP_SERVICE_URL = "http://localhost:5000/process_question";

    @Autowired
    public SPARQLProcessor(PlaceholderService placeholderService) {
        this.httpClient = HttpClient.newHttpClient();
        this.objectMapper = new ObjectMapper();
        this.placeholderService = placeholderService;
    }

    public String generateSparqlQuery(String naturalLanguageQuery) {
        logger.info("Iniciando geração de query para: '{}'", naturalLanguageQuery);

        try {
            // ETAPA 1: Chamar o serviço NLP para obter o template e as entidades
            String nlpResponseJson = callNlpService(naturalLanguageQuery);
            logger.info("Resposta do NLP: {}", nlpResponseJson);

            JsonNode rootNode = objectMapper.readTree(nlpResponseJson);
            String templateId = rootNode.path("templateId").asText();
            JsonNode entitiesNode = rootNode.path("entities");

            if (templateId.isEmpty() || templateId.equals("template_desconhecido")) {
                throw new RuntimeException("NLP não conseguiu determinar um template válido.");
            }

            // ETAPA 2: Carregar o conteúdo do template genérico
            String templateContent = loadTemplate(templateId);

            // ETAPA 3: Primeira substituição - Entidades específicas da pergunta (#ENTIDADE_NOME#, #DATA#, etc.)
            String queryWithEntities = replaceEntityPlaceholders(templateContent, entitiesNode);
            
            // ETAPA 4: Segunda substituição - Placeholders genéricos (P1, S1, etc.)
            String finalQuery = placeholderService.replaceGenericPlaceholders(queryWithEntities);

            logger.info("Consulta SPARQL final gerada:\n{}", finalQuery);
            return finalQuery;

        } catch (Exception e) {
            logger.error("Erro fatal ao gerar query para '{}': {}", naturalLanguageQuery, e.getMessage(), e);
            return "Erro ao processar a pergunta: " + e.getMessage();
        }
    }

    private String callNlpService(String query) throws IOException, InterruptedException {
        String jsonBody = "{\"question\": \"" + query.replace("\"", "\\\"") + "\"}";
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(NLP_SERVICE_URL))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(jsonBody, StandardCharsets.UTF_8))
                .build();
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) {
            throw new IOException("Serviço NLP falhou com status " + response.statusCode() + " e corpo: " + response.body());
        }
        return response.body();
    }

    private String loadTemplate(String templateName) throws IOException {
        Path path = new ClassPathResource("Templates/" + templateName + ".txt").getFile().toPath();
        return Files.readString(path, StandardCharsets.UTF_8);
    }

    private String replaceEntityPlaceholders(String template, JsonNode entities) {
        String finalQuery = template;
        
        // Itera sobre as entidades encontradas (ENTIDADE_NOME, DATA, TICKER, etc.)
        Iterator<Map.Entry<String, JsonNode>> fields = entities.fields();
        while (fields.hasNext()) {
            Map.Entry<String, JsonNode> field = fields.next();
            // O placeholder no template tem o formato #CHAVE#
            String placeholder = "#" + field.getKey() + "#";
            String value = field.getValue().asText();
            finalQuery = finalQuery.replace(placeholder, value);
        }
        return finalQuery;
    }
}