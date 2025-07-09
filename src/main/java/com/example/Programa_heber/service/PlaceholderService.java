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
import java.util.regex.Pattern;
import java.util.stream.Collectors;

@Service
public class PlaceholderService {

    private static final Logger logger = LoggerFactory.getLogger(PlaceholderService.class);
    private static final String PROPERTIES_PATH = "placeholders.properties";

    private Properties placeholders = new Properties();

    /**
     * Carrega o arquivo de propriedades na inicialização do serviço.
     * Este método é anotado com @PostConstruct para garantir que seja executado
     * após a criação do bean pelo Spring.
     */
    @PostConstruct
    public void loadProperties() {
        logger.info("Tentando carregar o arquivo de placeholders de: {}", PROPERTIES_PATH);
        ClassPathResource resource = new ClassPathResource(PROPERTIES_PATH);

        if (!resource.exists()) {
            logger.error("FALHA CRÍTICA: O arquivo '{}' não foi encontrado no classpath (src/main/resources). Verifique se o arquivo existe e se o nome está correto.", PROPERTIES_PATH);
            throw new RuntimeException("Falha ao carregar placeholders: arquivo não encontrado.");
        }

        try (InputStream input = resource.getInputStream()) {
            placeholders.load(input);
            logger.info("Arquivo de placeholders '{}' carregado com {} mapeamentos.", PROPERTIES_PATH, placeholders.size());
        } catch (IOException ex) {
            logger.error("FALHA CRÍTICA: Ocorreu um erro de I/O ao ler o arquivo de placeholders: {}", PROPERTIES_PATH, ex);
            throw new RuntimeException("Falha ao carregar placeholders.", ex);
        }
    }

    /**
     * Retorna o valor de uma chave específica do arquivo de propriedades.
     * É usado pelo SPARQLProcessor para obter o predicado RDF de uma métrica.
     * @param key A chave a ser buscada (ex: "metrica.preco_fechamento").
     * @return O valor correspondente (ex: "b3:precoFechamento") ou null se não for encontrado.
     */
    public String getPlaceholderValue(String key) {
        return placeholders.getProperty(key);
    }
    
    /**
     * Substitui todos os placeholders genéricos (S1, P1, SO1 etc.) na string da query
     * pelos seus valores correspondentes do arquivo .properties.
     * @param query A string da query com placeholders genéricos.
     * @return A query final com os placeholders RDF substituídos e os prefixos adicionados.
     */
    public String replaceGenericPlaceholders(String query) {
        String result = query;

        // Obtém e ordena as chaves do maior para o menor comprimento.
        // Isso é crucial para evitar substituições parciais (ex: substituir "S1" antes de "SO1").
        List<String> sortedKeys = placeholders.stringPropertyNames().stream()
                .filter(k -> !k.startsWith("metrica.") && !k.startsWith("prefix.")) // Filtra chaves de configuração
                .sorted(Comparator.comparingInt(String::length).reversed())
                .collect(Collectors.toList());

        for (String key : sortedKeys) {
            String value = placeholders.getProperty(key);
            
            // Lógica de substituição robusta:
            // - \\b: Garante que estamos substituindo a "palavra" inteira (ex: P1 e não o P1 em P18).
            // - Pattern.quote(key): Trata a chave (o placeholder, como "S1") como um texto literal,
            //   evitando que caracteres especiais sejam interpretados como comandos de regex.
            // - Matcher.quoteReplacement(value): Trata o valor (a substituição, como "?empresa") como um texto literal,
            //   evitando que caracteres como '?' ou '$' causem erros na substituição.
            result = result.replaceAll("\\b" + Pattern.quote(key) + "\\b", Matcher.quoteReplacement(value));
        }
        
        // Adiciona o cabeçalho de prefixos no início da consulta final.
        return addPrefixes() + result;
    }

    /**
     * Monta o cabeçalho de prefixos para a consulta SPARQL a partir das chaves "prefix.*"
     * no arquivo .properties.
     * @return Uma string contendo todas as declarações de prefixos.
     */
    private String addPrefixes() {
        StringBuilder prefixHeader = new StringBuilder();
        placeholders.stringPropertyNames().stream()
            .filter(key -> key.startsWith("prefix."))
            .sorted() // Ordena para um cabeçalho consistente
            .forEach(key -> {
                String prefixName = key.substring("prefix.".length());
                String prefixUri = placeholders.getProperty(key);
                prefixHeader.append("PREFIX ").append(prefixName).append(": <").append(prefixUri).append(">\n");
            });
        prefixHeader.append("\n"); // Adiciona uma linha em branco após os prefixos
        return prefixHeader.toString();
    }
}