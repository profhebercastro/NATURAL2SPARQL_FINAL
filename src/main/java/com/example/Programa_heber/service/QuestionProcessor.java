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

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.StringJoiner;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

@Service
public class QuestionProcessor {

    private static final Logger logger = LoggerFactory.getLogger(QuestionProcessor.class);
    private static final String PYTHON_SCRIPT_NAME = "pln_processor.py";
    private static final String BASE_ONTOLOGY_URI = "https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#";

    @Autowired
    private Ontology ontology;

    private Path pythonScriptPath;

    @PostConstruct
    public void initialize() {
        logger.info("Iniciando QuestionProcessor (@PostConstruct)...");
        try {
            Resource resource = new ClassPathResource("scripts/" + PYTHON_SCRIPT_NAME);
            if (!resource.exists()) {
                logger.warn("Script Python '{}' não encontrado em 'resources/scripts/'. Tentando na raiz de 'resources'.", PYTHON_SCRIPT_NAME);
                resource = new ClassPathResource(PYTHON_SCRIPT_NAME);
            }

            if (!resource.exists()) {
                logger.error("CRÍTICO: Script Python '{}' não encontrado no classpath. Processamento falhará.", PYTHON_SCRIPT_NAME);
                throw new FileNotFoundException("Script Python essencial não encontrado: " + PYTHON_SCRIPT_NAME);
            }

            if (resource.getURI().toString().startsWith("jar:")) {
                Path tempDir = Files.createTempDirectory("pyscripts_temp_");
                this.pythonScriptPath = tempDir.resolve(PYTHON_SCRIPT_NAME);
                try (InputStream inputStream = resource.getInputStream()) {
                    Files.copy(inputStream, this.pythonScriptPath);
                }
                this.pythonScriptPath.toFile().setExecutable(true, false);
                this.pythonScriptPath.toFile().deleteOnExit();
            } else {
                this.pythonScriptPath = Paths.get(resource.getURI());
            }
            logger.info("QuestionProcessor inicializado. Path do script Python: {}", this.pythonScriptPath);
        } catch (IOException e) {
            logger.error("CRÍTICO: Erro de IO ao inicializar QuestionProcessor: {}. Processamento indisponível.", e.getMessage(), e);
            this.pythonScriptPath = null;
        }
    }

    public ProcessamentoDetalhadoResposta processQuestion(String question) {
        logger.info("Serviço QuestionProcessor: Iniciando processamento da pergunta: '{}'", question);
        ProcessamentoDetalhadoResposta respostaDetalhada = new ProcessamentoDetalhadoResposta();
        String sparqlQueryGerada = "N/A - Query não gerada.";

        if (this.pythonScriptPath == null || !Files.exists(this.pythonScriptPath)) {
            respostaDetalhada.setErro("Erro crítico interno: Componente de PLN não está disponível.");
            respostaDetalhada.setSparqlQuery(sparqlQueryGerada);
            return respostaDetalhada;
        }

        try {
            Map<String, Object> resultadoPython = executePythonScript(question);
            ObjectMapper objectMapper = new ObjectMapper();

            String templateId = (String) resultadoPython.get("template_nome");
            @SuppressWarnings("unchecked")
            Map<String, String> placeholders = (Map<String, String>) resultadoPython.get("mapeamentos");

            if (resultadoPython.containsKey("erro")) {
                respostaDetalhada.setErro("Falha no PLN: " + resultadoPython.get("erro"));
                return respostaDetalhada;
            }

            if (templateId == null || placeholders == null) {
                respostaDetalhada.setErro("Não foi possível determinar o tipo da pergunta ou extrair detalhes.");
                return respostaDetalhada;
            }

            logger.info("Python: Template='{}', Placeholders={}", templateId, placeholders);

            String conteudoTemplate = readTemplateContent(templateId);
            sparqlQueryGerada = buildSparqlQuery(conteudoTemplate, placeholders, templateId);
            respostaDetalhada.setSparqlQuery(sparqlQueryGerada);
            logger.info("SPARQL Gerada:\n---\n{}\n---", sparqlQueryGerada);

            List<Map<String, String>> resultados = ontology.executeQuery(sparqlQueryGerada);

            if (resultados == null) {
                respostaDetalhada.setErro("Erro ao executar a consulta na base de conhecimento.");
            } else if (resultados.isEmpty()) {
                respostaDetalhada.setResposta("Não foram encontrados resultados.");
            } else {
                String respostaFormatada = formatarResultados(resultados, templateId);
                respostaDetalhada.setResposta(respostaFormatada);
                logger.info("Resultados formatados: {}", respostaFormatada);
            }
        } catch (Exception e) {
            logger.error("Erro GENÉRICO ao processar '{}': {}", question, e.getMessage(), e);
            respostaDetalhada.setErro("Erro inesperado no servidor.");
        }

        return respostaDetalhada;
    }

