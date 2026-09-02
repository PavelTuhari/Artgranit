import Foundation
import Combine
import SwiftUI
import UserNotifications
import AudioToolbox
import UIKit

/// Ядро: опрос источников, watchdog связи, движок «привлечения внимания» (ТЗ §4).
@MainActor
final class MonitorStore: ObservableObject {
    static let shared = MonitorStore()
    let settings = AppSettings.shared

    @Published var zabbix = LinkInfo()
    @Published var tbc = LinkInfo()
    @Published var problems: [ZProblem] = []
    @Published var temps: [HostTemps] = []
    @Published var tempHistory: [String: [TempPoint]] = [:]   // "host:1" -> точки
    @Published var stats = TBCStats()
    @Published var events: [TBCEvent] = []
    @Published var cassa = CassaSummary()
    @Published var attention: [AttentionItem] = []
    @Published var isRefreshing = false
    @Published var mutedUntil: Date?
    @Published var lastRefresh: Date?

    private var pollTimer: Timer?
    private var repeatTimer: Timer?
    private var notified: [String: AttentionLevel] = [:]   // дедупликация по ключу
    private var prevProblemIDs: Set<String> = []

    var topLevel: AttentionLevel { attention.map(\.level).max() ?? .none }
    var isMuted: Bool { if let m = mutedUntil { return m > Date() }; return false }
    /// Заслонка показывается только на critical и пока не нажали «Понял»
    var showTakeover: Bool { topLevel == .critical && !isMuted }

    // MARK: цикл опроса

    func start() {
        stop()
        Task { await refresh() }
        pollTimer = Timer.scheduledTimer(withTimeInterval: TimeInterval(max(10, settings.pollSeconds)), repeats: true) { [weak self] _ in
            Task { await self?.refresh() }
        }
        repeatTimer = Timer.scheduledTimer(withTimeInterval: TimeInterval(max(5, settings.repeatSeconds)), repeats: true) { [weak self] _ in
            Task { @MainActor in self?.repeatAlarmIfNeeded() }
        }
    }

    func stop() {
        pollTimer?.invalidate(); pollTimer = nil
        repeatTimer?.invalidate(); repeatTimer = nil
    }

    func refresh() async {
        guard !isRefreshing else { return }
        isRefreshing = true
        defer { isRefreshing = false; lastRefresh = Date(); evaluate() }

        async let z: Void = refreshZabbix()
        async let t: Void = refreshTBC()
        _ = await (z, t)
    }

    private func refreshZabbix() async {
        zabbix.lastAttempt = Date()
        guard let url = URL(string: settings.zabbixURL) else { zabbix.lastError = "адрес Zabbix не задан"; return }
        let client = ZabbixClient(url: url, user: settings.zabbixUser, password: settings.zabbixPassword)
        do {
            let s = try await client.fetch(hosts: settings.hostList)
            problems = s.problems
            temps = s.temps
            for h in s.temps {
                for (n, v) in [(1, h.cpu1), (2, h.cpu2)] {
                    guard let v else { continue }
                    var arr = tempHistory["\(h.host):\(n)"] ?? []
                    arr.append(TempPoint(t: Date(), value: v))
                    if arr.count > 240 { arr.removeFirst(arr.count - 240) }
                    tempHistory["\(h.host):\(n)"] = arr
                }
            }
            zabbix.lastOK = Date(); zabbix.lastError = nil; zabbix.latencyMs = s.latencyMs
        } catch {
            zabbix.lastError = error.localizedDescription
        }
    }

    private func refreshTBC() async {
        tbc.lastAttempt = Date()
        guard let url = URL(string: settings.tbcBaseURL) else { tbc.lastError = "адрес TBControl не задан"; return }
        do {
            let s = try await TBCClient(base: url, inviteHash: settings.inviteHash).fetch()
            stats = s.stats; events = s.events; cassa = s.cassa
            tbc.lastOK = Date(); tbc.lastError = nil; tbc.latencyMs = s.latencyMs
        } catch {
            tbc.lastError = error.localizedDescription
        }
    }

    // MARK: движок внимания

