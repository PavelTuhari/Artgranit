import SwiftUI

struct TemperatureView: View {
    @EnvironmentObject var store: MonitorStore
    @EnvironmentObject var settings: AppSettings

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 14) {
                    if store.temps.isEmpty {
                        ContentUnavailableView("Нет данных о температуре",
                                               systemImage: "thermometer.medium.slash",
                                               description: Text("Нужна связь с Zabbix (VPN) и items cpu.temp[1|2] на хостах: \(settings.tempHosts)"))
                    }
                    ForEach(store.temps) { h in
                        VStack(alignment: .leading, spacing: 10) {
                            HStack {
                                Text(h.host).font(.title3.bold())
                                Spacer()
                                if h.agentAvailable == false {
                                    Label("агент недоступен", systemImage: "wifi.slash").font(.caption).foregroundStyle(.red)
                                } else {
                                    Text("uptime \(h.uptimeText)").font(.caption).foregroundStyle(.secondary)
                                }
                            }
                            HStack(spacing: 14) {
                                Gauge(label: "CPU1", value: h.cpu1, warn: settings.tempWarn, crit: settings.tempCrit)
                                Gauge(label: "CPU2", value: h.cpu2, warn: settings.tempWarn, crit: settings.tempCrit)
                            }
                            Sparkline(points1: store.tempHistory["\(h.host):1"] ?? [],
                                      points2: store.tempHistory["\(h.host):2"] ?? [],
                                      warn: settings.tempWarn, crit: settings.tempCrit)
                                .frame(height: 70)
                            Text("обновлено \(h.updated.ago) назад · зоны: <\(settings.tempWarn) норма · \(settings.tempWarn)–\(settings.tempCrit - 1) повышена · ≥\(settings.tempCrit) перегрев")
                                .font(.caption2).foregroundStyle(.secondary)
                        }
                        .padding(14).background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 16))
                    }
                }
                .padding(.horizontal, 12).padding(.top, store.topLevel >= .notice ? 64 : 8)
            }
            .refreshable { await store.refresh() }
            .navigationTitle("Температура")
        }
    }
}

/// Полукруглый датчик с цветовыми зонами
struct Gauge: View {
    let label: String
    let value: Int?
    let warn: Int
    let crit: Int
    private let minT = 20.0, maxT = 90.0

    private func frac(_ v: Double) -> Double { min(max((v - minT) / (maxT - minT), 0), 1) }
    private var color: Color {
        guard let v = value else { return .gray }
        return v >= crit ? .red : v > warn ? .orange : .green
    }

    var body: some View {
        VStack(spacing: 4) {
            ZStack {
                Arc(from: 0, to: frac(Double(warn))).stroke(Color.green.opacity(0.35), style: .init(lineWidth: 10, lineCap: .butt))
                Arc(from: frac(Double(warn)), to: frac(Double(crit))).stroke(Color.orange.opacity(0.35), style: .init(lineWidth: 10, lineCap: .butt))
                Arc(from: frac(Double(crit)), to: 1).stroke(Color.red.opacity(0.35), style: .init(lineWidth: 10, lineCap: .butt))
                if let v = value {
                    Arc(from: 0, to: frac(Double(v))).stroke(color, style: .init(lineWidth: 10, lineCap: .round))
                }
                VStack(spacing: 0) {
                    Text(value.map { "\($0)" } ?? "—").font(.system(size: 30, weight: .bold, design: .rounded)).foregroundStyle(color)
                    Text("℃").font(.caption).foregroundStyle(.secondary)
                }.offset(y: 8)
            }
            .frame(height: 90)
            Text(label).font(.caption.bold())
        }
        .frame(maxWidth: .infinity)
    }
}

struct Arc: Shape {
    let from: Double, to: Double   // 0..1 по дуге 180°
    func path(in r: CGRect) -> Path {
        var p = Path()
        let c = CGPoint(x: r.midX, y: r.maxY - 6)
        let rad = min(r.width / 2, r.height) - 8
        p.addArc(center: c, radius: rad, startAngle: .degrees(180 + 180 * from), endAngle: .degrees(180 + 180 * to), clockwise: false)
        return p
    }
}

/// История за сессию: две линии + пороговые уровни
struct Sparkline: View {
    let points1: [TempPoint]
    let points2: [TempPoint]
    let warn: Int
    let crit: Int

    var body: some View {
        GeometryReader { g in
            let all = points1 + points2
            let lo = Double(min(all.map(\.value).min() ?? warn - 10, warn - 10))
            let hi = Double(max(all.map(\.value).max() ?? crit + 5, crit + 5))
            func y(_ v: Double) -> CGFloat { g.size.height - CGFloat((v - lo) / max(hi - lo, 1)) * g.size.height }
            func line(_ pts: [TempPoint]) -> Path {
                var p = Path()
                guard pts.count > 1 else { return p }
                for (i, pt) in pts.enumerated() {
                    let x = CGFloat(i) / CGFloat(pts.count - 1) * g.size.width
                    i == 0 ? p.move(to: CGPoint(x: x, y: y(Double(pt.value)))) : p.addLine(to: CGPoint(x: x, y: y(Double(pt.value))))
                }
                return p
            }
            ZStack {
                Path { p in p.move(to: CGPoint(x: 0, y: y(Double(warn)))); p.addLine(to: CGPoint(x: g.size.width, y: y(Double(warn)))) }
                    .stroke(Color.orange.opacity(0.5), style: .init(lineWidth: 1, dash: [4, 3]))
                Path { p in p.move(to: CGPoint(x: 0, y: y(Double(crit)))); p.addLine(to: CGPoint(x: g.size.width, y: y(Double(crit)))) }
                    .stroke(Color.red.opacity(0.5), style: .init(lineWidth: 1, dash: [4, 3]))
                line(points1).stroke(Color.blue, lineWidth: 2)
                line(points2).stroke(Color.purple, lineWidth: 2)
                if all.count < 2 {
                    Text("история накопится по мере опроса").font(.caption2).foregroundStyle(.secondary)
                }
            }
        }
    }
}
