import Foundation
import SwiftUI

// MARK: - Уровни внимания (ТЗ §4)

enum AttentionLevel: Int, Comparable {
    case none = 0, notice, warning, critical

    static func < (a: AttentionLevel, b: AttentionLevel) -> Bool { a.rawValue < b.rawValue }

    var color: Color {
        switch self {
        case .none: return .green
        case .notice: return .yellow
        case .warning: return .orange
        case .critical: return .red
        }
    }

    var title: String {
        switch self {
        case .none: return "Норма"
        case .notice: return "Внимание"
        case .warning: return "Предупреждение"
        case .critical: return "КРИТИЧНО"
        }
    }
}

/// Одна причина для внимания: ключ нужен для дедупликации уведомлений.
struct AttentionItem: Identifiable, Equatable {
    let key: String          // link:zabbix / temp:cloudbd:1 / trigger:123 / host:cloudbd
    let level: AttentionLevel
    let title: String
    let detail: String
    let since: Date
    var id: String { key }
}

// MARK: - Состояние связи с источником

enum LinkState: String {
    case unknown = "нет данных", ok = "связь есть", stale = "задержка", lost = "СВЯЗЬ ПОТЕРЯНА"
}

struct LinkInfo: Equatable {
    var lastOK: Date?
    var lastAttempt: Date?
    var lastError: String?
    var latencyMs: Int?

    /// «Потеряна» считается по последнему УСПЕШНОМУ опросу (ТЗ §4).
    func state(staleMin: Int, lostMin: Int, now: Date = Date()) -> LinkState {
        guard let ok = lastOK else { return lastAttempt == nil ? .unknown : .lost }
        let m = now.timeIntervalSince(ok) / 60
        if m >= Double(lostMin) { return .lost }
        if m >= Double(staleMin) { return .stale }
        return .ok
    }

    var minutesSinceOK: Int? {
        guard let ok = lastOK else { return nil }
        return Int(Date().timeIntervalSince(ok) / 60)
    }
}

// MARK: - Zabbix

struct ZProblem: Identifiable, Equatable {
    let id: String           // triggerid
    let name: String
    let priority: Int        // 0..5
    let host: String
    let lastChange: Date?

    var severity: String {
        ["Not classified", "Information", "Warning", "Average", "High", "Disaster"][min(max(priority, 0), 5)]
    }
    var color: Color {
        switch priority {
        case 5, 4: return .red
        case 3: return .orange
        case 2: return .yellow
        default: return .gray
        }
    }
}

struct HostTemps: Identifiable, Equatable {
    let host: String
    var cpu1: Int?
    var cpu2: Int?
    var uptimeSec: Int?
    var agentAvailable: Bool?   // nil = неизвестно
    var updated: Date
    var id: String { host }

    var maxTemp: Int? { [cpu1, cpu2].compactMap { $0 }.max() }
    var uptimeText: String {
        guard let s = uptimeSec else { return "—" }
        let d = s / 86400, h = (s % 86400) / 3600
        return d > 0 ? "\(d) дн \(h) ч" : "\(h) ч \((s % 3600) / 60) мин"
    }
}

struct TempPoint: Identifiable {
    let id = UUID()
    let t: Date
    let value: Int
}

// MARK: - TBControl

struct TBCStats: Equatable {
    var storesTotal = 0, storesOK = 0, storesDegraded = 0, storesCritical = 0
    var devicesTotal = 0, devicesOnline = 0, devicesOffline = 0, devicesDegraded = 0
    var p1 = 0, p2 = 0, p3 = 0, p4 = 0
    var incidentsOpen = 0
    var posOnline = 0, posTotal = 0

    init() {}
    init(json: [String: Any]) {
        func d(_ k: String) -> [String: Any] { json[k] as? [String: Any] ?? [:] }
        func i(_ dict: [String: Any], _ k: String) -> Int { (dict[k] as? NSNumber)?.intValue ?? 0 }
        let s = d("stores"), dv = d("devices"), ev = d("events"), pos = d("pos")
        storesTotal = i(s, "total"); storesOK = i(s, "ok"); storesDegraded = i(s, "degraded"); storesCritical = i(s, "critical")
        devicesTotal = i(dv, "total"); devicesOnline = i(dv, "online"); devicesOffline = i(dv, "offline"); devicesDegraded = i(dv, "degraded")
        p1 = i(ev, "p1"); p2 = i(ev, "p2"); p3 = i(ev, "p3"); p4 = i(ev, "p4")
        incidentsOpen = i(json, "incidents_open")
        posOnline = i(pos, "online"); posTotal = i(pos, "total")
    }
}

struct TBCEvent: Identifiable, Equatable {
    let id: Int
    let problem: String
    let severity: String     // P1..P4
    let source: String
    let status: String
    let createdAt: String

    var color: Color {
        switch severity {
        case "P1": return .red
        case "P2": return .orange
        case "P3": return .yellow
        default: return .gray
        }
    }
}

struct CassaStore: Identifiable, Equatable {
    let codUniv: String
    let name: String
    let regTotal: Int
    let regOnline: Int
    let regOffline: Int
    let regShutdown: Int
    var id: String { codUniv }
    var status: String {
        if regTotal == 0 { return "нет касс" }
        if regOnline == 0 { return "OFFLINE" }
        return Double(regOnline) / Double(regTotal) >= 0.6 ? "работает" : "деградация"
    }
    var color: Color {
        if regTotal == 0 { return .gray }
        if regOnline == 0 { return .red }
        return Double(regOnline) / Double(regTotal) >= 0.6 ? .green : .orange
    }
}

struct CassaSummary: Equatable {
    var storesTotal = 0, storesOnline = 0, storesOffline = 0
    var regTotal = 0, regOnline = 0, regOffline = 0
    var checkedAt = ""
    var stores: [CassaStore] = []
}
