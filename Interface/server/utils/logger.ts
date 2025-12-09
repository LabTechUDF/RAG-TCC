export enum LogLevel {
  DEBUG = 'DEBUG',
  INFO = 'INFO',
  WARN = 'WARN',
  ERROR = 'ERROR'
}

interface LogEntry {
  timestamp: string
  level: LogLevel
  message: string
  context?: string
  data?: any
  error?: any
}

class Logger {
  private formatLog(entry: LogEntry): string {
    const { timestamp, level, message, context, data, error } = entry
    let logMessage = `[${timestamp}] [${level}]`
    
    if (context) {
      logMessage += ` [${context}]`
    }
    
    logMessage += ` ${message}`
    
    if (data) {
      try {
        logMessage += ` | Data: ${JSON.stringify(data)}`
      } catch {
        logMessage += ` | Data: [Unable to stringify]`
      }
    }
    
    if (error) {
      logMessage += ` | Error: ${error.message || JSON.stringify(error)}`
      if (error.stack) {
        logMessage += `\n${error.stack}`
      }
    }
    
    return logMessage
  }

  private async writeToFile(logMessage: string) {
    // Only write to file on server side
    if (typeof window === 'undefined') {
      try {
        // Dynamic import para evitar problemas com o build
        const fs = await import('fs')
        const path = await import('path')
        const logPath = path.join(process.cwd(), 'application.log')
        fs.appendFileSync(logPath, logMessage + '\n', 'utf8')
      } catch {
        // Silently fail - não queremos que o log quebre a aplicação
      }
    }
  }

  private log(level: LogLevel, message: string, context?: string, data?: any, error?: any) {
    const timestamp = new Date().toISOString()
    const entry: LogEntry = {
      timestamp,
      level,
      message,
      context,
      data,
      error
    }

    const formattedLog = this.formatLog(entry)
    
    // Output to console
    switch (level) {
      case LogLevel.DEBUG:
        console.debug(formattedLog)
        break
      case LogLevel.INFO:
        console.info(formattedLog)
        break
      case LogLevel.WARN:
        console.warn(formattedLog)
        break
      case LogLevel.ERROR:
        console.error(formattedLog)
        break
    }

    // Write to file (async, non-blocking)
    this.writeToFile(formattedLog).catch(() => {
      // Ignore errors
    })
  }

  debug(message: string, context?: string, data?: any) {
    this.log(LogLevel.DEBUG, message, context, data)
  }

  info(message: string, context?: string, data?: any) {
    this.log(LogLevel.INFO, message, context, data)
  }

  warn(message: string, context?: string, data?: any) {
    this.log(LogLevel.WARN, message, context, data)
  }

  error(message: string, context?: string, data?: any, error?: any) {
    this.log(LogLevel.ERROR, message, context, data, error)
  }
}

// Export singleton instance
export const logger = new Logger()