    private String formatarResultados(List<Map<String, String>> resultados, String templateId) {
        if (resultados == null || resultados.isEmpty()) return "";

        switch (templateId) {
            case "Template_4A":
                StringJoiner joinerMultiLinha = new StringJoiner("\n");
                for (Map<String, String> row : resultados) {
                    joinerMultiLinha.add(row.getOrDefault("codigo", "N/A") + " - " + row.getOrDefault("volume", "N/A"));
                }
                return joinerMultiLinha.toString();

            case "Template_2A":
                StringJoiner joinerVirgula2A = new StringJoiner(", ");
                for (Map<String, String> row : resultados) {
                    String ticker = row.getOrDefault("individualTicker", "");
                    if (!ticker.isEmpty()) joinerVirgula2A.add(limparValor(ticker));
                }
                return joinerVirgula2A.toString();

            default:
                StringJoiner joinerVirgulaDefault = new StringJoiner(", ");
                for (Map<String, String> row : resultados) {
                    String valor = row.getOrDefault("valor", "");
                    if (!valor.isEmpty()) joinerVirgulaDefault.add(limparValor(valor));
                }
                return joinerVirgulaDefault.toString();
        }
    }

    private String limparValor(String item) {
        if (item == null) return "";
        String limpo = item.replaceAll("\\^\\^<http://www.w3.org/2001/XMLSchema#.*?>", "");
        if (limpo.startsWith(BASE_ONTOLOGY_URI)) limpo = limpo.substring(BASE_ONTOLOGY_URI.length());
        return limpo.trim();
    }

    private Map<String, Object> executePythonScript(String question) throws IOException, InterruptedException {
        String pythonExec = System.getProperty("python.executable", "python3");
        ProcessBuilder pb = new ProcessBuilder(pythonExec, this.pythonScriptPath.toString(), question);
        pb.environment().put("PYTHONIOENCODING", "UTF-8");
        Process process = pb.start();

        String stdoutResult;
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
            stdoutResult = reader.lines().collect(Collectors.joining(System.lineSeparator()));
        }

        int exitCode = process.waitFor();
        if (exitCode != 0) {
            String stderrResult;
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getErrorStream(), StandardCharsets.UTF_8))) {
                stderrResult = reader.lines().collect(Collectors.joining(System.lineSeparator()));
            }
            throw new RuntimeException("Script Python falhou com código " + exitCode + ". Erro: " + stderrResult);
        }
        return new ObjectMapper().readValue(stdoutResult, new TypeReference<>() {});
    }

    public String readTemplateContent(String templateId) throws IOException {
        String templateFileName = templateId.trim().replace(" ", "_") + ".txt";
        String templateResourcePath = "templates/" + templateFileName;
        Resource resource = new ClassPathResource(templateResourcePath);
        if (!resource.exists()) throw new FileNotFoundException("Template não encontrado: " + templateResourcePath);
        return new String(resource.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
    }

    private String buildSparqlQuery(String templateContent, Map<String, String> placeholders, String templateId) {
        String queryAtual = templateContent;
        for (Map.Entry<String, String> entry : placeholders.entrySet()) {
            String phKey = entry.getKey();
            String phValue = entry.getValue() != null ? entry.getValue() : "";
            queryAtual = queryAtual.replace(phKey, phValue.replace("\"", "\\\""));
        }
        return queryAtual;
    }
}