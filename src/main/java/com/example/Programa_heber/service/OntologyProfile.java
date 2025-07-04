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
import java.util.stream.Collectors;

@Component
public class OntologyProfile {

    private static final Logger logger = LoggerFactory.getLogger(OntologyProfile.class);
    private static final String PROFILE_PATH = "profiles/ontology_profile_b3.properties";

    private Properties profile = new Properties();
    private List<String> sortedKeys;

    @PostConstruct
    public void loadProfile() {
        try (InputStream input = new ClassPathResource(PROFILE_PATH).getInputStream()) {
            profile.load(input);
            this.sortedKeys = profile.stringPropertyNames().stream()
                    .sorted(Comparator.comparingInt(String::length).reversed())
                    .collect(Collectors.toList());
            logger.info("Perfil de ontologia '{}' carregado e chaves ordenadas com sucesso.", PROFILE_PATH);
        } catch (IOException ex) {
            logger.error("FALHA CRÍTICA: Não foi possível carregar o perfil da ontologia.", ex);
            throw new RuntimeException("Falha ao carregar perfil de ontologia.", ex);
        }
    }

    public String get(String key) {
        String value = profile.getProperty(key);
        if (value == null) {
            logger.warn("Chave de perfil não encontrada: '{}'.", key);
            return key;
        }
        return value;
    }

    public String replacePlaceholders(String query) {
        String result = query;
        for (String key : this.sortedKeys) {
            if (key.startsWith("prefix.") || key.startsWith("resposta.")) {
                continue;
            }
            String placeholder;
            String value = profile.getProperty(key);
            if (key.matches("^(S|O|ANS)\\d*")) {
                 placeholder = "?" + key;
            } else {
                 placeholder = key;
            }
            result = result.replace(placeholder, value);
        }
        return result;
    }
}