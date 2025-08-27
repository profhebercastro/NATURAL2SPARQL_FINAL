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
            
            if (templateContent.trim().toUpperCase().startsWith("ASK")) {
                resposta.setQueryType("ASK");
            } else {
                resposta.setQueryType("SELECT");
            }

            String finalQuery = buildQuery(templateContent, entitiesNode);
            
            resposta.setSparqlQuery(finalQuery);
            resposta.setTemplateId(templateId);
            
            if (entitiesNode.has("CALCULO")) {
                resposta.setTipoMetrica(entitiesNode.get("CALCULO").asText());
            } else if (entitiesNode.has("VALOR_DESEJADO")) {
                resposta.setTipoMetrica(entitiesNode.get("VALOR_DESEJADO").asText());
            } else if (templateId.equals("Template_2A")) {
                resposta.setTipoMetrica("metrica.codigo_negociacao");
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

        // ETAPA 1: Substituição de Blocos de Filtro
        String entidadeFilter = "";
        if (entities.has("ENTIDADE_NOME")) {
            String entidade = entities.get("ENTIDADE_NOME").asText();
            if (entidade.matches("^[A-Z]{4}[0-9]{1,2}$")) {
                entidadeFilter = "BIND(b3:" + entidade.toUpperCase() + " AS ?SO1)";
            } else {
                entidadeFilter = "?S1 P7 ?label . \n    FILTER(REGEX(STR(?label), \"" + entidade + "\", \"i\")) \n    ?S1 P1 ?SO1 .";
            }
        }
        
        String setorFilter = "";
        if (entities.has("NOME_SETOR")) {
            String nomeSetor = entities.get("NOME_SETOR").asText();
            setorFilter = "?S1 P9 ?S4 . \n    ?S4 P7 \"" + nomeSetor + "\"@pt .";
        }

        String tickersFilter = "";
        if (entities.has("LISTA_TICKERS")) {
            JsonNode tickersNode = entities.get("LISTA_TICKERS");
            if (tickersNode.isArray() && tickersNode.size() > 0) {
                List<String> uris = new ArrayList<>();
                for (JsonNode ticker : tickersNode) {
                    uris.add("b3:" + ticker.asText());
                }
                tickersFilter = "VALUES ?SO1 { " + String.join(" ", uris) + " }";
            }
        }

        String filterBlock = "";
        if (!tickersFilter.isEmpty()) filterBlock = tickersFilter;
        else if (!setorFilter.isEmpty()) filterBlock = setorFilter;
        else if (!entidadeFilter.isEmpty()) filterBlock = entidadeFilter;
        
        query = query.replace("#FILTER_BLOCK#", filterBlock);
        query = query.replace("#FILTER_BLOCK_ENTIDADE#", entidadeFilter);
        query = query.replace("#FILTER_BLOCK_SETOR#", !tickersFilter.isEmpty() ? tickersFilter : setorFilter);

        // ETAPA 2: Substituição de Placeholders Dinâmicos
        
        // --- CORREÇÃO: Renomeação dinâmica da variável de resultado ---
        String nomeVariavelResultado = "resultadoCalculado"; // Nome padrão
        if (entities.has("CALCULO")) {
            nomeVariavelResultado = toCamelCase(entities.get("CALCULO").asText());
        } else if (entities.has("VALOR_DESEJADO")) {
            nomeVariavelResultado = toCamelCase(entities.get("VALOR_DESEJADO").asText());
        }
        query = query.replace("?resultadoCalculado", "?" + nomeVariavelResultado);
        // --- FIM DA CORREÇÃO ---
        
        Iterator<Map.Entry<String, JsonNode>> fields = entities.fields();
        while (fields.hasNext()) {
            Map.Entry<String, JsonNode> field = fields.next();
            String placeholder = "#" + field.getKey().toUpperCase() + "#";
            String value = field.getValue().asText();

            switch (placeholder) {
                case "#VALOR_DESEJADO#":
                    String predicadoRDF = placeholderService.getPlaceholderValue(value);
                    if (predicadoRDF != null) {
                        query = query.replace(placeholder, predicadoRDF);
                        String varName = toCamelCase(value);
                        query = query.replace("?valor", "?" + varName).replace("?ANS", "?" + varName);
                    }
                    break;
                case "#CALCULO#":
                    String calculoSparql = getFormulaCalculo(value, "");
                    query = query.replace(placeholder, calculoSparql);
                    break;
                case "#RANKING_CALCULATION#":
                    String rankingCalculoSql = getFormulaCalculo(value, "_rank");
                    query = query.replace(placeholder, rankingCalculoSql);
                    break;
                case "#REGEX_PATTERN#":
                    String regexFilter = "FILTER(REGEX(STR(?ticker), \"" + value + "\"))";
                    query = query.replace("#REGEX_FILTER#", regexFilter);
                    break;
                default:
                    query = query.replace(placeholder, value);
                    break;
            }
        }
        
        // ETAPA 3: Limpeza e Finalização
        query = query.replaceAll("#[A-Z_]+#", ""); 
        query = placeholderService.replaceGenericPlaceholders(query);
        String prefixes = placeholderService.getPrefixes();

        return prefixes + query;
    }

    private String getFormulaCalculo(String calculoKey, String suffix) {
        switch (calculoKey) {
            // Cálculos compostos
            case "variacao_abs": return "ABS(?fechamento" + suffix + " - ?abertura" + suffix + ")";
            case "variacao_perc": return "((?fechamento" + suffix + " - ?abertura" + suffix + ") / ?abertura" + suffix + ") * 100";
            case "intervalo_abs": return "ABS(?maximo" + suffix + " - ?minimo" + suffix + ")";
            case "intervalo_perc": return "((?maximo" + suffix + " - ?minimo" + suffix + ") / ?abertura" + suffix + ") * 100";
            
            // Mapeamento de métricas simples para variáveis de ordenação
            case "preco_fechamento": return "?fechamento" + suffix;
            case "volume": return "?volumeNegociacao" + suffix;
            case "preco_abertura": return "?abertura" + suffix;
            case "preco_maximo": return "?maximo" + suffix;
            case "preco_minimo": return "?minimo" + suffix;
            
            default: return "?undefinedCalculation";
        }
    }

    private String toCamelCase(String text) {
        if (text == null || text.isEmpty()) { return ""; }
        String cleanText = text.replaceAll("^(metrica\\.|b3:)", "");
        StringBuilder camelCase = new StringBuilder();
        boolean nextIsUpper = false;
        for (char c : cleanText.toCharArray()) {
            if (c == '_') {
                nextIsUpper = true;
            } else {
                if (nextIsUpper) {
                    camelCase.append(Character.toUpperCase(c));
                    nextIsUpper = false;
                } else {
                    camelCase.append(camelCase.length() == 0 ? Character.toLowerCase(c) : c);
                }
            }
        }
        return camelCase.toString();
    }

    private String callNlpService(String query) throws IOException, InterruptedException {
        String jsonBody = objectMapper.createObjectNode().put("question", query).toString();
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(NLP_SERVICE_URL))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(jsonBody))
                .build();
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
                return reader.lines().collect(Collectors.joining(System.lineSeparator()));
            }
        } catch (IOException e) {
            throw new RuntimeException("Falha ao carregar template: " + path, e);
        }
    }
}