import SwiftUI

struct CassaView: View {
    @EnvironmentObject var store: MonitorStore

    var body: some View {
        NavigationStack {
            List {
                Section {
                    HStack(spacing: 8) {
                        StatTile(title: "магазины online", value: "\(store.cassa.storesOnline)/\(store.cassa.storesTotal)", color: .green)
                        StatTile(title: "offline", value: "\(store.cassa.storesOffline)", color: store.cassa.storesOffline > 0 ? .red : .primary)
                        StatTile(title: "кассы online", value: "\(store.cassa.regOnline)/\(store.cassa.regTotal)")
                    }
                    if !store.cassa.checkedAt.isEmpty {
                        Text("проверка на сервере: \(store.cassa.checkedAt)").font(.caption).foregroundStyle(.secondary)
                    }
                }
                Section("Магазины · \(store.cassa.stores.count)") {
                    ForEach(store.cassa.stores.sorted { $0.regOnline * 100 / max($0.regTotal, 1) < $1.regOnline * 100 / max($1.regTotal, 1) }) { s in
                        HStack {
                            Circle().fill(s.color).frame(width: 10, height: 10)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(s.name).font(.subheadline.bold())
                                Text("код \(s.codUniv) · \(s.status)").font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            Text("\(s.regOnline)/\(s.regTotal)").font(.headline).foregroundStyle(s.color)
                        }
                    }
                    if store.cassa.stores.isEmpty {
                        Text("нет данных — нужна связь с TBControl").font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
            .refreshable { await store.refresh() }
            .navigationTitle("Кассы")
            .safeAreaInset(edge: .top) { if store.topLevel >= .notice { Color.clear.frame(height: 56) } }
        }
    }
}
