package com.example.Programa_heber.service;

import com.example.Programa_heber.model.ProcessamentoDetalhadoResposta;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.util.Iterator;
import java.util.Map;

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

    /**
     * Gera a consulta SPARQL e retorna um objeto de resposta detalhado.
     * @param naturalLanguageQuery A pergunta do usuário.
     * @return Um objeto ProcessamentoDetalhadoResposta contendo a query, o ID do template ou um erro.
     */
    public ProcessamentoDetalhadoResposta generateSparqlQuery(String naturalLanguageQuery) {
        logger.info("Iniciando geração de query para: '{}'", naturalLanguageQuery);
        ProcessamentoDetalhadoResposta resposta = new ProcessamentoDetalhadoResposta();

        try {
            String nlpResponseJson = callNlpService(naturalLanguageQuery);
            logger.info("Resposta do NLP: {}", nlpResponseJson);

            JsonNode rootNode = objectMapper.readTree(nlpResponseJson);
            String templateId = rootNode.path("templateId").asText();
            JsonNode entitiesNode = rootNode.path("entities");

            if (templateId.isEmpty() || templateId.equals("template_desconhecido")) {
                resposta.setErro("NLP não conseguiu determinar um template válido.");
                return resposta;
            }

            String templateContent = loadTemplate(templateId);
            String queryWithEntities = replaceEntityPlaceholders(templateContent, entitiesNode);
            String finalQuery = placeholderService.replaceGenericPlaceholders(queryWithEntities);

            resposta.setSparqlQuery(finalQuery);
            resposta.setTemplateId(templateId); // Passa o ID do template para o frontend

            logger.info("Consulta SPARQL final gerada:\n{}", finalQuery);
            return resposta;

        } catch (Exception e) {
            logger.error("Erro fatal ao gerar query para '{}': {}", naturalLanguageQuery, e.getMessage(), e);
            resposta.setErro("Erro ao processar a pergunta: " + e.getMessage());
            return resposta;
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
        ClassPathResource resource = new ClassPathResource("Templates/" + templateName + ".txt");
        if (!resource.exists()) {
             throw new IOException("Arquivo de template não encontrado: Templates/" + templateName + ".txt");
        }
        try (InputStream inputStream = resource.getInputStream()) {
            return new String(inputStream.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    private String replaceEntityPlaceholders(String template, JsonNode entities) {
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
}