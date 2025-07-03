package com.example.Programa_heber.service;

import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.InputStream;
import java.util.Properties;

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
}