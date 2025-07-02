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
public class QuestionProcessor {

    private static final Logger logger = LoggerFactory.getLogger(QuestionProcessor.class);
    private static final String PYTHON_SCRIPT_NAME = "pln_processor.py";
    private static final String BASE_ONTOLOGY_URI = "https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#";
    
    // Lista de recursos que o script Python precisa para funcionar.
    private static final String[] PYTHON_RESOURCES = {
        PYTHON_SCRIPT_NAME, "perguntas_de_interesse.txt", "sinonimos_map.txt",
        "empresa_nome_map.json", "setor_map.json"
    };

    @Autowired
    private Ontology ontology;

    private Path pythonScriptPath;
    private final ObjectMapper objectMapper = new ObjectMapper();
    // Pattern compilado para checar se uma string tem formato de Ticker.
    private static final Pattern TICKER_PATTERN = Pattern.compile("^[A-Z]{4}\\d{1,2}$");

    @PostConstruct
    public void initialize() throws IOException {
        logger.info("Iniciando QuestionProcessor (@PostConstruct): Configurando ambiente Python...");
        try {
            // Cria um diretório temporário para os scripts Python, que será apagado ao fechar a JVM.
            Path tempDir = Files.createTempDirectory("pyscripts_temp_");
            tempDir.toFile().deleteOnExit();

            for (String fileName : PYTHON_RESOURCES) {
                Resource resource = new ClassPathResource(fileName);
                if (!resource.exists()) {
                    throw new FileNotFoundException("Recurso Python essencial não encontrado: " + fileName);
                }
                
                Path destination = tempDir.resolve(fileName);
                try (InputStream inputStream = resource.getInputStream()) {
                    Files.copy(inputStream, destination);
                }
                if (fileName.equals(PYTHON_SCRIPT_NAME)) {
                    this.pythonScriptPath = destination;
                    // Torna o script executável no ambiente (importante para Linux/macOS)
                    this.pythonScriptPath.toFile().setExecutable(true, false);
                }
            }
            logger.info("QuestionProcessor inicializado com sucesso. Ambiente Python pronto em: {}", tempDir);
        } catch (IOException e) {
            logger.error("FALHA CRÍTICA AO CONFIGURAR AMBIENTE PYTHON.", e);
            throw e; // Lança a exceção para impedir o boot da aplicação em caso de falha.
        }
    }
    
