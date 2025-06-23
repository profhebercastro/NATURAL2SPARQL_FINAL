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
import java.util.List;
import java.util.Map;
import java.util.StringJoiner;
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
            Resource resource = new ClassPathResource(PYTHON_SCRIPT_NAME);
            if (!resource.exists()) {
                logger.warn("Script Python '{}' não encontrado na raiz de 'resources/'. Verifique o caminho.", PYTHON_SCRIPT_NAME);
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
        respostaDetalhada.setSparqlQuery(sparqlQueryGerada);

        if (this.pythonScriptPath == null || !Files.exists(this.pythonScriptPath)) {
            respostaDetalhada.setErro("Erro crítico interno: Componente de PLN não está disponível.");
            return respostaDetalhada;
        }

        try {
            Map<String, Object> resultadoPython = executePythonScript(question);
            
            if (resultadoPython.containsKey("erro")) {
                respostaDetalhada.setErro("Falha no PLN: " + resultadoPython.get("erro"));
                return respostaDetalhada;
            }

            String templateId = (String) resultadoPython.get("template_nome");
            @SuppressWarnings("unchecked")
            Map<String, String> placeholders = (Map<String, String>) resultadoPython.get("mapeamentos");

            if (templateId == null || placeholders == null) {
                respostaDetalhada.setErro("Não foi possível determinar o tipo da pergunta ou extrair detalhes.");
                return respostaDetalhada;
            }

            logger.info("Python retornou: Template ID='{}', Placeholders={}", templateId, placeholders);

            String conteudoTemplate = readTemplateContent(templateId);
            sparqlQueryGerada = buildSparqlQuery(conteudoTemplate, placeholders);
            respostaDetalhada.setSparqlQuery(sparqlQueryGerada);
            logger.info("SPARQL Gerada:\n---\n{}\n---", sparqlQueryGerada);

            List<Map<String, String>> resultados = ontology.executeQuery(sparqlQueryGerada);

            if (resultados == null) {
                respostaDetalhada.setErro("Erro ao executar a consulta na base de conhecimento.");
            } else if (resultados.isEmpty()) {
                respostaDetalhada.setResposta("Não foram encontrados resultados para sua pergunta.");
            } else {
                String respostaFormatada = formatarResultados(resultados, templateId);
                respostaDetalhada.setResposta(respostaFormatada);
                logger.info("Resultados formatados: {}", respostaFormatada);
            }
        } catch (Exception e) {
            logger.error("Erro GENÉRICO ao processar '{}': {}", question, e.getMessage(), e);
            respostaDetalhada.setErro("Erro inesperado no servidor: " + e.getMessage());
        }
        
        return respostaDetalhada;
    }

    private String formatarResultados(List<Map<String, String>> resultados, String templateId) {
        if (resultados == null || resultados.isEmpty()) {
            return "Nenhum resultado encontrado.";
        }
        
        StringJoiner joiner;
        
        // Formato para múltiplas colunas (Template_4A)
        if ("Template_4A".equals(templateId)) {
            joiner = new StringJoiner("\n"); // Resposta em múltiplas linhas
            for (Map<String, String> row : resultados) {
                String ticker = row.getOrDefault("ticker", "?");
                String volume = row.getOrDefault("volume", "?");
                joiner.add(ticker + " - " + volume);
            }
            return joiner.toString();
        }

        // Para todos os outros, a resposta é uma lista de valores separados por vírgula
        joiner = new StringJoiner(", ");
        if (!resultados.isEmpty()) {
            // Pega o nome da primeira variável de resultado para ser genérico
            String varName = resultados.get(0).keySet().stream().findFirst().orElse("valor");
            
            for (Map<String, String> row : resultados) {
                String valor = row.getOrDefault(varName, "");
                if (!valor.isEmpty()) {
                    joiner.add(limparValor(valor));
                }
            }
        }
        return joiner.toString();
    }

    private String limparValor(String item) {
        if (item == null) return "";
        // Remove os sufixos de tipo de dado do XML Schema e o prefixo da ontologia
        String limpo = item.replaceAll("\\^\\^<http://www.w3.org/2001/XMLSchema#.*?>", "");
        if (limpo.startsWith(BASE_ONTOLOGY_URI)) {
            limpo = limpo.substring(BASE_ONTOLOGY_URI.length());
        }
        return limpo.trim();
    }

    private String buildSparqlQuery(String templateContent, Map<String, String> placeholders) {
        String queryAtual = templateContent;
        if (placeholders == null) return queryAtual;

        for (Map.Entry<String, String> entry : placeholders.entrySet()) {
            String phKey = entry.getKey();
            String phValue = entry.getValue();

            if (phValue != null && queryAtual.contains(phKey)) {
                String valorSubstituicao;
                
                switch (phKey) {
                    case "#DATA#":
                        valorSubstituicao = "\"" + phValue + "\"^^xsd:date";
                        break;
                    case "#VALOR_DESEJADO#":
                        valorSubstituicao = "b3:" + phValue;
                        break;
                    default: // Trata #ENTIDADE_NOME# e #SETOR# como literais string
                        // Lida com o caso especial de tag de idioma
                        if (templateContent.contains(phKey + "@pt")) {
                             queryAtual = queryAtual.replace(phKey + "@pt", "\"" + phValue.replace("\"", "\\\"") + "\"@pt");
                             continue; // Pula a substituição padrão abaixo para evitar duplicidade
                        }
                        valorSubstituicao = "\"" + phValue.replace("\"", "\\\"") + "\"";
                        break;
                }
                queryAtual = queryAtual.replace(phKey, valorSubstituicao);
            }
        }
        return queryAtual;
    }

    private Map<String, Object> executePythonScript(String question) throws IOException, InterruptedException {
        String pythonExec = System.getProperty("python.executable", "python3");
        Path pythonExecPath = Paths.get(pythonExec);
        if (!Files.exists(pythonExecPath)) {
            pythonExec = "python"; // Fallback para 'python' se 'python3' não for encontrado
        }

        ProcessBuilder pb = new ProcessBuilder(pythonExec, this.pythonScriptPath.toString(), question);
        pb.environment().put("PYTHONIOENCODING", "UTF-8");
        logger.info("Executando comando Python: {}", pb.command());
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
        if (stdoutResult.isEmpty()) {
            throw new RuntimeException("Script Python não retornou nenhuma saída.");
        }
        
        return new ObjectMapper().readValue(stdoutResult, new TypeReference<>() {});
    }

    public String readTemplateContent(String templateId) throws IOException {
        String templateFileName = templateId.replace(" ", "_") + ".txt";
        String templateResourcePath = "templates/" + templateFileName;
        Resource resource = new ClassPathResource(templateResourcePath);
        if (!resource.exists()) {
            throw new FileNotFoundException("Template SPARQL não encontrado: " + templateResourcePath);
        }
        try (InputStream inputStream = resource.getInputStream()) {
            return new String(inputStream.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}