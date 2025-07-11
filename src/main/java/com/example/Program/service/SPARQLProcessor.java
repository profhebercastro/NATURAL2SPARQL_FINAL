package com.example.Programa_heber.service;

import org.springframework.stereotype.Service;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.stream.Collectors;

@Service
public class SPARQLProcessor {

    private final PlaceholderService placeholderService;

    // Injeção de dependência via construtor (prática recomendada pelo Spring)
    public SPARQLProcessor(PlaceholderService placeholderService) {
        this.placeholderService = placeholderService;
    }

    /**
     * Constrói uma consulta SPARQL final a partir de um template e um mapa de entidades.
     * @param templateId O ID do template (ex: "Template_5B").
     * @param entidades Um mapa com as entidades extraídas pelo NLP.
     * @return Uma string contendo a consulta SPARQL pronta para ser executada.
     */
    public String buildQuery(String templateId, Map<String, String> entidades) {
        // 1. Carrega o conteúdo do arquivo de template correspondente.
        String query = loadTemplateContent(templateId);

        // 2. Substitui placeholders de entidade (nome, data, etc.).
        if (entidades.containsKey("nome_empresa")) {
            query = query.replace("#ENTIDADE_NOME#", entidades.get("nome_empresa"));
        }
        if (entidades.containsKey("data")) {
            query = query.replace("#DATA#", entidades.get("data"));
        }

        // 3. Substitui a métrica (ex: #VALOR_DESEJADO#).
        if (entidades.containsKey("metrica")) {
            String metricaKey = entidades.get("metrica");           // Ex: "metrica.preco_minimo"
            String metricaRdf = placeholderService.getProperty(metricaKey); // Ex: "b3:precoMinimo"
            if (metricaRdf != null) {
                query = query.replace("#VALOR_DESEJADO#", metricaRdf);
            }
        }
        
        // 4. LÓGICA NOVA: Substitui o padrão REGEX, se existir.
        if (entidades.containsKey("regex_pattern")) {
            query = query.replace("#REGEX_PATTERN#", entidades.get("regex_pattern"));
        } else {
            // Medida de segurança: Se o placeholder REGEX existir no template, mas não
            // foi fornecido um padrão, remove a linha inteira do filtro para evitar erros.
            // A regex `.*#REGEX_PATTERN#.*\\R?` remove a linha inteira, incluindo a quebra de linha.
            query = query.replaceAll(".*#REGEX_PATTERN#.*\\R?", "");
        }

        // 5. Substitui todos os placeholders genéricos (P1, S1, etc.) usando o serviço.
        query = placeholderService.replaceAllPlaceholders(query);

        return query;
    }

    /**
     * Carrega o conteúdo de um arquivo de template do classpath.
     * @param templateId O ID do template, que corresponde ao nome do arquivo (sem extensão).
     * @return O conteúdo do arquivo como uma String.
     */
    private String loadTemplateContent(String templateId) {
        String fileName = "/Templates/" + templateId + ".txt";
        try (InputStream is = SPARQLProcessor.class.getResourceAsStream(fileName)) {
            if (is == null) {
                throw new IllegalArgumentException("Arquivo de template não encontrado: " + fileName);
            }
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
                return reader.lines().collect(Collectors.joining(System.lineSeparator()));
            }
        } catch (Exception e) {
            // Lança uma exceção mais informativa em caso de erro.
            throw new RuntimeException("Falha ao carregar o template: " + fileName, e);
        }
    }
}