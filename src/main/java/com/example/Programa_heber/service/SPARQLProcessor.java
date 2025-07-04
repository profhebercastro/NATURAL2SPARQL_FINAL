package com.example.Programa_heber.service;

import com.example.Programa_heber.model.ProcessamentoDetalhadoResposta;
import com.example.Programa_heber.ontology.Ontology;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Service;
import org.springframework.util.StreamUtils;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.StringJoiner;
import java.util.regex.Pattern;

@Service
public class SPARQLProcessor {

    private static final Logger logger = LoggerFactory.getLogger(SPARQLProcessor.class);
    private static final String PYTHON_SCRIPT_NAME = "nlp_controller.py";
    private static final String[] PYTHON_RESOURCES = { PYTHON_SCRIPT_NAME, "Thesaurus.json" };

    @Autowired
    private Ontology ontology;

    private Path pythonScriptPath;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private static final Pattern TICKER_PATTERN = Pattern.compile("^[A-Z]{4}\\d{1,2}$");

    @PostConstruct
    public void initialize() throws IOException {
        logger.info("Iniciando SPARQLProcessor: Configurando ambiente Python...");
        try {
            Path tempDir = Files.createTempDirectory("pyscripts_temp_");
            tempDir.toFile().deleteOnExit();
            for (String fileName : PYTHON_RESOURCES) {
                Resource resource = new ClassPathResource(fileName);
                if (!resource.exists()) throw new FileNotFoundException("Recurso Python essencial não encontrado: " + fileName);
                Path destination = tempDir.resolve(fileName);
                try (InputStream inputStream = resource.getInputStream()) { Files.copy(inputStream, destination); }
                if (fileName.equals(PYTHON_SCRIPT_NAME)) {
                    this.pythonScriptPath = destination;
                    this.pythonScriptPath.toFile().setExecutable(true, false);
                }
            }
            logger.info("SPARQLProcessor inicializado com sucesso.");
        } catch (IOException e) {
            logger.error("FALHA CRÍTICA AO CONFIGURAR AMBIENTE PYTHON.", e);
            throw e;
        }
    }

    public ProcessamentoDetalhadoResposta generateSparqlQuery(String question) {
        ProcessamentoDetalhadoResposta respostaDetalhada = new ProcessamentoDetalhadoResposta();
        try {
            Map<String, Object> resultadoPython = executePythonScript(question);
            if (resultadoPython.containsKey("erro")) {
                respostaDetalhada.setErro((String) resultadoPython.get("erro"));
                return respostaDetalhada;
            }

            String templateId = (String) resultadoPython.get("template_nome");
            @SuppressWarnings("unchecked")
            Map<String, String> placeholders = (Map<String, String>) resultadoPython.get("mapeamentos");

            String conteudoTemplate = readTemplateContent(templateId);
            String sparqlQueryGerada = buildSparqlQuery(conteudoTemplate, placeholders);
            respostaDetalhada.setSparqlQuery(sparqlQueryGerada);
            respostaDetalhada.setTemplateId(templateId);

        } catch (Exception e) {
            logger.error("Erro ao GERAR query para '{}': {}", question, e.getMessage(), e);
            respostaDetalhada.setErro("Ocorreu um erro interno ao gerar a consulta.");
        }
        return respostaDetalhada;
    }
    
    // VERSÃO SIMPLIFICADA E FINAL DO buildSparqlQuery
    private String buildSparqlQuery(String templateContent, Map<String, String> placeholders) {
        String query = templateContent;

        // Substitui os placeholders do Python
        if (placeholders.containsKey("#ENTIDADE_NOME#")) {
            query = query.replace("#ENTIDADE_NOME#", formatarEntidade(placeholders.get("#ENTIDADE_NOME#")));
        }
        if (placeholders.containsKey("#SETOR#")) {
            String setor = placeholders.get("#SETOR#");
            query = query.replace("#SETOR#", "\"" + setor.replace("\"", "\\\"") + "\"@pt");
        }
        if (placeholders.containsKey("#DATA#")) {
            query = query.replace("#DATA#", "\"" + placeholders.get("#DATA#") + "\"^^xsd:date");
        }
        if (placeholders.containsKey("#VALOR_DESEJADO#")) {
            query = query.replace("#VALOR_DESEJADO#", "b3:" + placeholders.get("#VALOR_DESEJADO#"));
        }
        
        // Adiciona os prefixos no início
        String prefixes = "PREFIX b3: <https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#>\n" +
                          "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n" +
                          "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n\n";

        String finalQuery = prefixes + query;
        logger.info("Query SPARQL Final Gerada:\n{}", finalQuery);
        return finalQuery;
    }

