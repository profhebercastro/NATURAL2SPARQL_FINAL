package com.example.Programa_heber.service;

import com.example.Programa_heber.ontology.Ontology;
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
    private final Ontology ontology; // Supondo que a ontologia é injetada
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper; // Para parsear JSON

    // URL do nosso serviço de NLP rodando no mesmo ambiente Docker
    private static final String NLP_SERVICE_URL = "http://localhost:5000/process_question";

    @Autowired
    public SPARQLProcessor(Ontology ontology) {
        this.ontology = ontology;
        this.httpClient = HttpClient.newHttpClient();
        this.objectMapper = new ObjectMapper(); // Jackson's JSON mapper
    }

    public String generateSparqlQuery(String naturalLanguageQuery) {
        logger.info("Iniciando geração de query para: '{}'", naturalLanguageQuery);

        try {
            // ETAPA 1: Chamar o serviço NLP via API HTTP
            String nlpResponseJson = callNlpService(naturalLanguageQuery);
            logger.info("Resposta recebida do serviço NLP: {}", nlpResponseJson);

            // ETAPA 2: Parsear a resposta JSON do serviço Python
            JsonNode rootNode = objectMapper.readTree(nlpResponseJson);
            String templateName = rootNode.path("template").asText();
            JsonNode entitiesNode = rootNode.path("entities");

            if (templateName == null || templateName.isEmpty() || templateName.equals("template_desconhecido")) {
                throw new RuntimeException("Serviço NLP não conseguiu determinar um template válido.");
            }

            // ETAPA 3: Carregar o template SPARQL correspondente
            String templateContent = loadTemplate(templateName);

            // ETAPA 4: Substituir os placeholders no template com as entidades
            String finalQuery = replacePlaceholders(templateContent, entitiesNode);

            logger.info("Consulta SPARQL final gerada:\n{}", finalQuery);
            return finalQuery;

        } catch (Exception e) {
            logger.error("Erro fatal ao gerar query para '{}': {}", naturalLanguageQuery, e.getMessage(), e);
            // Retorna uma mensagem de erro amigável para a interface
            return "Erro ao processar a pergunta. Verifique os logs do servidor para mais detalhes.";
        }
    }

    private String callNlpService(String query) throws IOException, InterruptedException {
        // Cria o corpo da requisição JSON: {"question": "..."}
        String jsonBody = "{\"question\": \"" + escapeJson(query) + "\"}";

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(NLP_SERVICE_URL))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(jsonBody, StandardCharsets.UTF_8))
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new IOException("Serviço NLP falhou com status " + response.statusCode() + ". Resposta: " + response.body());
        }

        return response.body();
    }

    private String loadTemplate(String templateName) throws IOException {
        // O caminho para os templates dentro da pasta de recursos
        Path path = Paths.get("src/main/resources/Templates/" + templateName + ".txt");
        if (!Files.exists(path)) {
             throw new IOException("Arquivo de template não encontrado: " + path);
        }
        return Files.readString(path, StandardCharsets.UTF_8);
    }

    private String replacePlaceholders(String template, JsonNode entities) {
        String finalQuery = template;
        
        // Itera sobre todas as entidades encontradas (empresa, data, codigo, etc.)
        Iterator<Map.Entry<String, JsonNode>> fields = entities.fields();
        while (fields.hasNext()) {
            Map.Entry<String, JsonNode> field = fields.next();
            String placeholder = "{" + field.getKey() + "}";
            String value = field.getValue().asText();
            finalQuery = finalQuery.replace(placeholder, value);
        }
        
        return finalQuery;
    }

    // Função utilitária para escapar aspas em uma string para criar um JSON válido
    private String escapeJson(String text) {
        return text.replace("\"", "\\\"");
    }
}