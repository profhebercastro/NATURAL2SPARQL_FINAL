package com.example.Programa_heber.service;

import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.InputStream;
import java.util.Comparator;
import java.util.List;
import java.util.Properties;
import java.util.regex.Matcher;
import java.util.stream.Collectors;

@Component
public class OntologyProfile {

    private static final Logger logger = LoggerFactory.getLogger(OntologyProfile.class);
    private static final String PROFILE_PATH = "profiles/ontology_profile_b3.properties";

    private Properties profile = new Properties();

    @PostConstruct
    public void loadProfile() {
        try (InputStream input = new ClassPathResource(PROFILE_PATH).getInputStream()) {
            profile.load(input);
            logger.info("Perfil de ontologia '{}' carregado com sucesso com {} mapeamentos.", PROFILE_PATH, profile.size());
        } catch (IOException ex) {
            logger.error("FALHA CRÍTICA: Não foi possível carregar o perfil da ontologia: {}", PROFILE_PATH, ex);
            throw new RuntimeException("Falha ao carregar perfil de ontologia.", ex);
        }
    }

    public String get(String key) {
        String value = profile.getProperty(key);
        if (value == null) {
            logger.warn("Chave de perfil não encontrada: '{}'. Retornando a chave como valor.", key);
            return key;
        }
        return value;
    }

    /**
     * Substitui todos os placeholders genéricos (S, P, C, O, ANS) na string da query
     * pelos seus valores correspondentes do perfil.
     * @param query A string da query com placeholders genéricos.
     * @return A query com os placeholders substituídos.
     */
    public String replacePlaceholders(String query) {
        String result = query;
        
        // Ordena as chaves do maior para o menor para evitar substituições parciais (ex: P1 em P18)
        List<String> sortedKeys = profile.stringPropertyNames().stream()
                .sorted(Comparator.comparingInt(String::length).reversed())
                .collect(Collectors.toList());

        for (String key : sortedKeys) {
            if (key.startsWith("prefix.") || key.startsWith("resposta.")) {
                continue;
            }

            String placeholderRegex;
            String value = profile.getProperty(key);

            if (key.matches("^(S|O|ANS)\\d*")) {
                 placeholderRegex = "\\?" + key; // Busca por "?S1", "?O1", etc.
            } else {
                 placeholderRegex = key; // Busca por "C1", "P1", etc.
            }

            // Usa \\b para delimitar a "palavra" inteira
            result = result.replaceAll("\\b" + placeholderRegex + "\\b", Matcher.quoteReplacement(value));
        }
        return result;
    }
}