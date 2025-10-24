

### 🎯 Instruções otimizadas para o agente `trf4_scraper`

**Contexto geral:**
O script `trf4_scraper` deve seguir a mesma estrutura e lógica do `stf_scraper`, mas adaptada ao site do Tribunal Regional Federal da 4ª Região (TRF4).
O site do TRF4 utiliza **paginação estática com AJAX**, portanto todas as ações ocorrem na **mesma URL**, sendo necessário aguardar carregamentos dinâmicos entre as etapas.
Use `time.sleep()` ou função equivalente para aguardar o carregamento de elementos e garantir que os componentes estejam visíveis antes de interagir.

Resumo: Crie um novo scraper com uma pasta nova para esse projeto e convenções padronizadas, parecido com o stf_scraper. onde as instruções de como o comportamento da pagina se mantem e é alterado foram definidas abaixo.

---

### 🚀 Passos da raspagem (ordem obrigatória)

    name = 'trf4_jurisprudencia'
    allowed_domains = ['jurisprudencia.trf4.jus.br']
    start_urls = ['https://jurisprudencia.trf4.jus.br/pesquisa/pesquisa.php']


#### 1. Acessar a URL inicial

* Entrar na URL definida em `start_urls`.

#### 2. Abrir configurações avançadas

* Localizar e clicar no elemento com o seguinte **outerHTML**:

```html
<a href="#/" id="btnPesquisaAvancada" class="pop-underline px-4 btnPesquisaAvancadaInicio" data-toggle="collapse" data-target="#divPesquisaAvancada" title="Visualizar outros filtros que podem ser usados para melhorar o resultado da pesquisa" style="font-size: 1.2rem;font-weight: 300;" aria-expanded="true">
  Pesquisa avançada
  <i id="iconPesquisaAvancadaMinimizado" class="material-icons justify-content-between iconeComTexto">arrow_drop_up</i>
</a>
```

#### 3. Selecionar o tipo de documento “Decisão Monocrática”

* Dentro da seção “Tipo de Documento”, clicar no elemento com o seguinte **outerHTML**:

```html
<div class="filter-option-inner-inner">Decisão monocrática</div>
```

#### 4. Inserir o texto de pesquisa

* Localizar o campo de input com o **outerHTML**:

```html
<input type="search" id="txtPesquisa" name="txtPesquisa" class="form-control campoPesquisa" value="" placeholder="Informe o texto para pesquisa" aria-label="Texto para pesquisa" aria-describedby="btnConsultar" style="padding-right: 2rem">
```

* Inserir no campo o valor da **query de pesquisa**.
* Pressionar “Enter” **ou** clicar no botão de pesquisa descrito abaixo.

#### 5. Executar a pesquisa

* Clicar no botão de consulta identificado por:

```html
<button class="btn btn-sm btn-primary d-flex align-items-center ml-2 px-2 btnConsultar" type="submit" title="Consultar" id="btnConsultar_form_inicial" style="height: 37px">
  <i class="material-icons icon-aligned">search</i>
  <span class="d-none d-lg-block">Pesquisar</span>
</button>
```

#### 6. Calcular o número total de páginas

* Obter o valor:

```
total_paginas = (total_resultados / resultados_por_pagina) + 1
```

---

### 📄 Processamento de resultados

#### 7. Para cada resultado encontrado (decisão monocrática):

* Clicar na opção de **visualizar/copiar citação**, identificada pelo ícone:

```html
<i class="material-icons icon-aligned iconeComTexto mr-1">content_copy</i>
```

* Aguardar o carregamento da div de citação:

```html
<div class="citacao" id="divConteudoCitacao"></div>
```

* Em seguida, clicar em **“Copiar”**, cujo elemento é:

```html
<a id="iconCopiarCitacao" href="#/" class="eproc-button text-success m-1" title="">
  <i class="material-icons icon-aligned-sm iconeComTexto" style="font-size: 1.2rem">content_paste</i>
  Copiar
</a>
```

* Capturar o conteúdo copiado e **salvar em um arquivo JSON**.

#### 8. Continuar para o próximo resultado

* Após salvar o conteúdo do documento atual, avançar para o **próximo documento da página**.
* Repetir o processo até processar todos os resultados da página atual.

#### 9. Avançar para a próxima página

* Após terminar a página, avançar para a próxima página de resultados.
* Repetir o processo (passos 7 e 8) até atingir a **página final**.

#### 10. Encerrar a raspagem

* Quando o último documento da última página for copiado e salvo, encerrar a execução do script.

---

### 🧩 Observações técnicas

* O comportamento AJAX do site exige pequenas pausas (`sleep`) entre ações para garantir que os elementos estejam carregados.
* Utilize verificações de visibilidade de elementos antes de interagir.
* A estrutura do script deve seguir o padrão já existente no `stf_scraper`, apenas substituindo seletores e lógicas específicas para o site do TRF4.

Prompt mais técnico para executar isso.
## Prompt: Scraping Paralelo TRF4 com Controle de Paginação Compartilhada (Sem Threads)

**Objetivo:**
Implementar scraping paralelo no spider TRF4 região, onde múltiplos navegadores (definidos por `settings['parallel_browser_count']`) acessam páginas diferentes de uma mesma query, compartilhando uma única variável de controle de página onde a página é estática em AJAX. Não haverá divisão de grupos de queries no JSON; todos os workers usam a mesma URL base, variando apenas o parâmetro de página.

**Requisitos:**

1. **Configuração:**
    - Definir `parallel_browser_count` nas settings do Scrapy.
    - Inicializar `current_page_number = 1` como variável compartilhada entre os navegadores.

2. **Controle de concorrência (sem threads):**
    - Implementar mecanismo de trava (lock) para garantir que apenas UM navegador possa incrementar `current_page_number` por vez.
    - Quando um navegador terminar de raspar uma página que é estática porém tem sua numeração no final e quiser avançar, ele deve:
      - Adquirir o lock.
      - Incrementar `current_page_number`.
      - Liberar o lock.
    - Outros navegadores que terminarem antes devem aguardar a liberação do lock para acessar o próximo número de página.

3. **Execução:**
    - Todos os navegadores usam a mesma URL base, alterando apenas o parâmetro `page=current_page_number`.
    - Não criar grupos de queries ou arquivos JSON separados para cada worker.
    - O spider deve continuar até que não haja mais páginas para raspar (última página identificada pelo navegador).

4. **Persistência:**
    - Persistir `current_page_number` em arquivo ou variável global protegida por lock para garantir continuidade em caso de falha.

**Resumo:**
Implementar scraping paralelo com controle de paginação compartilhada (onde a página é estática AJAX, logo o link não muda), sem grupos e sem threads, usando lock externo para garantir que apenas um navegador incremente a variável de página por vez. Todos os workers usam a mesma query e URL base, variando apenas o número da página. 

