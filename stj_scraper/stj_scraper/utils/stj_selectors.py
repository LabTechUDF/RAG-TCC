"""
STJ SCON Selectors - XPath and CSS selectors for STJ SCON system
"""

# XPath for textarea with decision text
TEXTAREA_XPATH = '//*[@id="textSemformatacao1"]'

# CSS selector for textarea with decision text
TEXTAREA_CSS = '#textSemformatacao1'

# Selectors for decision listing page
DECISION_LINK_SELECTORS = [
    'a[onclick*="abreDetalheDiarioProcesso"]',
    'a[href*="verDecisao.asp"]',
    'a[href*="texto="]',
    'td.texto a',
    '.resultado a[href*="texto"]'
]

# Selectors for next page navigation
NEXT_PAGE_SELECTORS = [
    'a:contains("Próxima")',
    'a[href*="pagina="]',
    'input[value="Próxima"]',
    '.paginacao a:last-child'
]

# Selectors for decision metadata
RELATOR_SELECTORS = [
    '.relator',
    'td:contains("Relator")',
    'span:contains("RELATOR")'
]

DATE_SELECTORS = [
    '.data-julgamento',
    'td:contains("Data")',
    'span:contains("DJ")'
]

PARTES_SELECTORS = [
    '.partes',
    'td:contains("RECORRENTE")',
    'td:contains("RECORRIDO")'
]