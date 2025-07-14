package com.example.Programa_heber.service;

import com.example.Programa_heber.model.ProcessamentoDetalhadoResposta;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
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
import java.util.Iterator;
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

            // Lógica unificada para todos os templates
            String templateContent = loadTemplate(templateId);
            String finalQuery = replacePlaceholders(templateContent, entitiesNode);
            
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
    
    private String replacePlaceholders(String template, JsonNode entities) {
        String finalQuery = template;
        
        // --- LÓGICA DE SUBSTITUIÇÃO UNIFICADA E ROBUSTA ---
        
        // 1. Substitui placeholders dinâmicos (ex: #ENTIDADE_NOME#, #DATA#, #REGEX_PATTERN#, etc.)
        Iterator<Map.Entry<String, JsonNode>> fields = entities.fields();
        while (fields.hasNext()) {
            Map.Entry<String, JsonNode> field = fields.next();
            String placeholder = "#" + field.getKey() + "#"; 
            String value = field.getValue().asText();
            
            // Tratamento especial para métricas/variações, que buscam o valor no .properties
            if (field.getKey().equals("VALOR_DESEJADO")) {
                String predicadoRDF = placeholderService.getPlaceholderValue(value);
                if (predicadoRDF != null) {
                    finalQuery = finalQuery.replace(placeholder, predicadoRDF);
                } else {
                    logger.warn("Chave de métrica '{}' não encontrada. Placeholder '{}' não será substituído.", value, placeholder);
                }
            } else {
                // Substituição direta para todos os outros placeholders dinâmicos
                finalQuery = finalQuery.replace(placeholder, value);
            }
        }
        
        // 2. Substitui placeholders de cálculo (se existirem no template)
        // Isso é feito em um passo separado para garantir que as variáveis do BIND não sejam afetadas.
        if (entities.has("CALCULO")) {
             String calculoKey = entities.get("CALCULO").asText("");
             String calculoSparql;
             switch (calculoKey) {
                 case "variacao_abs": calculoSparql = "(?fechamento - ?abertura)"; break;
                 case "variacao_perc": calculoSparql = "((?fechamento - ?abertura) / ?abertura)"; break;
                 case "intervalo_abs": calculoSparql = "(?maximo - ?minimo)"; break;
                 case "intervalo_perc": calculoSparql = "((?maximo - ?minimo) / ?abertura)"; break;
                 case "variacao_abs_abs": calculoSparql = "ABS(?fechamento - ?abertura)"; break;
                 default: calculoSparql = "0";
             }
             finalQuery = finalQuery.replace("#CALCULO#", calculoSparql);
        }

        // 3. Lógica para o bloco de filtro de setor (opcional)
        if (entities.has("NOME_SETOR")) {
            String nomeSetor = entities.get("NOME_SETOR").asText();
            String setorFilter = "?S1 P9 ?S4 . \n" +
                                 "    ?S4 P7 \"" + nomeSetor + "\"@pt .";
            finalQuery = finalQuery.replace("#SETOR_FILTER_BLOCK#", setorFilter);
        } else {
            finalQuery = finalQuery.replace("#SETOR_FILTER_BLOCK#", "");
        }
        
        // 4. Limpeza final de placeholders não utilizados
        finalQuery = finalQuery.replaceAll("#[A-Z_]+#", "");
        
        // 5. Chama o serviço que substitui os placeholders genéricos (P1, S1, etc.) e adiciona os prefixos
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