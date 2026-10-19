import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var store: MonitorStore
    @EnvironmentObject var settings: AppSettings

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 14) {
                    // Связь — первое, что видно (ТЗ §3.1)
                    HStack(spacing: 10) {
                        LinkCard(title: "Zabbix", info: store.zabbix, staleMin: settings.staleMinutes, lostMin: settings.lostMinutes)
                        LinkCard(title: "TBControl", info: store.tbc, staleMin: settings.staleMinutes, lostMin: settings.lostMinutes * 2)
                    }

                    // Температура серверов — мини-датчики
                    if !store.temps.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Температура CPU").font(.headline)
                            ForEach(store.temps) { h in
                                HStack {
                                    Text(h.host).font(.subheadline.bold()).frame(width: 90, alignment: .leading)
                                    TempPill(label: "CPU1", value: h.cpu1, warn: settings.tempWarn, crit: settings.tempCrit)
                                    TempPill(label: "CPU2", value: h.cpu2, warn: settings.tempWarn, crit: settings.tempCrit)
                                    Spacer()
                                    if h.agentAvailable == false {
                                        Image(systemName: "wifi.slash").foregroundStyle(.red)
                                    } else {
                                        Text("up \(h.uptimeText)").font(.caption2).foregroundStyle(.secondary)
                                    }
                                }
                            }
                        }
                        .padding(12).background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 14))
                    }

                    // Сеть магазинов (TBControl)
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Сеть магазинов").font(.headline)
                        HStack(spacing: 8) {
                            StatTile(title: "critical", value: "\(store.stats.storesCritical)", color: store.stats.storesCritical > 0 ? .red : .primary)
                            StatTile(title: "degraded", value: "\(store.stats.storesDegraded)", color: store.stats.storesDegraded > 0 ? .orange : .primary)
                            StatTile(title: "ok из \(store.stats.storesTotal)", value: "\(store.stats.storesOK)", color: .green)
                        }
                        HStack(spacing: 8) {
                            StatTile(title: "устройств offline", value: "\(store.stats.devicesOffline)", color: store.stats.devicesOffline > 0 ? .red : .primary)
                            StatTile(title: "события P1 / P2", value: "\(store.stats.p1) / \(store.stats.p2)", color: store.stats.p1 > 0 ? .red : .primary)
                            StatTile(title: "инцидентов", value: "\(store.stats.incidentsOpen)")
                        }
                        HStack(spacing: 8) {
                            StatTile(title: "кассы online", value: "\(store.cassa.regOnline) / \(store.cassa.regTotal)",
                                     color: store.cassa.regOffline > store.cassa.regOnline ? .orange : .green)
                            StatTile(title: "магазины online", value: "\(store.cassa.storesOnline) / \(store.cassa.storesTotal)")
                        }
                    }
                    .padding(12).background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 14))

                    // Топ проблем Zabbix
                    VStack(alignment: .leading, spacing: 6) {
                        HStack { Text("Проблемы Zabbix").font(.headline); Spacer(); Text("\(store.problems.count)").foregroundStyle(.secondary) }
                        ForEach(store.problems.prefix(6)) { p in
                            HStack(alignment: .top, spacing: 8) {
                                Circle().fill(p.color).frame(width: 8, height: 8).padding(.top, 6)
                                VStack(alignment: .leading, spacing: 1) {
                                    Text(p.name).font(.subheadline).lineLimit(2)
                                    Text("\(p.host) · \(p.severity)" + (p.lastChange.map { " · \($0.ago)" } ?? "")).font(.caption).foregroundStyle(.secondary)
                                }
                            }
                        }
                        if store.problems.isEmpty { Text("нет активных проблем").font(.caption).foregroundStyle(.secondary) }
                    }
                    .padding(12).background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 14))

                    if let lr = store.lastRefresh {
                        Text("обновлено \(lr.ago) назад · опрос каждые \(settings.pollSeconds) с").font(.caption2).foregroundStyle(.secondary)
                    }
                }
                .padding(.horizontal, 12).padding(.top, store.topLevel >= .notice ? 64 : 8)
            }
            .refreshable { await store.refresh() }
            .navigationTitle("TBControl")
            .toolbar {
                if store.isRefreshing { ProgressView() }
            }
        }
    }
}

struct TempPill: View {
    let label: String
    let value: Int?
    let warn: Int
    let crit: Int
    var color: Color {
        guard let v = value else { return .gray }
        return v >= crit ? .red : v > warn ? .orange : v >= warn - 2 ? .yellow : .green
    }
    var body: some View {
        HStack(spacing: 4) {
            Text(label).font(.caption2)
            Text(value.map { "\($0)℃" } ?? "—").font(.subheadline.bold())
        }
        .padding(.horizontal, 8).padding(.vertical, 4)
        .background(color.opacity(0.18), in: Capsule())
        .foregroundStyle(color == .yellow ? .primary : color)
    }
}
