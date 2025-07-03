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
     * pelos seus valores correspondentes do perfil.
     * @param query A string da query com placeholders genéricos.
     * @return A query com os placeholders substituídos.
     */
    public String replacePlaceholders(String query) {
        String result = query;
        // Itera sobre todas as chaves do arquivo de propriedades (S1, P1, C1, etc.)
        for (String key : profile.stringPropertyNames()) {
            // Ignora chaves de configuração como "prefix.b3" e "resposta.*"
            if (key.startsWith("prefix.") || key.startsWith("resposta.")) {
                continue;
            }

            String placeholder = key;
            String value = profile.getProperty(key);

            // Se a chave for de uma variável (S, O, ANS), adiciona o '?' para a busca
            if (key.matches("^(S|O|ANS)\\d*")) {
                 placeholder = "?" + key;
            }

            result = result.replace(placeholder, value);
        }
        return result;
    }
}