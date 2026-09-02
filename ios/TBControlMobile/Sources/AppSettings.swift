import Foundation
import Combine

/// Настройки приложения (ТЗ §3.5). Адреса — в UserDefaults, секреты — в Keychain.
final class AppSettings: ObservableObject {
    static let shared = AppSettings()
    private let d = UserDefaults.standard

    @Published var zabbixURL: String { didSet { d.set(zabbixURL, forKey: "zabbixURL") } }
    @Published var zabbixUser: String { didSet { d.set(zabbixUser, forKey: "zabbixUser") } }
    @Published var zabbixPassword: String { didSet { Keychain.set(zabbixPassword, for: "zabbixPassword") } }
    @Published var tbcBaseURL: String { didSet { d.set(tbcBaseURL, forKey: "tbcBaseURL") } }
    @Published var inviteHash: String { didSet { Keychain.set(inviteHash, for: "inviteHash") } }
    /// Хосты Zabbix, у которых читаем cpu.temp[1|2]
    @Published var tempHosts: String { didSet { d.set(tempHosts, forKey: "tempHosts") } }

    @Published var tempWarn: Int { didSet { d.set(tempWarn, forKey: "tempWarn") } }
    @Published var tempCrit: Int { didSet { d.set(tempCrit, forKey: "tempCrit") } }
    @Published var staleMinutes: Int { didSet { d.set(staleMinutes, forKey: "staleMinutes") } }
    @Published var lostMinutes: Int { didSet { d.set(lostMinutes, forKey: "lostMinutes") } }
    @Published var pollSeconds: Int { didSet { d.set(pollSeconds, forKey: "pollSeconds") } }
    @Published var repeatSeconds: Int { didSet { d.set(repeatSeconds, forKey: "repeatSeconds") } }
    /// «Я вне VPN»: недоступность Zabbix не эскалируется до critical
    @Published var outsideVPN: Bool { didSet { d.set(outsideVPN, forKey: "outsideVPN") } }

    var hostList: [String] {
        tempHosts.split(whereSeparator: { $0 == "," || $0 == " " }).map { String($0) }.filter { !$0.isEmpty }
    }

    private init() {
        zabbixURL = d.string(forKey: "zabbixURL") ?? "http://192.168.0.110/zabbix/api_jsonrpc.php"
        zabbixUser = d.string(forKey: "zabbixUser") ?? "Admin"
        // Для отладки в симуляторе секреты можно передать окружением
        // (xcrun simctl launch с SIMCTL_CHILD_TBC_ZBX_PASSWORD / SIMCTL_CHILD_TBC_INVITE);
        // в Keychain они при этом не пишутся.
        let env = ProcessInfo.processInfo.environment
        let kcPwd = Keychain.get("zabbixPassword")
        zabbixPassword = kcPwd.isEmpty ? (env["TBC_ZBX_PASSWORD"] ?? "") : kcPwd
        tbcBaseURL = d.string(forKey: "tbcBaseURL") ?? "https://nufarul.eminescu.md"
        let kcInv = Keychain.get("inviteHash")
        inviteHash = kcInv.isEmpty ? (env["TBC_INVITE"] ?? "") : kcInv
        tempHosts = d.string(forKey: "tempHosts") ?? "cloudbd, PROXMOX3"
        tempWarn = d.object(forKey: "tempWarn") as? Int ?? 52
        tempCrit = d.object(forKey: "tempCrit") as? Int ?? 60
        staleMinutes = d.object(forKey: "staleMinutes") as? Int ?? 5
        lostMinutes = d.object(forKey: "lostMinutes") as? Int ?? 15
        pollSeconds = d.object(forKey: "pollSeconds") as? Int ?? 30
        repeatSeconds = d.object(forKey: "repeatSeconds") as? Int ?? 20
        outsideVPN = d.bool(forKey: "outsideVPN")
    }
}
