import Foundation
import OSLog

@Observable
@MainActor
public final class GT1000Diagnostics {
    public struct Entry: Identifiable, Equatable, Sendable {
        public enum Level: String, Sendable {
            case debug = "DEBUG"
            case info = "INFO"
            case warning = "WARN"
            case error = "ERROR"
        }

        public let id: UUID
        public let timestamp: Date
        public let level: Level
        public let message: String

        public init(
            id: UUID = UUID(),
            timestamp: Date = Date(),
            level: Level,
            message: String
        ) {
            self.id = id
            self.timestamp = timestamp
            self.level = level
            self.message = message
        }

        public var formattedText: String {
            let timestamp = timestamp.formatted(
                .dateTime
                    .hour(.twoDigits(amPM: .omitted))
                    .minute(.twoDigits)
                    .second(.twoDigits)
                    .secondFraction(.fractional(3))
            )
            return "\(timestamp) \(level.rawValue) \(message)"
        }
    }

    public static let shared = GT1000Diagnostics()

    public private(set) var entries: [Entry] = []

    private let logger = Logger(subsystem: "com.gt1000.app", category: "diagnostics")
    private let maximumEntryCount: Int

    public init(maximumEntryCount: Int = 200) {
        self.maximumEntryCount = maximumEntryCount
    }

    public func debug(_ message: String) {
        record(.debug, message)
    }

    public func info(_ message: String) {
        record(.info, message)
    }

    public func warning(_ message: String) {
        record(.warning, message)
    }

    public func error(_ message: String) {
        record(.error, message)
    }

    public func clear() {
        entries.removeAll()
        logger.info("Cleared diagnostics log")
    }

    public var formattedText: String {
        entries.map(\.formattedText).joined(separator: "\n")
    }

    public var latestMessage: String {
        entries.last?.message ?? "No diagnostics yet"
    }

    private func record(_ level: Entry.Level, _ message: String) {
        let entry = Entry(level: level, message: message)
        entries.append(entry)

        if entries.count > maximumEntryCount {
            entries.removeFirst(entries.count - maximumEntryCount)
        }

        switch level {
        case .debug:
            logger.debug("\(message, privacy: .public)")
        case .info:
            logger.info("\(message, privacy: .public)")
        case .warning:
            logger.warning("\(message, privacy: .public)")
        case .error:
            logger.error("\(message, privacy: .public)")
        }
    }

}
