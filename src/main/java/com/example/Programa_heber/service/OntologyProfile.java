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

    /**
     * Obtém um valor do perfil. Se não encontrar, retorna a própria chave para depuração.
     * @param key A chave a ser buscada no perfil.
     * @return O valor correspondente ou a própria chave se não for encontrada.
     */
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
     * pelos seus valores correspondentes do perfil. A substituição é feita de forma robusta,
     * ordenando as chaves para evitar matches parciais (ex: P1 em P18).
     * @param query A string da query com placeholders genéricos.
     * @return A query com os placeholders substituídos.
     */
    public String replacePlaceholders(String query) {
        String result = query;
        
        // Ordena as chaves do maior para o menor comprimento para evitar substituições parciais.
        // Ex: Garante que "P18" seja processado antes de "P1".
        List<String> sortedKeys = profile.stringPropertyNames().stream()
                .sorted(Comparator.comparingInt(String::length).reversed())
                .collect(Collectors.toList());

        for (String key : sortedKeys) {
            // Ignora chaves de configuração que não são placeholders de query
            if (key.startsWith("prefix.") || key.startsWith("resposta.")) {
                continue;
            }

            String placeholderRegex;
            String value = profile.getProperty(key);

            // Constrói a expressão regular correta para cada tipo de placeholder
            if (key.matches("^(S|O|ANS)\\d*")) {
                 // Para variáveis como S1, O1, ANS, o placeholder no template é "?S1"
                 placeholderRegex = "\\?" + key; // Busca por "?S1", "?O1", etc.
            } else {
                 // Para classes e predicados como C1, P1, o placeholder é "C1"
                 placeholderRegex = key;
            }

            // Usa \\b para delimitar a "palavra" inteira e evitar matches parciais
            // Matcher.quoteReplacement escapa caracteres especiais no valor de substituição
            result = result.replaceAll("\\b" + placeholderRegex + "\\b", Matcher.quoteReplacement(value));
        }
        return result;
    }
}