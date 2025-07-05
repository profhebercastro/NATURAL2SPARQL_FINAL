package com.example.Programa_heber.service;

import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.io.InputStream;
import java.util.Comparator;
import java.util.List;
import java.util.Properties;
import java.util.regex.Matcher;
import java.util.stream.Collectors;

@Service
public class PlaceholderService {

    private static final Logger logger = LoggerFactory.getLogger(PlaceholderService.class);
    private static final String PROPERTIES_PATH = "placeholders.properties";

    private Properties placeholders = new Properties();

    @PostConstruct
    public void loadProperties() {
        try (InputStream input = new ClassPathResource(PROPERTIES_PATH).getInputStream()) {
            placeholders.load(input);
            logger.info("Arquivo de placeholders '{}' carregado com {} mapeamentos.", PROPERTIES_PATH, placeholders.size());
        } catch (IOException ex) {
            logger.error("FALHA CRÍTICA: Não foi possível carregar o arquivo de placeholders: {}", PROPERTIES_PATH, ex);
            throw new RuntimeException("Falha ao carregar placeholders.", ex);
        }
    }

    /**
     * Substitui todos os placeholders genéricos (S1, P1, C5_setor, etc.) na string da query
     * pelos seus valores correspondentes do arquivo .properties.
     * @param query A string da query com placeholders genéricos.
     * @return A query final com os placeholders RDF substituídos.
     */
    public String replaceGenericPlaceholders(String query) {
        String result = query;

        // Ordena as chaves do maior para o menor comprimento para evitar substituições parciais.
        // Ex: Garante que "S2_label" seja processado antes de "S2".
        List<String> sortedKeys = placeholders.stringPropertyNames().stream()
                .sorted(Comparator.comparingInt(String::length).reversed())
                .collect(Collectors.toList());

        for (String key : sortedKeys) {
            // Ignora prefixos, que são tratados separadamente se necessário
            if (key.startsWith("prefix.")) {
                continue;
            }

            String value = placeholders.getProperty(key);
            String placeholderRegex;

            // Variáveis SPARQL (começam com S, C, ANS) são substituídas com o '?'
            if (key.matches("^(S|C|ANS).*")) {
                 placeholderRegex = "\\?" + key; // Busca por "?S1", "?C5_setor", etc.
            } else {
                 // Propriedades e outros são substituídos diretamente
                 placeholderRegex = key; // Busca por "P1", "P18", etc.
            }
            
            // Usa \\b para delimitar a "palavra" inteira e evitar que "P1" substitua parte de "P10"
            // Matcher.quoteReplacement escapa caracteres especiais no valor de substituição ($)
            result = result.replaceAll("\\b" + placeholderRegex + "\\b", Matcher.quoteReplacement(value));
        }
        return addPrefixes() + result;
    }
    
    /**
     * Monta o cabeçalho de prefixos para a consulta SPARQL.
     * @return Uma string contendo todos os prefixos definidos no arquivo .properties.
     */
    private String addPrefixes() {
        StringBuilder prefixHeader = new StringBuilder();
        placeholders.stringPropertyNames().stream()
            .filter(key -> key.startsWith("prefix."))
            .forEach(key -> {
                String prefixName = key.substring("prefix.".length());
                String prefixUri = placeholders.getProperty(key);
                prefixHeader.append("PREFIX ").append(prefixName).append(": <").append(prefixUri).append(">\n");
            });
        prefixHeader.append("\n");
        return prefixHeader.toString();
    }
}