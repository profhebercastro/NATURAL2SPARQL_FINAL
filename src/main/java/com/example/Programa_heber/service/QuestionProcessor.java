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

@Service
public class QuestionProcessor {

    private static final Logger logger = LoggerFactory.getLogger(QuestionProcessor.class);
    private static final String PYTHON_SCRIPT_NAME = "pln_processor.py";
    private static final String BASE_ONTOLOGY_URI = "https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#";
    private static final String[] PYTHON_RESOURCES = {
        PYTHON_SCRIPT_NAME, "perguntas_de_interesse.txt", "sinonimos_map.txt",
        "empresa_nome_map.json", "setor_map.json"
    };

    @Autowired
    private Ontology ontology;

    private Path pythonScriptPath;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @PostConstruct
    public void initialize() throws IOException {
        logger.info("Iniciando QuestionProcessor (@PostConstruct): Configurando ambiente Python...");
        try {
            Path tempDir = Files.createTempDirectory("pyscripts_temp_");
            tempDir.toFile().deleteOnExit();

            for (String fileName : PYTHON_RESOURCES) {
                Resource resource = new ClassPathResource(fileName);
                if (!resource.exists()) throw new FileNotFoundException("Recurso Python essencial não encontrado: " + fileName);
                
                Path destination = tempDir.resolve(fileName);
                try (InputStream inputStream = resource.getInputStream()) {
                    Files.copy(inputStream, destination);
                }
                if (fileName.equals(PYTHON_SCRIPT_NAME)) {
                    this.pythonScriptPath = destination;
                    this.pythonScriptPath.toFile().setExecutable(true, false);
                }
            }
            logger.info("QuestionProcessor inicializado com sucesso. Ambiente Python pronto em: {}", tempDir);
        } catch (IOException e) {
            logger.error("FALHA CRÍTICA AO CONFIGURAR AMBIENTE PYTHON.", e);
            throw e;
        }
    }
    
    public ProcessamentoDetalhadoResposta generateSparqlQuery(String question) {
        logger.info("Serviço QuestionProcessor: Iniciando GERAÇÃO de query para: '{}'", question);
        ProcessamentoDetalhadoResposta respostaDetalhada = new ProcessamentoDetalhadoResposta();
        
        try {
            Map<String, Object> resultadoPython = executePythonScript(question);
            
            if (resultadoPython.containsKey("erro")) {
                String erroPython = (String) resultadoPython.get("erro");
                logger.error("Script Python retornou um erro de PLN: {}", erroPython);
                respostaDetalhada.setErro("Falha na análise da pergunta: " + erroPython);
                return respostaDetalhada;
            }

            String templateId = (String) resultadoPython.get("template_nome");
            @SuppressWarnings("unchecked")
            Map<String, String> placeholders = (Map<String, String>) resultadoPython.get("mapeamentos");

            if (templateId == null || placeholders == null) {
                respostaDetalhada.setErro("Não foi possível determinar o tipo da pergunta ou extrair detalhes.");
                return respostaDetalhada;
            }

            logger.info("Análise PLN (Geração): Template ID='{}', Placeholders={}", templateId, placeholders);

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
    
    public String executeAndFormat(String sparqlQuery, String templateId) {
        logger.info("Serviço QuestionProcessor: Iniciando EXECUÇÃO de query.");
        try {
            List<Map<String, String>> resultados = ontology.executeQuery(sparqlQuery);
            return formatarResultados(resultados, templateId);
        } catch (Exception e) {
            logger.error("Erro ao EXECUTAR query: {}", e.getMessage(), e);
            return "Erro ao executar a consulta na base de conhecimento.";
        }
    }

    private String buildSparqlQuery(String templateContent, Map<String, String> placeholders) {
        String queryAtual = templateContent;
        if (placeholders == null) return queryAtual;

        if (placeholders.containsKey("#ENTIDADE_NOME#")) {
            String valor = placeholders.get("#ENTIDADE_NOME#").replace("\"", "\\\"");
            if (queryAtual.contains("#ENTIDADE_NOME#@pt")) {
                queryAtual = queryAtual.replace("#ENTIDADE_NOME#@pt", "\"" + valor + "\"@pt");
            } else {
                queryAtual = queryAtual.replace("#ENTIDADE_NOME#", "\"" + valor + "\"");
            }
        }
        if (placeholders.containsKey("#SETOR#")) {
            String valor = placeholders.get("#SETOR#").replace("\"", "\\\"");
            queryAtual = queryAtual.replace("#SETOR#@pt", "\"" + valor + "\"@pt");
        }
        if (placeholders.containsKey("#DATA#")) {
            String valor = placeholders.get("#DATA#");
            queryAtual = queryAtual.replace("#DATA#", "\"" + valor + "\"^^xsd:date");
        }
        if (placeholders.containsKey("#VALOR_DESEJADO#")) {
            String valor = placeholders.get("#VALOR_DESEJADO#");
            queryAtual = queryAtual.replace("#VALOR_DESEJADO#", valor);
        }
        return queryAtual;
    }

    private Map<String, Object> executePythonScript(String question) throws IOException, InterruptedException {
        ProcessBuilder pb = new ProcessBuilder("python3", this.pythonScriptPath.toString(), question);
        logger.info("Executando comando Python: {}", String.join(" ", pb.command()));
        Process process = pb.start();
        String stdoutResult = StreamUtils.copyToString(process.getInputStream(), StandardCharsets.UTF_8);
        String stderrResult = StreamUtils.copyToString(process.getErrorStream(), StandardCharsets.UTF_8);
        int exitCode = process.waitFor();
        if (!stderrResult.isEmpty()) logger.warn("Script Python emitiu mensagens no stderr: {}", stderrResult);
        if (exitCode != 0) throw new RuntimeException("Script Python falhou. Erro: " + stderrResult);
        if (stdoutResult.isEmpty()) throw new RuntimeException("Script Python não retornou nenhuma saída.");
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

    private String formatarResultados(List<Map<String, String>> resultados, String templateId) {
        if (resultados == null || resultados.isEmpty()) return "Não foram encontrados resultados para a sua pergunta.";
        StringJoiner joiner;
        if ("Template_4A".equals(templateId)) {
            joiner = new StringJoiner("\n");
            joiner.add("Ticker - Volume Negociado");
            joiner.add("-------------------------");
            for (Map<String, String> row : resultados) {
                String ticker = limparValor(row.getOrDefault("ticker", "?"));
                String volume = limparValor(row.getOrDefault("volume", "?"));
                joiner.add(String.format("%-7s - %s", ticker, volume));
            }
            return joiner.toString();
        }
        joiner = new StringJoiner(", ");
        if (!resultados.get(0).isEmpty()) {
            String varName = resultados.get(0).keySet().stream().findFirst().orElse("valor");
            for (Map<String, String> row : resultados) {
                String valor = row.getOrDefault(varName, "");
                if (!valor.isEmpty()) joiner.add(limparValor(valor));
            }
        }
        String resultadoFinal = joiner.toString();
        return resultadoFinal.isEmpty() ? "Não foram encontrados resultados para a sua pergunta." : resultadoFinal;
    }

    private String limparValor(String item) {
        if (item == null) return "";
        String limpo = item.replaceAll("\\^\\^<http://www.w3.org/2001/XMLSchema#.*?>", "");
        if (limpo.startsWith(BASE_ONTOLOGY_URI)) limpo = limpo.substring(BASE_ONTOLOGY_URI.length());
        return limpo.trim();
    }
}