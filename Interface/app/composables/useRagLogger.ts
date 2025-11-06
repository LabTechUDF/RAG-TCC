/**
 * RAG Ops Logger
 * 
 * Gera logs estruturados do pipeline RAG (G1 → DBVECTOR → G2)
 * para monitoramento e debugging.
 */

interface G1Metrics {
  model: string
  optimized_query: string
  tokens_count: number
  used_clusters: string[]
  latency_ms: number
}

interface VDBMetrics {
  backend: 'faiss' | 'opensearch' | 'hybrid'
  k: number
  total: number
  avg_score: number
  top_score: number
  doc_ids: string[]
  latency_ms: number
}

interface G2Metrics {
  model: string
  coverage: 'high' | 'medium' | 'low' | 'none'
  citations_used: string[]
  suggestions_count: number
  answer_chars: number
  latency_ms: number
}

interface RAGLogEntry {
  request_id: string
  timestamp: string
  user_query: string
  lang: string
  g1: G1Metrics
  vdb: VDBMetrics
  g2: G2Metrics
  pipeline_total_ms: number
  error?: string
}

interface LogCheck {
  status: 'OK' | 'WARN' | 'ERROR'
  component: 'G1' | 'VDB' | 'G2' | 'PIPELINE'
  message: string
}

export function useRagLogger() {
  /**
   * Gera ID único para requisição
   */
  function generateRequestId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  /**
   * Trunca string longa
   */
  function truncate(str: string, maxLen: number = 120): string {
    if (str.length <= maxLen) return str
    return str.substring(0, maxLen) + '…'
  }

  /**
   * Formata score com 3 casas decimais
   */
  function formatScore(score: number): string {
    return score.toFixed(3)
  }

  /**
   * Avalia status do pipeline baseado nas métricas
   */
  function assessStatus(entry: RAGLogEntry): 'OK' | 'WARN' | 'ERROR' {
    // ERROR conditions
    if (entry.error && entry.error.length > 0) return 'ERROR'
    if (entry.vdb.total === 0) return 'ERROR'
    if (!entry.g1.optimized_query || entry.g1.optimized_query.length === 0) return 'ERROR'
    if (entry.g2.answer_chars === 0) return 'ERROR'
    
    // Check citations validity (case-insensitive)
    const docIdsLower = entry.vdb.doc_ids.map(id => id.toLowerCase())
    const invalidCitations = entry.g2.citations_used.filter(
      cite => !docIdsLower.includes(cite.toLowerCase())
    )
    if (invalidCitations.length > 0) return 'ERROR'
    
    // WARN conditions
    if (entry.g1.tokens_count < 6 || entry.g1.tokens_count > 20) return 'WARN'
    if (entry.vdb.avg_score < 0.50) return 'WARN'
    if (entry.g2.coverage === 'low') return 'WARN'
    if (entry.g2.citations_used.length === 0 && entry.vdb.total >= 1) return 'WARN'
    if (entry.g2.suggestions_count > 0) return 'WARN'
    if (entry.g1.latency_ms > 800) return 'WARN'
    if (entry.vdb.latency_ms > 400) return 'WARN'
    if (entry.g2.latency_ms > 1500) return 'WARN'
    if (entry.pipeline_total_ms > 2500) return 'WARN'
    
    // OK conditions
    if (
      entry.g1.optimized_query.length > 0 &&
      entry.g1.tokens_count >= 6 && entry.g1.tokens_count <= 20 &&
      entry.g1.used_clusters.length <= 3 &&
      entry.vdb.total >= 1 &&
      entry.vdb.avg_score >= 0.50 &&
      (entry.g2.coverage === 'high' || entry.g2.coverage === 'medium') &&
      entry.g2.citations_used.length >= 1 &&
      !entry.error
    ) {
      return 'OK'
    }
    
    return 'WARN'
  }

  /**
   * Gera lista de checks
   */
  function generateChecks(entry: RAGLogEntry): LogCheck[] {
    const checks: LogCheck[] = []
    
    // G1 Checks
    if (entry.g1.tokens_count >= 6 && entry.g1.tokens_count <= 20) {
      checks.push({
        status: 'OK',
        component: 'G1',
        message: `tokens [ok] (${entry.g1.tokens_count} ∈ 6–20)`
      })
    } else {
      checks.push({
        status: 'WARN',
        component: 'G1',
        message: `tokens [warn] (${entry.g1.tokens_count} ∉ 6–20)`
      })
    }
    
    if (entry.g1.used_clusters.length <= 3) {
      checks.push({
        status: 'OK',
        component: 'G1',
        message: `clusters [ok] (${entry.g1.used_clusters.length} ≤ 3)`
      })
    } else {
      checks.push({
        status: 'WARN',
        component: 'G1',
        message: `clusters [warn] (${entry.g1.used_clusters.length} > 3)`
      })
    }
    
    if (entry.g1.latency_ms <= 800) {
      checks.push({
        status: 'OK',
        component: 'G1',
        message: `latency [ok] (${entry.g1.latency_ms}ms ≤ 800ms)`
      })
    } else {
      checks.push({
        status: 'WARN',
        component: 'G1',
        message: `latency [warn] (${entry.g1.latency_ms}ms > 800ms)`
      })
    }
    
    // VDB Checks
    if (entry.vdb.total >= 1) {
      checks.push({
        status: 'OK',
        component: 'VDB',
        message: `docs [ok] (${entry.vdb.total} ≥ 1)`
      })
    } else {
      checks.push({
        status: 'ERROR',
        component: 'VDB',
        message: `docs [error] (${entry.vdb.total} = 0)`
      })
    }
    
    if (entry.vdb.avg_score >= 0.50) {
      checks.push({
        status: 'OK',
        component: 'VDB',
        message: `avg_score [ok] (${formatScore(entry.vdb.avg_score)} ≥ 0.50)`
      })
    } else {
      checks.push({
        status: 'WARN',
        component: 'VDB',
        message: `avg_score [warn] (${formatScore(entry.vdb.avg_score)} < 0.50)`
      })
    }
    
    if (entry.vdb.latency_ms <= 400) {
      checks.push({
        status: 'OK',
        component: 'VDB',
        message: `latency [ok] (${entry.vdb.latency_ms}ms ≤ 400ms)`
      })
    } else {
      checks.push({
        status: 'WARN',
        component: 'VDB',
        message: `latency [warn] (${entry.vdb.latency_ms}ms > 400ms)`
      })
    }
    
    // G2 Checks
    if (entry.g2.coverage === 'high' || entry.g2.coverage === 'medium') {
      checks.push({
        status: 'OK',
        component: 'G2',
        message: `coverage [ok] (${entry.g2.coverage})`
      })
    } else if (entry.g2.coverage === 'low') {
      checks.push({
        status: 'WARN',
        component: 'G2',
        message: `coverage [warn] (${entry.g2.coverage})`
      })
    } else {
      checks.push({
        status: 'ERROR',
        component: 'G2',
        message: `coverage [error] (${entry.g2.coverage})`
      })
    }
    
    if (entry.g2.citations_used.length >= 1) {
      checks.push({
        status: 'OK',
        component: 'G2',
        message: `citations [ok] (${entry.g2.citations_used.length} ≥ 1)`
      })
    } else if (entry.vdb.total >= 1) {
      checks.push({
        status: 'WARN',
        component: 'G2',
        message: `citations [warn] (0 citações com ${entry.vdb.total} docs)`
      })
    }
    
    // Validate citations (case-insensitive comparison)
    const docIdsLower = entry.vdb.doc_ids.map(id => id.toLowerCase())
    const invalidCitations = entry.g2.citations_used.filter(
      cite => !docIdsLower.includes(cite.toLowerCase())
    )
    if (invalidCitations.length > 0) {
      checks.push({
        status: 'ERROR',
        component: 'G2',
        message: `citations [error] (IDs inválidos: ${invalidCitations.join(', ')})`
      })
    }
    
    if (entry.g2.suggestions_count > 0) {
      checks.push({
        status: 'WARN',
        component: 'G2',
        message: `suggestions [warn] (${entry.g2.suggestions_count} sugestões geradas)`
      })
    }
    
    if (entry.g2.latency_ms <= 1500) {
      checks.push({
        status: 'OK',
        component: 'G2',
        message: `latency [ok] (${entry.g2.latency_ms}ms ≤ 1500ms)`
      })
    } else {
      checks.push({
        status: 'WARN',
        component: 'G2',
        message: `latency [warn] (${entry.g2.latency_ms}ms > 1500ms)`
      })
    }
    
    // Pipeline Check
    if (entry.pipeline_total_ms <= 2500) {
      checks.push({
        status: 'OK',
        component: 'PIPELINE',
        message: `total [ok] (${entry.pipeline_total_ms}ms ≤ 2500ms)`
      })
    } else {
      checks.push({
        status: 'WARN',
        component: 'PIPELINE',
        message: `total [warn] (${entry.pipeline_total_ms}ms > 2500ms)`
      })
    }
    
    // Error check
    if (entry.error && entry.error.length > 0) {
      checks.push({
        status: 'ERROR',
        component: 'PIPELINE',
        message: `error: ${truncate(entry.error, 80)}`
      })
    }
    
    return checks
  }

  /**
   * Formata log em texto legível
   */
  function formatHumanReadable(entry: RAGLogEntry, status: string, checks: LogCheck[]): string {
    const lines: string[] = []
    
    lines.push(`RAG ▶︎ request_id=${entry.request_id} │ ${entry.timestamp} │ lang=${entry.lang}`)
    lines.push(`• STATUS: ${status}`)
    
    // G1
    lines.push(`• G1  QueryBuilder`)
    lines.push(`  - model=${entry.g1.model} │ tokens=${entry.g1.tokens_count} │ clusters=${JSON.stringify(entry.g1.used_clusters)}`)
    lines.push(`  - query="${truncate(entry.g1.optimized_query)}"`)
    lines.push(`  - latency=${entry.g1.latency_ms}ms`)
    
    // VDB
    lines.push(`• VDB VectorSearch`)
    lines.push(`  - backend=${entry.vdb.backend} │ k=${entry.vdb.k} │ total=${entry.vdb.total}`)
    lines.push(`  - avg_score=${formatScore(entry.vdb.avg_score)} │ top_score=${formatScore(entry.vdb.top_score)}`)
    lines.push(`  - doc_ids=${JSON.stringify(entry.vdb.doc_ids)}`)
    lines.push(`  - latency=${entry.vdb.latency_ms}ms`)
    
    // G2
    lines.push(`• G2  AnswerComposer`)
    lines.push(`  - model=${entry.g2.model} │ coverage=${entry.g2.coverage} │ citations=${JSON.stringify(entry.g2.citations_used)}`)
    lines.push(`  - suggestions=${entry.g2.suggestions_count} │ answer_chars=${entry.g2.answer_chars}`)
    lines.push(`  - latency=${entry.g2.latency_ms}ms`)
    
    // Checks
    lines.push(`• CHECKS:`)
    checks.forEach(check => {
      const icon = check.status === 'OK' ? '✅' : check.status === 'WARN' ? '⚠️' : '❌'
      lines.push(`  ${icon} ${check.component}: ${check.message}`)
    })
    
    // Error
    lines.push(`• ERROR: ${entry.error || '-'}`)
    
    // Total
    lines.push(`• TOTAL: ${entry.pipeline_total_ms}ms`)
    
    return lines.join('\n')
  }

  /**
   * Formata log em JSON (NDJSON)
   */
  function formatJSON(entry: RAGLogEntry, status: string, checks: LogCheck[]): string {
    return JSON.stringify({
      request_id: entry.request_id,
      timestamp: entry.timestamp,
      status,
      lang: entry.lang,
      user_query: truncate(entry.user_query),
      g1: entry.g1,
      vdb: entry.vdb,
      g2: entry.g2,
      latency_total_ms: entry.pipeline_total_ms,
      checks: checks.map(c => `${c.status}:${c.component}:${c.message}`),
      error: entry.error || ''
    })
  }

  /**
   * Gera log completo (texto + JSON)
   */
  function generateLog(entry: RAGLogEntry): string {
    const status = assessStatus(entry)
    const checks = generateChecks(entry)
    
    const humanReadable = formatHumanReadable(entry, status, checks)
    const jsonLine = formatJSON(entry, status, checks)
    
    return `${humanReadable}\n\n${jsonLine}`
  }

  /**
   * Log para console com formatação
   */
  function logToConsole(entry: RAGLogEntry): void {
    const log = generateLog(entry)
    const status = assessStatus(entry)
    
    if (status === 'ERROR') {
      console.error(log)
    } else if (status === 'WARN') {
      console.warn(log)
    } else {
      console.log(log)
    }
  }

  /**
   * Exporta log para arquivo (opcional - requer backend)
   */
  async function exportLog(entry: RAGLogEntry, format: 'json' | 'text' = 'json'): Promise<string> {
    const log = generateLog(entry)
    
    // No navegador, apenas retorna o log
    // Em produção, você pode enviar para um endpoint de logging
    return format === 'json' ? formatJSON(entry, assessStatus(entry), generateChecks(entry)) : log
  }

  return {
    generateRequestId,
    generateLog,
    logToConsole,
    exportLog,
    assessStatus,
    generateChecks,
    truncate,
    formatScore
  }
}
