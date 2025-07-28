import rdflib

# Nome do arquivo de ontologia a ser verificado
ontology_file = 'ontology_inferred_final.ttl'

# Cria um novo grafo RDF
g = rdflib.Graph()

print(f"Carregando o arquivo '{ontology_file}'...")

try:
    # Tenta carregar (parse) o arquivo no grafo
    g.parse(ontology_file, format='turtle')
    
    # A função len(g) retorna o número total de triplas no grafo
    num_triples = len(g)
    
    print("-" * 30)
    print(f"SUCESSO! O arquivo foi carregado.")
    print(f"Número exato de triplas encontradas: {num_triples}")
    print("-" * 30)

except Exception as e:
    print(f"\nERRO: Falha ao carregar ou analisar o arquivo.")
    print(f"Detalhe do erro: {e}")