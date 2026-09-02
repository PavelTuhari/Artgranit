import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var store: MonitorStore
    @EnvironmentObject var settings: AppSettings

    var body: some View {
        NavigationStack {
            Form {
                Section("Zabbix (через VPN93)") {
                    TextField("URL api_jsonrpc.php", text: $settings.zabbixURL).textInputAutocapitalization(.never).keyboardType(.URL)
                    TextField("Пользователь", text: $settings.zabbixUser).textInputAutocapitalization(.never)
                    SecureField("Пароль", text: $settings.zabbixPassword)
                    TextField("Хосты с t° (через запятую)", text: $settings.tempHosts).textInputAutocapitalization(.never)
                    Toggle("Я вне VPN (не считать потерю Zabbix критичной)", isOn: $settings.outsideVPN)
                }
                Section("TBControl (nufarul)") {
                    TextField("Базовый URL", text: $settings.tbcBaseURL).textInputAutocapitalization(.never).keyboardType(.URL)
                    SecureField("Хэш инвайта (?h=…)", text: $settings.inviteHash)
                    Text("Инвайт создаётся в панели TBControl → Инвайты. Пароли и хэш хранятся в Keychain.")
                        .font(.caption).foregroundStyle(.secondary)
                }
                Section("Пороги температуры, ℃") {
                    Stepper("Повышена: > \(settings.tempWarn)", value: $settings.tempWarn, in: 30...90)
                    Stepper("Перегрев: ≥ \(settings.tempCrit)", value: $settings.tempCrit, in: settings.tempWarn + 1...100)
                }
                Section("Связь с мониторингом") {
                    Stepper("Задержка после \(settings.staleMinutes) мин", value: $settings.staleMinutes, in: 1...60)
                    Stepper("Потеря (critical) после \(settings.lostMinutes) мин", value: $settings.lostMinutes, in: settings.staleMinutes + 1...240)
                    Stepper("Опрос каждые \(settings.pollSeconds) с", value: $settings.pollSeconds, in: 10...300, step: 10)
                    Stepper("Повтор сигнала каждые \(settings.repeatSeconds) с", value: $settings.repeatSeconds, in: 5...120, step: 5)
                    Text("Изменения интервалов применяются после повторного открытия приложения.")
                        .font(.caption).foregroundStyle(.secondary)
                }
                Section("Проверка") {
                    Button {
                        Task { await store.refresh() }
                    } label: { Label("Опросить сейчас", systemImage: "arrow.clockwise") }
                    Button(role: .destructive) {
                        store.testAlarm()
                    } label: { Label("Тест сигнала (critical на 25 с)", systemImage: "bell.badge") }
                    if let m = store.mutedUntil, m > Date() {
                        Button("Снять заглушку (до \(m.formatted(date: .omitted, time: .shortened)))") { store.mutedUntil = nil }
                    }
                    LabeledContent("Zabbix", value: store.zabbix.lastError ?? "OK")
                    LabeledContent("TBControl", value: store.tbc.lastError ?? "OK")
                }
                Section {
                    Text("TBControl Mobile 1.0 · ТЗ: docs/TBControl/MOBILE_APP_TZ.md")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Настройки")
            .safeAreaInset(edge: .top) { if store.topLevel >= .notice { Color.clear.frame(height: 56) } }
        }
    }
}
