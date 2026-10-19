import SwiftUI

struct ContentView: View {
    @EnvironmentObject var store: MonitorStore

    var body: some View {
        ZStack(alignment: .top) {
            TabView {
                DashboardView().tabItem { Label("Обзор", systemImage: "gauge.with.dots.needle.67percent") }
                TemperatureView().tabItem { Label("Температура", systemImage: "thermometer.medium") }
                ProblemsView().tabItem { Label("Проблемы", systemImage: "exclamationmark.triangle") }
                    .badge(store.problems.filter { $0.priority >= 4 }.count)
                CassaView().tabItem { Label("Кассы", systemImage: "cart") }
                SettingsView().tabItem { Label("Настройки", systemImage: "gearshape") }
            }
            .tint(store.topLevel >= .warning ? store.topLevel.color : .accentColor)

            // Полоса внимания (notice/warning) вверху экрана
            if store.topLevel >= .notice && !store.showTakeover {
                AttentionBar()
                    .transition(.move(edge: .top).combined(with: .opacity))
            }

            // Полноэкранная заслонка (critical) до «Понял»
            if store.showTakeover {
                TakeoverView()
                    .transition(.opacity)
                    .zIndex(10)
            }
        }
        .animation(.easeInOut(duration: 0.3), value: store.topLevel)
        .animation(.easeInOut(duration: 0.3), value: store.showTakeover)
    }
}

/// Верхняя полоса: цвет = максимальный уровень, текст = первая причина
struct AttentionBar: View {
    @EnvironmentObject var store: MonitorStore
    var body: some View {
        let top = store.attention.first
        HStack(spacing: 10) {
            Image(systemName: store.topLevel == .warning ? "exclamationmark.triangle.fill" : "info.circle.fill")
            VStack(alignment: .leading, spacing: 1) {
                Text(top?.title ?? store.topLevel.title).font(.subheadline.bold()).lineLimit(1)
                if let d = top?.detail, !d.isEmpty { Text(d).font(.caption).lineLimit(1) }
            }
            Spacer()
            if store.attention.count > 1 {
                Text("+\(store.attention.count - 1)").font(.caption.bold())
                    .padding(.horizontal, 6).padding(.vertical, 2)
                    .background(.white.opacity(0.25), in: Capsule())
            }
        }
        .foregroundStyle(store.topLevel == .notice ? .black : .white)
        .padding(.horizontal, 14).padding(.vertical, 10)
        .background(store.topLevel.color)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .padding(.horizontal, 10).padding(.top, 4)
        .shadow(radius: 4)
    }
}

/// Красная заслонка с пульсацией — не пропадает, пока не нажали «Понял»
struct TakeoverView: View {
    @EnvironmentObject var store: MonitorStore
    @State private var pulse = false

    var body: some View {
        ZStack {
            Color.red.opacity(pulse ? 0.95 : 0.75).ignoresSafeArea()
            VStack(spacing: 18) {
                Image(systemName: "exclamationmark.octagon.fill")
                    .font(.system(size: 84)).scaleEffect(pulse ? 1.08 : 0.94)
                Text("КРИТИЧНО").font(.largeTitle.weight(.black)).tracking(2)
                VStack(spacing: 10) {
                    ForEach(store.attention.filter { $0.level == .critical }.prefix(4)) { it in
                        VStack(spacing: 2) {
                            Text(it.title).font(.title3.bold()).multilineTextAlignment(.center)
                            if !it.detail.isEmpty { Text(it.detail).font(.subheadline).opacity(0.9) }
                        }
                    }
                }
                .padding(.horizontal)
                Text("сигнал повторяется каждые \(store.settings.repeatSeconds) с").font(.caption).opacity(0.8)
                Button {
                    store.acknowledge()
                } label: {
                    Text("ПОНЯЛ — заглушить на 30 мин")
                        .font(.headline).padding(.vertical, 14).frame(maxWidth: .infinity)
                        .background(.white, in: RoundedRectangle(cornerRadius: 14))
                        .foregroundStyle(.red)
                }
                .padding(.horizontal, 30)
            }
            .foregroundStyle(.white)
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 0.7).repeatForever(autoreverses: true)) { pulse = true }
        }
    }
}

// MARK: - общие элементы

struct LinkCard: View {
    let title: String
    let info: LinkInfo
    let staleMin: Int
    let lostMin: Int

    var body: some View {
        let st = info.state(staleMin: staleMin, lostMin: lostMin)
        let color: Color = st == .ok ? .green : st == .stale ? .orange : st == .lost ? .red : .gray
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Circle().fill(color).frame(width: 10, height: 10)
                Text(title).font(.headline)
                Spacer()
                if let ms = info.latencyMs, st == .ok { Text("\(ms) мс").font(.caption).foregroundStyle(.secondary) }
            }
            Text(st.rawValue).font(.subheadline.bold()).foregroundStyle(color)
            Text(info.minutesSinceOK.map { "успешный опрос \($0) мин назад" } ?? "ещё не опрашивался")
                .font(.caption).foregroundStyle(.secondary)
            if let e = info.lastError { Text(e).font(.caption2).foregroundStyle(.red).lineLimit(2) }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(color.opacity(0.10), in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(color.opacity(0.5), lineWidth: 1))
    }
}

struct StatTile: View {
    let title: String
    let value: String
    var color: Color = .primary
    var body: some View {
        VStack(spacing: 4) {
            Text(value).font(.title2.bold()).foregroundStyle(color)
            Text(title).font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity).padding(.vertical, 10)
        .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 12))
    }
}

extension Date {
    var ago: String {
        let s = Int(Date().timeIntervalSince(self))
        if s < 60 { return "\(s) с" }
        if s < 3600 { return "\(s / 60) мин" }
        if s < 86400 { return "\(s / 3600) ч" }
        return "\(s / 86400) дн"
    }
}
