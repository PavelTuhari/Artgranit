import Foundation

/// Клиент Zabbix 3.4 JSON-RPC (ТЗ §2). Только чтение.
struct ZabbixClient {
    let url: URL
    let user: String
    let password: String

    struct Snapshot {
        var problems: [ZProblem] = []
        var temps: [HostTemps] = []
        var latencyMs: Int = 0
    }

    enum ZError: LocalizedError {
        case api(String), transport(String), badURL
        var errorDescription: String? {
            switch self {
            case .api(let s): return "Zabbix: \(s)"
            case .transport(let s): return "Сеть: \(s)"
            case .badURL: return "Некорректный адрес Zabbix"
            }
        }
    }

    private func rpc(_ method: String, _ params: Any, auth: String?) async throws -> Any {
        var body: [String: Any] = ["jsonrpc": "2.0", "method": method, "params": params, "id": 1]
        if let a = auth { body["auth"] = a }
        var req = URLRequest(url: url, timeoutInterval: 12)
        req.httpMethod = "POST"
        req.setValue("application/json-rpc", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, resp): (Data, URLResponse)
        do { (data, resp) = try await URLSession.shared.data(for: req) }
        catch { throw ZError.transport(error.localizedDescription) }
        guard let http = resp as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw ZError.transport("HTTP \((resp as? HTTPURLResponse)?.statusCode ?? 0)")
        }
        guard let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw ZError.api("не JSON")
        }
        if let err = obj["error"] as? [String: Any] {
            throw ZError.api((err["data"] as? String) ?? (err["message"] as? String) ?? "ошибка API")
        }
        return obj["result"] ?? NSNull()
    }

    func fetch(hosts: [String]) async throws -> Snapshot {
        let t0 = Date()
        // 3.4 принимает только `user`; в новых версиях — `username`
        var token: String
        do {
            token = try await rpc("user.login", ["user": user, "password": password], auth: nil) as? String ?? ""
        } catch ZError.api(let msg) where msg.lowercased().contains("parameter") {
            token = try await rpc("user.login", ["username": user, "password": password], auth: nil) as? String ?? ""
        }
        var snap = Snapshot()

        // Активные проблемы
        let trg = try await rpc("trigger.get", [
            "output": ["triggerid", "description", "priority", "lastchange"],
            "filter": ["value": 1], "only_true": 1, "monitored": 1, "skipDependent": 1,
            "expandDescription": 1, "selectHosts": ["host"],
            "sortfield": "priority", "sortorder": "DESC"
        ], auth: token) as? [[String: Any]] ?? []
        snap.problems = trg.map { t in
            let hosts = (t["selectHosts"] as? [[String: Any]]) ?? (t["hosts"] as? [[String: Any]]) ?? []
            let lc = Double(t["lastchange"] as? String ?? "") ?? 0
            return ZProblem(id: t["triggerid"] as? String ?? UUID().uuidString,
                            name: t["description"] as? String ?? "",
                            priority: Int(t["priority"] as? String ?? "0") ?? 0,
                            host: hosts.first?["host"] as? String ?? "",
                            lastChange: lc > 0 ? Date(timeIntervalSince1970: lc) : nil)
        }

        // Температура, uptime, доступность агента по нужным хостам
        if !hosts.isEmpty {
            let hs = try await rpc("host.get", ["filter": ["host": hosts],
                                                "output": ["hostid", "host", "available"]], auth: token) as? [[String: Any]] ?? []
            for h in hs {
                guard let hid = h["hostid"] as? String, let name = h["host"] as? String else { continue }
                var ht = HostTemps(host: name, updated: Date())
                if let av = h["available"] as? String { ht.agentAvailable = av == "1" ? true : (av == "2" ? false : nil) }
                let items = try await rpc("item.get", ["hostids": hid, "output": ["key_", "lastvalue"],
                                                       "search": ["key_": "cpu.temp"], "searchByAny": 1],
                                          auth: token) as? [[String: Any]] ?? []
                for it in items {
                    let key = it["key_"] as? String ?? ""
                    let v = Int(Double(it["lastvalue"] as? String ?? "") ?? -1)
                    if key == "cpu.temp[1]" { ht.cpu1 = v >= 0 ? v : nil }
                    if key == "cpu.temp[2]" { ht.cpu2 = v >= 0 ? v : nil }
                }
                let up = try await rpc("item.get", ["hostids": hid, "output": ["lastvalue"],
                                                    "search": ["key_": "system.uptime"]], auth: token) as? [[String: Any]] ?? []
                if let s = up.first?["lastvalue"] as? String, let n = Double(s) { ht.uptimeSec = Int(n) }
                snap.temps.append(ht)
            }
            // хосты, которых нет в Zabbix, всё равно показываем как «нет данных»
            for name in hosts where !snap.temps.contains(where: { $0.host == name }) {
                snap.temps.append(HostTemps(host: name, updated: Date()))
            }
        }
        snap.latencyMs = Int(Date().timeIntervalSince(t0) * 1000)
        return snap
    }
}
