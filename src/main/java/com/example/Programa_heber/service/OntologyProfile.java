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
    private List<String> sortedKeys; // Cache para as chaves ordenadas

    @PostConstruct
    public void loadProfile() {
        try (InputStream input = new ClassPathResource(PROFILE_PATH).getInputStream()) {
            profile.load(input);
            // Ordena as chaves do maior para o menor comprimento e guarda em cache
            this.sortedKeys = profile.stringPropertyNames().stream()
                    .sorted(Comparator.comparingInt(String::length).reversed())
                    .collect(Collectors.toList());
            logger.info("Perfil de ontologia '{}' carregado e chaves ordenadas com sucesso.", PROFILE_PATH);
        } catch (IOException ex) {
            logger.error("FALHA CRÍTICA: Não foi possível carregar o perfil da ontologia.", ex);
            throw new RuntimeException("Falha ao carregar perfil de ontologia.", ex);
        }
    }

    /**
     * Obtém um valor do perfil. Se não encontrar, retorna a própria chave para depuração.
     * @param key A chave a ser buscada no perfil.
     * @return O valor correspondente ou a própria chave se não for encontrada.
     */
    public String get(String key) {
        String value = profile.getProperty(key);
        if (value == null) {
            logger.warn("Chave de perfil não encontrada: '{}'.", key);
            return key;
        }
        return value;
    }

    /**
     * Substitui todos os placeholders genéricos (S, P, C, O, ANS) na string da query
     * pelos seus valores correspondentes do perfil. A substituição é feita de forma robusta,
     * ordenando as chaves para evitar matches parciais (ex: P1 em P18).
     * @param query A string da query com placeholders genéricos.
     * @return A query com os placeholders substituídos.
     */
    public String replacePlaceholders(String query) {
        String result = query;
        
        for (String key : this.sortedKeys) {
            // Ignora chaves de configuração que não são placeholders de query
            if (key.startsWith("prefix.") || key.startsWith("resposta.")) {
                continue;
            }

            String placeholder;
            String value = profile.getProperty(key);

            // Constrói o placeholder a ser buscado no template
            if (key.matches("^(S|O|ANS)\\d*")) {
                 placeholder = "?" + key; // Variáveis começam com '?'
            } else {
                 placeholder = key; // Classes e Predicados não
            }

            // Usa String.replace(), que é seguro porque as chaves estão ordenadas por tamanho.
            // Isso evita que "P1" seja substituído dentro de "P18".
            result = result.replace(placeholder, value);
        }
        return result;
    }
}