    public String executeAndFormat(String sparqlQuery, String templateId) {
        try {
            List<Map<String, String>> resultados = ontology.executeQuery(sparqlQuery);
            return formatarResultados(resultados, templateId);
        } catch (Exception e) {
            logger.error("Erro ao EXECUTAR query: {}", e.getMessage(), e);
            return "Erro ao executar a consulta na base de conhecimento.";
        }
    }

    private String formatarResultados(List<Map<String, String>> resultados, String templateId) {
        if (resultados == null || resultados.isEmpty()) {
            return "Não foram encontrados resultados para a sua pergunta.";
        }
        
        if ("Template_4A".equals(templateId)) {
            StringJoiner joiner = new StringJoiner("\n");
            joiner.add(String.format("%-10s | %s", "Ticker", "Volume Negociado"));
            joiner.add("------------------------------------");
            for (Map<String, String> row : resultados) {
                String ticker = limparValor(row.getOrDefault("ticker", "N/A"));
                try {
                    double volumeValue = Double.parseDouble(row.getOrDefault("volume", "0"));
                    String volumeFormatado = String.format("%,.2f", volumeValue);
                    joiner.add(String.format("%-10s | %s", ticker, volumeFormatado));
                } catch (NumberFormatException e) {
                     joiner.add(String.format("%-10s | %s", ticker, row.getOrDefault("volume", "N/A")));
                }
            }
            return joiner.toString();
        }

        StringJoiner joiner = new StringJoiner(", ");
        if (!resultados.get(0).isEmpty()) {
            String varName = resultados.get(0).keySet().stream().findFirst().orElse("valor");
            for (Map<String, String> row : resultados) {
                String valor = row.getOrDefault(varName, "");
                if (valor != null && !valor.isEmpty()) {
                    joiner.add(limparValor(valor));
                }
            }
        }
        
        String resultadoFinal = joiner.toString();
        return resultadoFinal.isEmpty() ? "Não foram encontrados resultados para a sua pergunta." : resultadoFinal;
    }

    private String formatarEntidade(String entidade) {
        String entidadeEscapada = entidade.replace("\"", "\\\"");
        return TICKER_PATTERN.matcher(entidade).matches()
            ? "\"" + entidadeEscapada + "\""
            : "\"" + entidadeEscapada + "\"@pt";
    }

    private Map<String, Object> executePythonScript(String question) throws IOException, InterruptedException {
        ProcessBuilder pb = new ProcessBuilder("python3", this.pythonScriptPath.toString(), question);
        Process process = pb.start();
        String stdoutResult = StreamUtils.copyToString(process.getInputStream(), StandardCharsets.UTF_8);
        String stderrResult = StreamUtils.copyToString(process.getErrorStream(), StandardCharsets.UTF_8);
        process.waitFor();
        return objectMapper.readValue(stdoutResult, new TypeReference<>() {});
    }

    private String readTemplateContent(String templateId) throws IOException {
        String templateFileName = templateId + ".txt";
        String templateResourcePath = "Templates/" + templateFileName;
        Resource resource = new ClassPathResource(templateResourcePath);
        if (!resource.exists()) throw new FileNotFoundException("Template SPARQL não encontrado: " + templateResourcePath);
        try (InputStream inputStream = resource.getInputStream()) {
            return new String(inputStream.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
    
    private String limparValor(String item) {
        if (item == null) return "";
        return item.replaceAll("\\^\\^<http://www.w3.org/2001/XMLSchema#.*?>", "").trim();
    }
}