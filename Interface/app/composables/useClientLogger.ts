export enum ClientLogLevel {
  DEBUG = 'DEBUG',
  INFO = 'INFO',
  WARN = 'WARN',
  ERROR = 'ERROR'
}

interface ClientLogEntry {
  timestamp: string
  level: ClientLogLevel
  message: string
  context?: string
  data?: any
  error?: any
}

class ClientLogger {
  private formatLog(entry: ClientLogEntry): string {
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
    }
    
    return logMessage
  }

  private log(level: ClientLogLevel, message: string, context?: string, data?: any, error?: any) {
    const timestamp = new Date().toISOString()
    const entry: ClientLogEntry = {
      timestamp,
      level,
      message,
      context,
      data,
      error
    }

    const formattedLog = this.formatLog(entry)
    
    // Output to console with appropriate styling
    switch (level) {
      case ClientLogLevel.DEBUG:
        console.debug(formattedLog, data, error)
        break
      case ClientLogLevel.INFO:
        console.info(formattedLog, data, error)
        break
      case ClientLogLevel.WARN:
        console.warn(formattedLog, data, error)
        break
      case ClientLogLevel.ERROR:
        console.error(formattedLog, data, error)
        if (error?.stack) {
          console.error(error.stack)
        }
        break
    }
  }

  debug(message: string, context?: string, data?: any) {
    this.log(ClientLogLevel.DEBUG, message, context, data)
  }

  info(message: string, context?: string, data?: any) {
    this.log(ClientLogLevel.INFO, message, context, data)
  }

  warn(message: string, context?: string, data?: any) {
    this.log(ClientLogLevel.WARN, message, context, data)
  }

  error(message: string, context?: string, data?: any, error?: any) {
    this.log(ClientLogLevel.ERROR, message, context, data, error)
  }
}

// Export composable
export const useClientLogger = () => {
  const logger = new ClientLogger()
  return logger
}
