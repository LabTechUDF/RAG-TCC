# stj_scraper

Coletor do **STJ – Íntegras de decisões terminativas e acórdãos do Diário da Justiça** (CKAN), com **normalização para RAG** e **salvamento padrão em um único NDJSON** (uma linha por decisão monocrática). Mantém a padronização estrutural do `stf_scraper`, sem modificá-lo.

## Estrutura

```
stj_scraper/
├── configs/                    # Configurações
├── data/                      # Saída padrão: stj_decisoes_monocraticas.jsonl
├── logs/                      # Único arquivo de log: app.log
├── temp_queue/               # Cache temporário de downloads
├── scrapy.cfg               # Configuração do Scrapy
├── manage.py               # CLI principal
└── stj_scraper/
    ├── __init__.py
    ├── items.py            # Definição dos items
    ├── pipelines.py        # Pipelines de processamento
    ├── settings.py         # Configurações do Scrapy
    ├── middlewares.py      # Middlewares
    ├── stj_queue_manager.py # Gerenciador de fila principal
    ├── utils/
    │   ├── io_utils.py     # Utilitários de I/O
    │   ├── zip_utils.py    # Processamento de ZIPs
    │   ├── ckan_utils.py   # Interação com portal CKAN
    │   ├── text_extraction.py # Extração de texto e metadados
    │   └── clustering.py   # Clusterização por artigos
    └── spiders/
        └── stj_dataset_spider.py # Spider principal
```

> **Logs:** um único arquivo em `stj_scraper/logs/app.log`.

## Requisitos

- Python 3.11+
- Poetry

## Instalação

```bash
cd stj_scraper
poetry install
```

## Execução

O comando principal `stj crawl` baixa os .zip, filtra decisão monocrática, encontra .txt por seqDocumento e grava um único NDJSON.

```bash
poetry run python manage.py stj crawl
```

### Opções

- `--dataset-url URL` (default: dataset oficial)
- `--limit N` - Limita número de recursos a processar
- `--article-filter "179,330,171"` - Filtra por artigos específicos
- `--cluster-order {article|random}` (default: article)
- `--out PATH` (default: data/)
- `--output-jsonl PATH` (default: data/stj_decisoes_monocraticas.jsonl)
- `--resume` - Retoma processamento anterior
- `--write-txt false` (padrão: não salva .txt)

### Exemplos

```bash
# Processar todos os recursos
poetry run python manage.py stj crawl

# Limitar a 3 recursos para teste
poetry run python manage.py stj crawl --limit 3

# Filtrar apenas artigos específicos
poetry run python manage.py stj crawl --article-filter "179,330,171"

# Retomar processamento interrompido
poetry run python manage.py stj crawl --resume

# Salvar arquivos TXT em disco (além do JSONL)
poetry run python manage.py stj crawl --write-txt true

# Ordenação aleatória dos clusters
poetry run python manage.py stj crawl --cluster-order random
```

### Comandos adicionais

```bash
# Ver status da fila de processamento
poetry run python manage.py status

# Limpar arquivos de estado da fila
poetry run python manage.py cleanup
```

## Saída

### NDJSON único: `data/stj_decisoes_monocraticas.jsonl`

Cada linha contém campos normalizados (cluster, título, número do processo, conteúdo, datas…) e bloco trace (nome do .zip, resource_id, URL de download, folder/caminho interno do .txt, URLs de dataset/recurso, cache local, caminho lógico de cluster).

### Exemplo (1 linha):

```json
{
  "cluster_name": "art_179",
  "cluster_description": "Código Penal art. 179", 
  "article_reference": "CP art. 179",
  "source": "STJ - 202202.zip",
  "title": "REsp 1890871",
  "case_number": "1890871",
  "content": "[texto integral do arquivo .txt]",
  "url": null,
  "tribunal": "STJ",
  "legal_area": null,
  "relator": "MIN. JOÃO OTÁVIO DE NORONHA",
  "publication_date": "2022-02-10",
  "decision_date": "2022-02-08",
  "partes": "Recorrente: FULANO DE TAL; Recorrido: MINISTÉRIO PÚBLICO FEDERAL",
  "decision": "Negar provimento ao recurso especial...",
  "legislacao": "CP art. 179; Lei nº 8.137/90",
  "content_quality": 95,
  "trace": {
    "zip_filename": "202202.zip",
    "zip_resource_id": "2b640cb2-cd3f-4737-999b-efece1196fbe",
    "zip_download_url": "https://dadosabertos.web.stj.jus.br/dataset/.../download/202202.zip",
    "zip_internal_path": "decisoes/2022/02/144948780.txt",
    "dataset_url": "https://dadosabertos.web.stj.jus.br/dataset/integras-de-decisoes-terminativas-e-acordaos-do-diario-da-justica",
    "resource_page_url": "https://dadosabertos.web.stj.jus.br/dataset/.../resource/2b640cb2-...",
    "local_cache_dir": "stj_scraper/temp_queue/2b640cb2-.../",
    "cluster_path": "data/clustered/ART_179/202202/"
  }
}
```

## Funcionamento

1. **Descoberta de Recursos**: Acessa o portal CKAN e extrai lista de arquivos .zip disponíveis
2. **Download**: Baixa cada .zip identificado
3. **Extração**: Processa JSONs internos para encontrar decisões
4. **Filtragem**: Identifica decisões monocráticas baseado em `tipoDocumento` e metadados
5. **Matching**: Para cada decisão elegível, localiza arquivo .txt correspondente pelo `seqDocumento`
6. **Processamento**: Extrai conteúdo do .txt, analisa artigos legais, metadados e normaliza
7. **Salvamento**: Grava linha no JSONL único com campos normalizados e trace completo

## Rastreabilidade

Cada decisão mantém proveniência completa:
- **ZIP origem**: nome, resource_id, URL de download
- **Localização interna**: caminho do .txt dentro do ZIP
- **URLs**: dataset, página do recurso
- **Cache local**: diretório temporário usado
- **Cluster lógico**: onde seria salvo em estrutura de pastas

## Qualidade

- **Filtros robustos**: Apenas decisões monocráticas válidas
- **Matching inteligente**: Tolerância a zero-padding nos nomes de arquivos
- **Score de qualidade**: Baseado em completude de metadados, tamanho do conteúdo
- **Deduplicação**: Por `seqDocumento` para evitar duplicatas
- **Normalização**: Datas epoch → YYYY-MM-DD, texto limpo

## Troubleshooting

**"Não encontrou .txt para seqDocumento"**: 
- Inspecione `zip_internal_path` no trace
- Use `--limit 1` e habilite DEBUG no log para análise detalhada

**HTTP 403/timeout**: 
- Ajuste User-Agent nas configurações
- Verifique conexão com o portal STJ

**Processamento lento**:
- Use `--limit N` para testes
- Monitore logs em `logs/app.log`
- Verifique espaço em disco na pasta `temp_queue/`

**Retomar processamento**:
- Use `--resume` para continuar de onde parou
- Estado salvo em `stj_scraper/queue_state.json`