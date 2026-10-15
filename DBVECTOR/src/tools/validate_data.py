"""
Script de validação de qualidade de dados para RAG Jurídico.
Valida campos obrigatórios, tamanho de texto, tokens residuais e duplicatas.
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Any

from src import config


def load_jsonl(filepath: Path) -> List[Dict[str, Any]]:
    """Carrega documentos de arquivo JSONL."""
    docs = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                docs.append(json.loads(line))
    return docs


def check_missing_fields(doc: Dict[str, Any], required_fields: List[str]) -> bool:
    """Verifica se documento possui todos os campos obrigatórios."""
    for field in required_fields:
        if field not in doc or not doc[field]:
            return True
    return False


def check_text_too_short(text: str, min_chars: int) -> bool:
    """Verifica se texto é muito curto."""
    return len(text.strip()) < min_chars


def check_bad_tokens(text: str) -> bool:
    """
    Verifica se texto contém tokens HTML/residuais indesejados.
    Procura por: ' br ', 'br ', '<br>', '<br/>', '&nbsp;', etc.
    """
    text_lower = text.lower()
    patterns = [
        r'\sbr\b',      # ' br' ou ' br ' (espaço antes + boundary)
        r'<br>',        # <br>
        r'<br\s*/>',    # <br/> ou <br />
        r'&nbsp;',      # &nbsp;
        r'&[a-z]+;',    # outras entidades HTML
        r'<[^>]+>',     # tags HTML genéricas
    ]
    
    for pattern in patterns:
        if re.search(pattern, text_lower):
            return True
    return False


def validate_dataset(
    docs: List[Dict[str, Any]],
    min_chars: int = 200,
    required_fields: List[str] = None,
    text_field: str = "content",
    id_field: str = "case_number"
) -> Dict[str, Any]:
    """
    Valida dataset completo e retorna métricas de qualidade.
    
    Args:
        docs: Lista de documentos
        min_chars: Tamanho mínimo de caracteres para texto
        required_fields: Campos obrigatórios (default: ['case_number', 'content'])
        text_field: Nome do campo de texto principal (default: 'content')
    
    Returns:
        Dicionário com métricas de validação
    """
    if required_fields is None:
        required_fields = ["case_number", "content"]
    
    total = len(docs)
    if total == 0:
        return {
            "total": 0,
            "missing_fields_pct": 0.0,
            "too_short_pct": 0.0,
            "bad_tokens_pct": 0.0,
            "dupe_ids": 0,
            "bad_overall_pct": 0.0,
            "ok_to_proceed": True
        }
    
    # Contadores
    missing_fields_count = 0
    too_short_count = 0
    bad_tokens_count = 0
    
    # Coleta IDs para detectar duplicatas (usa case_number como ID)
    ids = []
    
    for doc in docs:
        # Campos ausentes
        if check_missing_fields(doc, required_fields):
            missing_fields_count += 1
        
        # ID para duplicatas (tenta id_field primeiro, depois id)
        doc_id = doc.get(id_field) or doc.get("id")
        if doc_id:
            ids.append(doc_id)
        
        # Verifica texto (usa text_field configurável)
        text = doc.get(text_field) or doc.get("text") or ""
        if text:
            # Texto curto
            if check_text_too_short(text, min_chars):
                too_short_count += 1
            
            # Tokens ruins
            if check_bad_tokens(text):
                bad_tokens_count += 1
    
    # Duplicatas de ID
    id_counts = Counter(ids)
    dupe_ids = sum(1 for count in id_counts.values() if count > 1)
    
    # Percentuais
    missing_fields_pct = (missing_fields_count / total) * 100
    too_short_pct = (too_short_count / total) * 100
    bad_tokens_pct = (bad_tokens_count / total) * 100
    
    # % problemas geral (considera qualquer problema)
    # Documentos com pelo menos um problema
    problem_docs = set()
    for i, doc in enumerate(docs):
        if check_missing_fields(doc, required_fields):
            problem_docs.add(i)
        
        text = doc.get(text_field) or doc.get("text") or ""
        if text:
            if check_text_too_short(text, min_chars):
                problem_docs.add(i)
            if check_bad_tokens(text):
                problem_docs.add(i)
    
    # Adiciona duplicatas
    for doc_id in id_counts:
        if id_counts[doc_id] > 1:
            # Marca todos os docs com esse ID como problemáticos
            for i, doc in enumerate(docs):
                id_candidate = doc.get(id_field) or doc.get("id")
                if id_candidate == doc_id:
                    problem_docs.add(i)
    
    bad_overall_pct = (len(problem_docs) / total) * 100
    
    return {
        "total": total,
        "missing_fields_pct": round(missing_fields_pct, 2),
        "too_short_pct": round(too_short_pct, 2),
        "bad_tokens_pct": round(bad_tokens_pct, 2),
        "dupe_ids": dupe_ids,
        "bad_overall_pct": round(bad_overall_pct, 2),
        "ok_to_proceed": True  # Será atualizado após comparação com threshold
    }


def main():
    """CLI principal para validação de dados."""
    parser = argparse.ArgumentParser(
        description="Valida qualidade de dados para indexação RAG"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Caminho para arquivo JSONL de entrada"
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        default=config.MIN_CHARS,
        help=f"Tamanho mínimo de caracteres (default: {config.MIN_CHARS})"
    )
    parser.add_argument(
        "--max-bad-pct",
        type=float,
        default=config.VALIDATION_MAX_BAD_PCT,
        help=f"% máxima de docs problemáticos (default: {config.VALIDATION_MAX_BAD_PCT})"
    )
    parser.add_argument(
        "--report",
        type=str,
        default="reports/validation/report.json",
        help="Caminho para salvar relatório JSON"
    )
    parser.add_argument(
        "--required-fields",
        type=str,
        nargs="+",
        default=["case_number", "content"],
        help="Campos obrigatórios (default: case_number content)"
    )
    parser.add_argument(
        "--text-field",
        type=str,
        default="content",
        help="Nome do campo de texto principal (default: content)"
    )
    parser.add_argument(
        "--id-field",
        type=str,
        default="case_number",
        help="Campo usado para detectar duplicatas (default: case_number; use id quando um processo tem várias decisões)"
    )
    
    args = parser.parse_args()
    
    # Valida arquivo de entrada
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Erro: Arquivo não encontrado: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    print(f"📊 Validando dados de: {input_path}")
    print(f"📏 Min chars: {args.min_chars}")
    print(f"🎯 Max bad %: {args.max_bad_pct}")
    print()
    
    # Carrega e valida
    try:
        docs = load_jsonl(input_path)
        print(f"✅ {len(docs)} documentos carregados")
    except Exception as e:
        print(f"❌ Erro ao carregar arquivo: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Executa validação
    report = validate_dataset(
        docs,
        min_chars=args.min_chars,
        required_fields=args.required_fields,
        text_field=args.text_field,
        id_field=args.id_field
    )
    
    # Verifica threshold
    report["ok_to_proceed"] = report["bad_overall_pct"] <= args.max_bad_pct
    
    # Exibe resultados
    print("\n📈 Resultados da Validação:")
    print(f"   Total de documentos: {report['total']}")
    print(f"   Campos ausentes: {report['missing_fields_pct']:.2f}%")
    print(f"   Texto muito curto: {report['too_short_pct']:.2f}%")
    print(f"   Tokens ruins (HTML/br): {report['bad_tokens_pct']:.2f}%")
    print(f"   IDs duplicados: {report['dupe_ids']}")
    print(f"   → Problemas gerais: {report['bad_overall_pct']:.2f}%")
    print()
    
    # Salva relatório
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Relatório salvo em: {report_path}")
    
    # Gating: falha se acima do threshold
    if not report["ok_to_proceed"]:
        print()
        print(f"❌ FALHA: {report['bad_overall_pct']:.2f}% > {args.max_bad_pct}%")
        print("   Dataset não passou na validação de qualidade!")
        print("   Corrija os problemas antes de prosseguir com indexação.")
        sys.exit(2)
    else:
        print()
        print(f"✅ OK: Dataset aprovado ({report['bad_overall_pct']:.2f}% <= {args.max_bad_pct}%)")
        sys.exit(0)


if __name__ == "__main__":
    main()