    public ProcessamentoDetalhadoResposta generateSparqlQuery(String question) {
        logger.info("Serviço QuestionProcessor: Iniciando GERAÇÃO de query para: '{}'", question);
        ProcessamentoDetalhadoResposta respostaDetalhada = new ProcessamentoDetalhadoResposta();
        
        try {
            Map<String, Object> resultadoPython = executePythonScript(question);
            
            // Se o script Python retornou um erro de negócio, repassa para o usuário.
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
        logger.info("Serviço QuestionProcessor: Iniciando EXECUÇÃO de query com template {}.", templateId);
        try {
            List<Map<String, String>> resultados = ontology.executeQuery(sparqlQuery);
            return formatarResultados(resultados, templateId);
        } catch (Exception e) {
            logger.error("Erro ao EXECUTAR query: {}", e.getMessage(), e);
            return "Erro ao executar a consulta na base de conhecimento.";
        }
    }

    /**
     * CORRIGIDO: Método final para construir a query SPARQL de forma robusta.
     * Formata os placeholders de acordo com o tipo (data, label, ticker, etc).
     */
    private String buildSparqlQuery(String templateContent, Map<String, String> placeholders) {
        String query = templateContent;
        if (placeholders == null) return query;

        // Substitui placeholders simples primeiro
        if (placeholders.containsKey("#DATA#")) {
            query = query.replace("#DATA#", "\"" + placeholders.get("#DATA#") + "\"^^xsd:date");
        }
        if (placeholders.containsKey("#VALOR_DESEJADO#")) {
            query = query.replace("#VALOR_DESEJADO#", "b3:" + placeholders.get("#VALOR_DESEJADO#"));
        }
        if (placeholders.containsKey("#SETOR#")) {
            // Adiciona a tag de idioma @pt para os setores
            query = query.replace("#SETOR#", "\"" + placeholders.get("#SETOR#").replace("\"", "\\\"") + "\"@pt");
        }

        // Lida com o placeholder de entidade de forma especial
        if (placeholders.containsKey("#ENTIDADE_NOME#")) {
            String entidade = placeholders.get("#ENTIDADE_NOME#");
            // Escapa aspas para segurança
            String entidadeEscapada = entidade.replace("\"", "\\\"");
            
            String valorFormatado;
            // Verifica se a entidade é um ticker ou um nome de empresa
            if (TICKER_PATTERN.matcher(entidade).matches()) {
                // Se for um ticker, o valor é uma string literal
                valorFormatado = "\"" + entidadeEscapada + "\"";
            } else {
                // Se for um nome de empresa, adiciona a tag de idioma @pt
                valorFormatado = "\"" + entidadeEscapada + "\"@pt";
            }
            query = query.replace("#ENTIDADE_NOME#", valorFormatado);
        }
        
        // Versão antiga de substituição de placeholder de label, mantida para retrocompatibilidade se necessário
        if (placeholders.containsKey("#ENTIDADE_LABEL#")) {
            query = query.replace("#ENTIDADE_LABEL#", "\"" + placeholders.get("#ENTIDADE_LABEL#").replace("\"", "\\\"") + "\"@pt");
        }

        logger.info("Query SPARQL Final Gerada:\n{}", query);
        return query;
    }


    private Map<String, Object> executePythonScript(String question) throws IOException, InterruptedException {
        // Usa python3, que é mais padrão em ambientes Linux modernos.
        ProcessBuilder pb = new ProcessBuilder("python3", this.pythonScriptPath.toString(), question);
        logger.info("Executando comando Python: {}", String.join(" ", pb.command()));
        
        Process process = pb.start();
        String stdoutResult = StreamUtils.copyToString(process.getInputStream(), StandardCharsets.UTF_8);
        String stderrResult = StreamUtils.copyToString(process.getErrorStream(), StandardCharsets.UTF_8);
        
        int exitCode = process.waitFor();
        
        if (!stderrResult.isEmpty()) {
            // Loga o stderr como WARN, pois o script Python pode usar stderr para seus próprios logs de INFO.
            logger.warn("Script Python emitiu mensagens no stderr: {}", stderrResult);
        }
        
        if (exitCode != 0) {
            throw new RuntimeException("Script Python falhou com código de saída " + exitCode + ". Erro: " + stderrResult);
        }
        if (stdoutResult.isEmpty()) {
            throw new RuntimeException("Script Python não retornou nenhuma saída (stdout). Erro: " + stderrResult);
        }
        
        return objectMapper.readValue(stdoutResult, new TypeReference<>() {});
    }

    private String readTemplateContent(String templateId) throws IOException {
        String templateFileName = templateId + ".txt";
        String templateResourcePath = "Templates/" + templateFileName;
        Resource resource = new ClassPathResource(templateResourcePath);
        if (!resource.exists()) {
            throw new FileNotFoundException("Template SPARQL não encontrado: " + templateResourcePath);
        }
        try (InputStream inputStream = resource.getInputStream()) {
            return new String(inputStream.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    private String formatarResultados(List<Map<String, String>> resultados, String templateId) {
        if (resultados == null || resultados.isEmpty()) {
            return "Não foram encontrados resultados para a sua pergunta.";
        }
        
        // Tratamento especial para Template_4A que retorna Ticker e Volume
        if ("Template_4A".equals(templateId)) {
            StringJoiner joiner = new StringJoiner("\n");
            joiner.add(String.format("%-10s | %s", "Ticker", "Volume Negociado"));
            joiner.add("------------------------------------");
            for (Map<String, String> row : resultados) {
                String ticker = limparValor(row.getOrDefault("ticker", "N/A"));
                try {
                    // Formata o volume como um número com separador de milhar e duas casas decimais.
                    double volumeValue = Double.parseDouble(row.getOrDefault("volume", "0"));
                    String volumeFormatado = String.format("%,.2f", volumeValue);
                    joiner.add(String.format("%-10s | %s", ticker, volumeFormatado));
                } catch (NumberFormatException e) {
                     joiner.add(String.format("%-10s | %s", ticker, row.getOrDefault("volume", "N/A")));
                }
            }
            return joiner.toString();
        }

        // Formatação padrão para os outros templates que retornam uma lista de valores.
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

    private String limparValor(String item) {
        if (item == null) return "";
        // Remove a URI de datatype do final do literal (ex: ^^<http://...#double>).
        String limpo = item.replaceAll("\\^\\^<http://www.w3.org/2001/XMLSchema#.*?>", "");
        // Se for uma URI completa da nossa ontologia, extrai apenas o fragmento (o nome).
        if (limpo.startsWith(BASE_ONTOLOGY_URI)) {
            limpo = limpo.substring(BASE_ONTOLOGY_URI.length());
        }
        return limpo.trim();
    }
}