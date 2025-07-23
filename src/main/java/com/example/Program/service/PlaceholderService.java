package com.example.Program.service;

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
import java.util.regex.Pattern;
import java.util.stream.Collectors;

@Service
public class PlaceholderService {
    private static final Logger logger = LoggerFactory.getLogger(PlaceholderService.class);
    private static final String PROPERTIES_PATH = "placeholders.properties";
    private final Properties placeholders = new Properties();

    @PostConstruct
    public void loadProperties() {
        ClassPathResource resource = new ClassPathResource(PROPERTIES_PATH);
        if (!resource.exists()) { throw new RuntimeException("Arquivo de placeholders não encontrado: " + PROPERTIES_PATH); }
        try (InputStream input = resource.getInputStream()) {
            placeholders.load(input);
            logger.info("Arquivo de placeholders '{}' carregado.", PROPERTIES_PATH);
        } catch (IOException ex) {
            throw new RuntimeException("Falha ao carregar placeholders.", ex);
        }
    }

    public String getPlaceholderValue(String key) {
        return placeholders.getProperty(key);
    }
    
    public String replaceGenericPlaceholders(String query) {
        String result = query;
        // Ordena as chaves pelo comprimento, da maior para a menor, para evitar substituições parciais (ex: S1 antes de S10)
        List<String> sortedKeys = placeholders.stringPropertyNames().stream()
                .filter(k -> !k.startsWith("metrica.") && !k.startsWith("prefix."))
                .sorted(Comparator.comparingInt(String::length).reversed())
                .collect(Collectors.toList());

        for (String key : sortedKeys) {
            String value = placeholders.getProperty(key);
            String placeholderToReplace;
            String finalValue;

            // Placeholders de variáveis (S*, O*, ANS) são prefixados com '?'
            if (key.matches("^(S|O|ANS).*")) {
                placeholderToReplace = "?" + key;
                finalValue = "?" + value;
            } else { // Placeholders de predicados (P*) não têm '?'
                placeholderToReplace = key;
                finalValue = value;
            }
            
            // Usar replaceAll com Pattern.quote para tratar os placeholders como texto literal
            result = result.replaceAll(Pattern.quote(placeholderToReplace), Matcher.quoteReplacement(finalValue));
        }
        return result;
    }

    public String getPrefixes() {
        StringBuilder prefixHeader = new StringBuilder();
        placeholders.stringPropertyNames().stream()
            .filter(key -> key.startsWith("prefix."))
            .sorted()
            .forEach(key -> {
                String prefixName = key.substring("prefix.".length());
                String prefixUri = placeholders.getProperty(key);
                prefixHeader.append("PREFIX ").append(prefixName).append(": <").append(prefixUri).append(">\n");
            });
        return prefixHeader.toString();
    }
}