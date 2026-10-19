import SwiftUI

struct ProblemsView: View {
    @EnvironmentObject var store: MonitorStore

    private var grouped: [(String, [ZProblem])] {
        let order = [5, 4, 3, 2, 1, 0]
        return order.compactMap { pr in
            let items = store.problems.filter { $0.priority == pr }
            return items.isEmpty ? nil : (items[0].severity, items)
        }
    }

    var body: some View {
        NavigationStack {
            List {
                Section("Внимание сейчас (\(store.attention.count))") {
                    if store.attention.isEmpty {
                        Label("всё в норме", systemImage: "checkmark.circle.fill").foregroundStyle(.green)
                    }
                    ForEach(store.attention) { a in
                        HStack(alignment: .top, spacing: 10) {
                            RoundedRectangle(cornerRadius: 2).fill(a.level.color).frame(width: 5)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(a.title).font(.subheadline.bold())
                                if !a.detail.isEmpty { Text(a.detail).font(.caption).foregroundStyle(.secondary) }
                                Text("с \(a.since.ago) назад").font(.caption2).foregroundStyle(.tertiary)
                            }
                        }
                    }
                }
                ForEach(grouped, id: \.0) { sev, items in
                    Section("\(sev) · \(items.count)") {
                        ForEach(items) { p in
                            HStack(alignment: .top, spacing: 10) {
                                Circle().fill(p.color).frame(width: 10, height: 10).padding(.top, 5)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(p.name).font(.subheadline)
                                    Text(p.host + (p.lastChange.map { " · \($0.ago) назад" } ?? "")).font(.caption).foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }
                Section("События TBControl (open) · \(store.events.count)") {
                    ForEach(store.events.prefix(30)) { e in
                        HStack(alignment: .top, spacing: 10) {
                            Text(e.severity).font(.caption.bold()).foregroundStyle(.white)
                                .padding(.horizontal, 6).padding(.vertical, 2).background(e.color, in: Capsule())
                            VStack(alignment: .leading, spacing: 2) {
                                Text(e.problem).font(.subheadline)
                                Text("\(e.source) · \(e.createdAt)").font(.caption).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }
            .refreshable { await store.refresh() }
            .navigationTitle("Проблемы")
            .safeAreaInset(edge: .top) { if store.topLevel >= .notice { Color.clear.frame(height: 56) } }
        }
    }
}
