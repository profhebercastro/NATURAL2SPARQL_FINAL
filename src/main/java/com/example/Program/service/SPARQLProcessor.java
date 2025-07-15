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
    // Garanta que esta URL esteja correta para o seu ambiente
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
            if ("Template_6A".equals(templateId) || "Template_7A".equals(templateId) || "Template_8A".equals(templateId) || "Template_8B".equals(templateId)) {
                finalQuery = buildCalculationQuery(templateContent, entitiesNode);
            } else {
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

    private String buildCalculationQuery(String template, JsonNode entities) {
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
        String query = template.replace("#CALCULO#", calculoSparql);

        // **LÓGICA CENTRAL PARA LIDAR COM O ARRAY "IMAT"**
        if (entities.has("NOME_SETOR")) {
            JsonNode setorNode = entities.get("NOME_SETOR");
            String setorFilter;

            if (setorNode.isArray()) { // --> Esta condição será VERDADEIRA para a pergunta do IMAT
                List<String> setores = new ArrayList<>();
                // Itera sobre o array ["Materiais Básicos", "Minerais Metálicos", ...]
                for (JsonNode setor : setorNode) {
                    // Formata cada um para a sintaxe SPARQL: "Nome do Setor"@pt
                    setores.add("\"" + setor.asText() + "\"@pt");
                }
                // Junta todos com vírgula: "Setor1"@pt, "Setor2"@pt, ...
                String inClause = String.join(", ", setores);
                
                // Determina a variável correta a ser usada no filtro (para subqueries ou não)
                String subjectVariable = query.contains("?S1_rank") ? "?S1_rank" : "?S1";
                
                // Monta o filtro SPARQL com a cláusula IN
                setorFilter = subjectVariable + " P9 ?S4 . \n    ?S4 P7 ?label . \n    FILTER(?label IN (" + inClause + "))";
            } else { // Fallback para o caso de ser um único setor (string)
                String nomeSetor = setorNode.asText();
                String subjectVariable = query.contains("?S1_rank") ? "?S1_rank" : "?S1";
                setorFilter = subjectVariable + " P9 ?S4 . \n    ?S4 P7 \"" + nomeSetor + "\"@pt .";
            }
            query = query.replace("#SETOR_FILTER_BLOCK#", setorFilter);
        } else {
            query = query.replace("#SETOR_FILTER_BLOCK#", "");
        }

        if (entities.has("ENTIDADE_NOME")) query = query.replace("#ENTIDADE_NOME#", entities.get("ENTIDADE_NOME").asText());
        if (entities.has("DATA")) query = query.replace("#DATA#", entities.get("DATA").asText());
        query = query.replace("#ORDEM#", entities.path("ORDEM").asText("DESC"));
        query = query.replace("#LIMITE#", entities.path("LIMITE").asText("1"));

        return placeholderService.replaceGenericPlaceholders(query);
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
                             .map(String::trim)
                             .filter(line -> !line.startsWith("#") && !line.isEmpty())
                             .collect(Collectors.joining(System.lineSeparator()));
            }
        } catch (IOException e) {
            throw new RuntimeException("Falha ao carregar template: " + path, e);
        }
    }
}