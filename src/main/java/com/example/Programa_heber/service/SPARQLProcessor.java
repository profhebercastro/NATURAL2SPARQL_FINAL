package com.example.Programa_heber.service;

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
    
    // Serviços e ferramentas injetados
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;
    private final PlaceholderService placeholderService; // Serviço para substituir P1, S1, etc.

    // URL do serviço de NLP rodando no mesmo ambiente
    private static final String NLP_SERVICE_URL = "http://localhost:5000/process_question";

    @Autowired
    public SPARQLProcessor(PlaceholderService placeholderService) {
        this.httpClient = HttpClient.newHttpClient();
        this.objectMapper = new ObjectMapper(); // Jackson's JSON mapper
        this.placeholderService = placeholderService;
    }

    /**
     * Orquestra a geração completa da consulta SPARQL.
     * @param naturalLanguageQuery A pergunta do usuário em linguagem natural.
     * @return A string da consulta SPARQL final e pronta para ser executada.
     */
    public String generateSparqlQuery(String naturalLanguageQuery) {
        logger.info("Iniciando geração de query para: '{}'", naturalLanguageQuery);

        try {
            // ETAPA 1: Chamar o serviço NLP para obter o ID do template e as entidades específicas.
            String nlpResponseJson = callNlpService(naturalLanguageQuery);
            logger.info("Resposta do NLP: {}", nlpResponseJson);

            // Parsear a resposta JSON do serviço Python.
            JsonNode rootNode = objectMapper.readTree(nlpResponseJson);
            String templateId = rootNode.path("templateId").asText();
            JsonNode entitiesNode = rootNode.path("entities");

            if (templateId == null || templateId.isEmpty() || templateId.equals("template_desconhecido")) {
                throw new RuntimeException("NLP não conseguiu determinar um template válido.");
            }

            // ETAPA 2: Carregar o conteúdo do template genérico a partir do seu ID.
            String templateContent = loadTemplate(templateId);

            // ETAPA 3: Primeira substituição - Entidades específicas da pergunta (#ENTIDADE_NOME#, #DATA#, etc.).
            String queryWithEntities = replaceEntityPlaceholders(templateContent, entitiesNode);
            
            // ETAPA 4: Segunda substituição - Placeholders genéricos (P1, S1, etc.) usando o PlaceholderService.
            String finalQuery = placeholderService.replaceGenericPlaceholders(queryWithEntities);

            logger.info("Consulta SPARQL final gerada:\n{}", finalQuery);
            return finalQuery;

        } catch (Exception e) {
            logger.error("Erro fatal ao gerar query para '{}': {}", naturalLanguageQuery, e.getMessage(), e);
            return "Erro ao processar a pergunta: " + e.getMessage();
        }
    }

    /**
     * Faz uma chamada HTTP POST para o serviço de NLP em Python.
     * @param query A pergunta do usuário.
     * @return A resposta JSON do serviço NLP como uma String.
     */
    private String callNlpService(String query) throws IOException, InterruptedException {
        // Escapa as aspas na pergunta para criar um corpo JSON válido.
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

    /**
     * Carrega o conteúdo de um arquivo de template da pasta de recursos.
     * @param templateName O nome do template (ex: "Template_1A").
     * @return O conteúdo do arquivo como uma String.
     */
    private String loadTemplate(String templateName) throws IOException {
        // ClassPathResource é a forma correta de ler recursos de dentro de um JAR/classpath.
        ClassPathResource resource = new ClassPathResource("Templates/" + templateName + ".txt");
        
        if (!resource.exists()) {
             throw new IOException("Arquivo de template não encontrado: Templates/" + templateName + ".txt");
        }
        
        try (InputStream inputStream = resource.getInputStream()) {
            return new String(inputStream.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    /**
     * Realiza a primeira etapa de substituição, trocando os placeholders de entidade
     * (ex: #ENTIDADE_NOME#) pelos valores extraídos pelo NLP.
     * @param template O conteúdo do arquivo de template.
     * @param entities O nó JSON contendo as entidades.
     * @return A query com as entidades substituídas.
     */
    private String replaceEntityPlaceholders(String template, JsonNode entities) {
        String finalQuery = template;
        
        // Itera sobre todas as entidades encontradas (ENTIDADE_NOME, DATA, TICKER, VALOR_DESEJADO, etc.)
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