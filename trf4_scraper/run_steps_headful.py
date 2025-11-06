#!/usr/bin/env python3
"""
Headful Playwright script para executar os passos 1–5 no site de jurisprudência do TRF4
usando as queries em `trf4_scraper/configs/queries.txt`.

Uso:
  python3 trf4_scraper/run_steps_headful.py --headed

Observação: exige `playwright` instalado e os navegadores (ex.: `playwright install chromium`).
"""

import time
import argparse
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

START_URL = 'https://jurisprudencia.trf4.jus.br/pesquisa/pesquisa.php'
QUERIES_PATH = Path(__file__).parent / 'configs' / 'queries.txt'

log = logging.getLogger('trf4_steps')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


def read_queries():
    if not QUERIES_PATH.exists():
        log.error(f'Arquivo de queries não encontrado: {QUERIES_PATH}')
        return []
    lines = [l.strip() for l in QUERIES_PATH.read_text(encoding='utf-8').splitlines()]
    return [l for l in lines if l]


def perform_steps(page, query, show_pause=1.0):
    """Executa os passos conforme pedido:
    1 - Abre o site
    2 - Clica no campo de input `#txtPesquisa` e insere a query
    3 - Clica em `#btnPesquisaAvancada`
    4 - Seleciona o tipo de documento "Decisão monocrática"
    5 - Clica em consultar (`#btnConsultar`) ou pressiona Enter
    """
    log.info('1 - Navegando para o site')
    page.goto(START_URL, wait_until='load')
    time.sleep(show_pause)

    log.info('2 - Localizando campo de input #txtPesquisa')
    try:
        page.wait_for_selector('#txtPesquisa', timeout=5000)
        page.click('#txtPesquisa')
        page.fill('#txtPesquisa', query)
    except PWTimeout:
        log.warning('#txtPesquisa não encontrada - tentando foco no body e enviar via evaluate')
        page.evaluate("(q) => { const el = document.querySelector('#txtPesquisa'); if(el) { el.focus(); el.value = q; el.dispatchEvent(new Event('input', { bubbles: true })); } }", query)
    time.sleep(show_pause)

    log.info('3 - Clicando em Pesquisa Avançada (#btnPesquisaAvancada)')
    try:
        page.wait_for_selector('#btnPesquisaAvancada', timeout=5000)
        page.click('#btnPesquisaAvancada')
    except PWTimeout:
        log.warning('#btnPesquisaAvancada não encontrada (selector pode ter mudado)')
    time.sleep(show_pause)

    log.info('4 - Selecionando "Decisão monocrática"')
    try:
        # Aguarda opções e tenta clicar no botão que contém o texto
        page.wait_for_selector('.filter-option-inner-inner', timeout=5000)
        page.evaluate("() => { const els = Array.from(document.querySelectorAll('.filter-option-inner-inner')); const target = els.find(e => e.textContent && e.textContent.trim().toLowerCase().includes('decisão monocrática')) || els[0]; if(target) target.click(); }")
    except PWTimeout:
        log.warning('Opção para selecionar tipo de documento não encontrada (timeout)')
    time.sleep(show_pause)

    log.info('5 - Submetendo pesquisa (clicando em #btnConsultar ou pressionando Enter)')
    try:
        # Tenta clicar no botão id #btnConsultar primeiro
        if page.query_selector('#btnConsultar'):
            page.click('#btnConsultar')
        elif page.query_selector('#btnConsultar_form_inicial'):
            page.click('#btnConsultar_form_inicial')
        else:
            # Pressiona Enter no campo
            page.press('#txtPesquisa', 'Enter')
    except Exception as e:
        log.exception('Falha ao submeter a pesquisa: %s', e)

    # Espera um pouco para ver os resultados
    time.sleep(2.0)


def main():
    parser = argparse.ArgumentParser(description='Executa passos 1-5 no site TRF4 com Playwright (headful)')
    parser.add_argument('--headed', action='store_true', help='Executar com browser visível (headful)')
    parser.add_argument('--query', type=str, default='', help='Executar apenas uma query específica (sobrescreve o arquivo)')
    args = parser.parse_args()

    queries = [args.query] if args.query else read_queries()
    if not queries:
        log.error('Nenhuma query para processar. Forneça via --query ou preencha configs/queries.txt')
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed, args=['--lang=pt-BR', '--no-sandbox', '--disable-dev-shm-usage'])
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        for q in queries:
            log.info('--- Iniciando query: %s', q)
            try:
                perform_steps(page, q, show_pause=1.0)
                log.info('Query finalizada (observe o navegador): %s', q)
                # Pausa entre queries para inspeção
                time.sleep(1.5)
            except Exception:
                log.exception('Erro ao processar query: %s', q)

        log.info('Fechando navegador')
        context.close()
        browser.close()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
