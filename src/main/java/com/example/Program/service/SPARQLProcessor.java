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
            String finalQuery = buildQuery(templateContent, entitiesNode);

            resposta.setSparqlQuery(finalQuery);
            resposta.setTemplateId(templateId);
            
            // Passa o tipo da métrica para o objeto de resposta
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
        
        String entidadeFilter = "";
        if (entities.has("ENTIDADE_NOME")) {
            entidadeFilter = "?S1 rdfs:label ?label . \n    FILTER(REGEX(STR(?label), \"" + entities.get("ENTIDADE_NOME").asText() + "\", \"i\"))";
        }
        query = query.replace("#FILTER_BLOCK_ENTIDADE#", entidadeFilter);

        String setorFilter = "";
        if (entities.has("NOME_SETOR")) {
            JsonNode setorNode = entities.get("NOME_SETOR");
            String subjectVariable = query.contains("?S1_rank") ? "?S1_rank" : "?S1";
            if (setorNode.isArray()) {
                List<String> setores = new ArrayList<>();
                for (JsonNode setor : setorNode) {
                    setores.add("\"" + setor.asText() + "\"@pt");
                }
                String inClause = String.join(", ", setores);
                setorFilter = subjectVariable + " b3:atuaEm ?setor . \n    ?setor rdfs:label ?label . \n    FILTER(?label IN (" + inClause + "))";
            } else {
                String nomeSetor = setorNode.asText();
                setorFilter = subjectVariable + " b3:atuaEm ?setor . \n    ?setor rdfs:label \"" + nomeSetor + "\"@pt .";
            }
        }
        query = query.replace("#FILTER_BLOCK_SETOR#", setorFilter);

        if (entities.has("REGEX_PATTERN")) {
            String regexFilter = "FILTER(REGEX(STR(?ticker), \"" + entities.get("REGEX_PATTERN").asText() + "\"))";
            query = query.replace("#REGEX_FILTER#", regexFilter);
        } else {
            query = query.replace("#REGEX_FILTER#", "");
        }
        
        if (query.contains("#FILTER_BLOCK#")) {
            String filterBlock4C = !setorFilter.isEmpty() ? setorFilter : entidadeFilter;
            query = query.replace("#FILTER_BLOCK#", filterBlock4C);
        }

        query = placeholderService.replaceGenericPlaceholders(query);
        
        Iterator<Map.Entry<String, JsonNode>> fields = entities.fields();
        while (fields.hasNext()) {
            Map.Entry<String, JsonNode> field = fields.next();
            String placeholder = "#" + field.getKey().toUpperCase() + "#";
            String value = field.getValue().asText();

            if (placeholder.equals("#VALOR_DESEJADO#")) {
                String predicadoRDF = placeholderService.getPlaceholderValue(value);
                if (predicadoRDF != null) query = query.replace(placeholder, predicadoRDF);
            } else if (placeholder.equals("#CALCULO#")) {
                String calculoSparql;
                // --- INÍCIO DA CORREÇÃO DAS FÓRMULAS ---
                switch (value) {
                    // Variação é Fechamento - Abertura
                    case "variacao_abs":   calculoSparql = "(?fechamento - ?abertura)"; break;
                    case "variacao_perc":  calculoSparql = "((?fechamento - ?abertura) / ?abertura) * 100"; break;
                    
                    // Intervalo é Máximo - Mínimo
                    case "intervalo_abs":  calculoSparql = "(?maximo - ?minimo)"; break;
                    case "intervalo_perc": calculoSparql = "((?maximo - ?minimo) / ?abertura) * 100"; break;

                    // Variação absoluta (sem sinal) para "menor variação"
                    case "variacao_abs_abs": calculoSparql = "ABS(?fechamento - ?abertura)"; break;
                    
                    default: calculoSparql = "0";
                }
                // --- FIM DA CORREÇÃO DAS FÓRMULAS ---
                query = query.replace(placeholder, calculoSparql);
            } else {
                query = query.replace(placeholder, value);
            }
        }
        
        return query.replaceAll("#[A-Z_]+#", ""); 
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