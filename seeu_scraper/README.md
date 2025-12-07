# 🗂️ SEEU Scraper

O **SEEU Scraper** é um coletor de dados desenvolvido com **Scrapy**, projetado para extrair informações do portal de documentação do Sistema Eletrônico de Execução Unificado (SEEU). Ele organiza os dados coletados em um formato estruturado, facilitando o uso posterior para análise ou integração com outros sistemas.

---

## 🚀 Como Funciona

### **Fluxo de Execução**
1. **Inicialização do Spider**:
   - O spider principal (`seeu_docs`) é iniciado a partir da URL base: `https://docs.seeu.pje.jus.br/docs/category/guias-de-uso-para-o-seeu/`.
   - Ele segue os links internos para explorar as páginas relacionadas.

2. **Extração de Dados**:
   - Para cada página visitada, o spider coleta os seguintes campos:
     - **cluster_name**: Nome do cluster ao qual o documento pertence.
     - **title**: Título da página ou documento.
     - **content**: Conteúdo textual extraído dos parágrafos da página.
     - **url**: URL da página de origem.

3. **Armazenamento**:
   - Os dados extraídos são salvos no arquivo `data/seeu_docs.json` no formato JSON.
   - O arquivo é sobrescrito a cada execução para garantir que os dados estejam atualizados.

4. **Configuração Personalizada**:
   - O spider utiliza a configuração `FEED_EXPORT_FIELDS` para garantir a ordem dos campos no arquivo JSON exportado.

---

## 🏗️ Estrutura do Projeto

```
seeu_scraper/
├── scrapy.cfg                # Configuração do Scrapy
├── data/
│   └── seeu_docs.json        # Dados extraídos
├── seeu_scraper/
│   ├── spiders/
│   │   └── seeu_docs.py      # Spider principal
│   ├── settings.py           # Configurações do Scrapy
│   ├── pipelines.py          # Processamento de itens (opcional)
│   └── ...                   # Outros arquivos do projeto
```

---

## 📋 Como Executar

### **Pré-requisitos**
- Python 3.12+
- Dependências listadas no arquivo `requirements.txt`

### **Passos**
1. **Instale as dependências**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Execute o spider**:
   ```bash
   scrapy crawl seeu_docs
   ```

3. **Verifique os dados extraídos**:
   - Os dados estarão disponíveis no arquivo `data/seeu_docs.json`.

---

## 🔧 Configurações Importantes

- **`DOWNLOAD_DELAY`**: Define um atraso entre as requisições para evitar sobrecarregar o servidor.
- **`CONCURRENT_REQUESTS_PER_DOMAIN`**: Limita o número de requisições simultâneas para o mesmo domínio.
- **`ROBOTSTXT_OBEY`**: Configurado como `True` para respeitar as regras do arquivo `robots.txt` do site.

---

## 📂 Saída

Os dados extraídos são organizados no seguinte formato:

```json
[
  {
    "cluster_name": "Documentos de suporte SEEU",
    "title": "Guias de uso para o SEEU",
    "content": "Este espaço apresenta guias de uso simples e objetivos...",
    "url": "https://docs.seeu.pje.jus.br/docs/category/guias-de-uso-para-o-seeu/"
  },
  {
    "cluster_name": "Documentos de suporte SEEU",
    "title": "Portal de Documentação do SEEU",
    "content": "Em sintonia com as constantes melhorias do SEEU...",
    "url": "https://docs.seeu.pje.jus.br/docs/intro/"
  }
]
```

---

## 🛠️ Personalização

Para modificar o comportamento do scraper, edite os seguintes arquivos:
- **`seeu_scraper/spiders/seeu_docs.py`**: Para alterar a lógica de extração de dados.
- **`seeu_scraper/settings.py`**: Para ajustar configurações como delays, headers, e middlewares.

---

## 📞 Suporte

Para dúvidas ou problemas, entre em contato com o desenvolvedor ou consulte a documentação oficial do Scrapy:
- [Documentação do Scrapy](https://docs.scrapy.org/)