    func evaluate() {
        var items: [AttentionItem] = []
        let now = Date()

        // 1. Связь с Zabbix — самое важное (ТЗ §4)
        let zs = zabbix.state(staleMin: settings.staleMinutes, lostMin: settings.lostMinutes)
        if zs == .lost || zs == .stale {
            let mins = zabbix.minutesSinceOK.map { "\($0) мин" } ?? "никогда"
            var lvl: AttentionLevel = zs == .lost ? .critical : .warning
            if settings.outsideVPN && lvl == .critical { lvl = .warning }   // вне VPN — ожидаемо
            items.append(AttentionItem(key: "link:zabbix", level: lvl,
                                       title: zs == .lost ? "НЕТ СВЯЗИ С ZABBIX" : "Zabbix отвечает с задержкой",
                                       detail: "последний успешный опрос: \(mins)" + (zabbix.lastError.map { " · \($0)" } ?? ""),
                                       since: zabbix.lastOK ?? now))
        } else if zabbix.lastOK == nil, zabbix.lastAttempt != nil {
            items.append(AttentionItem(key: "link:zabbix", level: settings.outsideVPN ? .notice : .warning,
                                       title: "Zabbix недоступен", detail: zabbix.lastError ?? "", since: now))
        }

        // 2. Связь с TBControl — уровнем ниже
        let ts = tbc.state(staleMin: settings.staleMinutes, lostMin: settings.lostMinutes * 2)
        if ts == .lost || ts == .stale {
            items.append(AttentionItem(key: "link:tbc", level: ts == .lost ? .warning : .notice,
                                       title: ts == .lost ? "Нет связи с TBControl" : "TBControl с задержкой",
                                       detail: "последний успешный опрос: \(tbc.minutesSinceOK.map { "\($0) мин" } ?? "—")",
                                       since: tbc.lastOK ?? now))
        }

        // 3. Температура CPU
        for h in temps {
            for (n, v) in [(1, h.cpu1), (2, h.cpu2)] {
                guard let v else { continue }
                if v >= settings.tempCrit {
                    items.append(AttentionItem(key: "temp:\(h.host):\(n)", level: .critical,
                                               title: "ПЕРЕГРЕВ CPU\(n) \(h.host)", detail: "\(v)℃ (порог \(settings.tempCrit))", since: now))
                } else if v > settings.tempWarn {
                    items.append(AttentionItem(key: "temp:\(h.host):\(n)", level: .warning,
                                               title: "t° CPU\(n) \(h.host) повышена", detail: "\(v)℃ (порог \(settings.tempWarn))", since: now))
                } else if v >= settings.tempWarn - 2 {
                    items.append(AttentionItem(key: "temp:\(h.host):\(n)", level: .notice,
                                               title: "t° CPU\(n) \(h.host) у порога", detail: "\(v)℃", since: now))
                }
            }
            if h.agentAvailable == false {
                items.append(AttentionItem(key: "host:\(h.host)", level: .critical,
                                           title: "СЕРВЕР \(h.host) НЕДОСТУПЕН", detail: "zabbix-агент не отвечает", since: now))
            }
        }

        // 4. Проблемы Zabbix High/Disaster
        for p in problems where p.priority >= 4 {
            items.append(AttentionItem(key: "trigger:\(p.id)", level: p.priority == 5 ? .critical : .warning,
                                       title: p.name, detail: "\(p.host) · \(p.severity)", since: p.lastChange ?? now))
        }
        // 5. TBControl P1
        if stats.p1 > 0 {
            items.append(AttentionItem(key: "tbc:p1", level: .warning, title: "События P1 в сети: \(stats.p1)",
                                       detail: "магазины critical: \(stats.storesCritical)", since: now))
        }

        items.sort { $0.level > $1.level }
        let old = attention
        attention = items
        notifyChanges(old: old, new: items)
        UNUserNotificationCenter.current().setBadgeCount(items.filter { $0.level >= .warning }.count) { _ in }
    }

    private func notifyChanges(old: [AttentionItem], new: [AttentionItem]) {
        // Уведомление — только при появлении/росте уровня (дедупликация по ключу)
        for it in new where it.level >= .warning {
            if let prev = notified[it.key], prev >= it.level { continue }
            notified[it.key] = it.level
            postNotification(it)
            haptic(it.level)
            if it.level == .critical { playAlarm() }
        }
        // Нормализация — зелёное уведомление и сброс дедупликации
        for o in old where o.level >= .warning && !new.contains(where: { $0.key == o.key }) {
            notified[o.key] = nil
            postNotification(AttentionItem(key: "ok:" + o.key, level: .none, title: "В норме: \(o.title)", detail: "", since: Date()))
        }
        if new.allSatisfy({ $0.level < .critical }) { mutedUntil = nil }
    }

    /// Повтор сигнала каждые N с, пока critical и не нажато «Понял» (ТЗ §4)
    private func repeatAlarmIfNeeded() {
        guard showTakeover, UIApplication.shared.applicationState == .active else { return }
        playAlarm(); haptic(.critical)
    }

    func acknowledge(minutes: Int = 30) {
        mutedUntil = Date().addingTimeInterval(TimeInterval(minutes * 60))
    }

    // MARK: сигналы

    func haptic(_ level: AttentionLevel) {
        let g = UINotificationFeedbackGenerator()
        g.prepare()
        g.notificationOccurred(level == .critical ? .error : .warning)
    }

    func playAlarm() {
        AudioServicesPlayAlertSound(SystemSoundID(1005))
        AudioServicesPlaySystemSound(kSystemSoundID_Vibrate)
    }

    func requestNotificationPermission() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { _, _ in }
    }

    private func postNotification(_ it: AttentionItem) {
        let c = UNMutableNotificationContent()
        c.title = (it.level == .critical ? "🔴 " : it.level == .warning ? "🟠 " : "🟢 ") + it.title
        c.body = it.detail
        c.sound = it.level == .critical ? .defaultCritical : .default
        c.interruptionLevel = it.level >= .warning ? .timeSensitive : .active
        c.threadIdentifier = it.key
        let req = UNNotificationRequest(identifier: it.key + "-\(Int(Date().timeIntervalSince1970))", content: c, trigger: nil)
        UNUserNotificationCenter.current().add(req)
    }

    /// «Тест сигнала» из настроек — воспроизводит critical-режим (ТЗ §6.2)
    func testAlarm() {
        attention.insert(AttentionItem(key: "test", level: .critical, title: "ТЕСТ СИГНАЛА",
                                       detail: "так выглядит критичная ситуация", since: Date()), at: 0)
        mutedUntil = nil
        playAlarm(); haptic(.critical)
        postNotification(attention[0])
        DispatchQueue.main.asyncAfter(deadline: .now() + 25) { [weak self] in
            self?.attention.removeAll { $0.key == "test" }
        }
    }
}
