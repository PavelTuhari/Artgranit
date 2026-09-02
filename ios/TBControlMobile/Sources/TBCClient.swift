import Foundation

/// Клиент TBControl (nufarul): вход по хэш-инвайту, далее cookie-сессия (ТЗ §2).
struct TBCClient {
    let base: URL
    let inviteHash: String

    struct Snapshot {
        var stats = TBCStats()
        var events: [TBCEvent] = []
        var cassa = CassaSummary()
        var latencyMs = 0
    }

    enum TError: LocalizedError {
        case auth, transport(String), api(String)
        var errorDescription: String? {
            switch self {
            case .auth: return "TBControl: инвайт не принят (проверьте хэш)"
            case .transport(let s): return "Сеть: \(s)"
            case .api(let s): return "TBControl: \(s)"
            }
        }
    }

    private var session: URLSession {
        let c = URLSessionConfiguration.default
        c.httpCookieStorage = HTTPCookieStorage.shared
        c.timeoutIntervalForRequest = 15
        return URLSession(configuration: c)
    }

    private func getJSON(_ path: String) async throws -> [String: Any] {
        let url = URL(string: base.absoluteString.trimmingCharacters(in: CharacterSet(charactersIn: "/")) + path)!
        let (data, resp): (Data, URLResponse)
        do { (data, resp) = try await session.data(from: url) }
        catch { throw TError.transport(error.localizedDescription) }
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw code == 200 ? TError.api("не JSON") : TError.transport("HTTP \(code)")
        }
        if obj["success"] as? Bool == false {
            let e = obj["error"] as? String ?? "ошибка"
            throw e.contains("авториз") ? TError.auth : TError.api(e)
        }
        return obj
    }

    /// GET /UNA.md/orasldev/tbcontrol?h=<hash> — сервер логинит сессию и ставит cookie.
    private func login() async throws {
        guard !inviteHash.isEmpty else { throw TError.auth }
        let url = URL(string: base.absoluteString.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
                      + "/UNA.md/orasldev/tbcontrol?h=" + inviteHash)!
        do { _ = try await session.data(from: url) }
        catch { throw TError.transport(error.localizedDescription) }
    }

    func fetch() async throws -> Snapshot {
        let t0 = Date()
        var stats: [String: Any]
        do { stats = try await getJSON("/api/tbc/stats") }
        catch TError.auth { try await login(); stats = try await getJSON("/api/tbc/stats") }
        var snap = Snapshot()
        snap.stats = TBCStats(json: stats["data"] as? [String: Any] ?? [:])

        let ev = try await getJSON("/api/tbc/events?status=open&limit=50")
        snap.events = (ev["data"] as? [[String: Any]] ?? []).map { e in
            TBCEvent(id: (e["id"] as? NSNumber)?.intValue ?? 0,
                     problem: e["problem"] as? String ?? "",
                     severity: e["severity"] as? String ?? "",
                     source: e["source"] as? String ?? "",
                     status: e["status"] as? String ?? "",
                     createdAt: e["created_at"] as? String ?? "")
        }

        if let cs = try? await getJSON("/api/tbc/cassa"), let d = cs["data"] as? [String: Any] {
            func i(_ x: [String: Any], _ k: String) -> Int { (x[k] as? NSNumber)?.intValue ?? 0 }
            let st = d["stats"] as? [String: Any] ?? [:]
            var c = CassaSummary()
            c.storesTotal = i(st, "stores_total"); c.storesOnline = i(st, "stores_online"); c.storesOffline = i(st, "stores_offline")
            c.regTotal = i(st, "reg_total"); c.regOnline = i(st, "reg_online"); c.regOffline = i(st, "reg_offline")
            c.checkedAt = st["checked_at"] as? String ?? ""
            c.stores = (d["stores"] as? [[String: Any]] ?? []).map { s in
                CassaStore(codUniv: "\(s["cod_univ"] ?? "")",
                           name: (s["store_name"] as? String) ?? (s["name"] as? String) ?? "Магазин \(s["cod_univ"] ?? "")",
                           regTotal: i(s, "reg_total"), regOnline: i(s, "reg_online"),
                           regOffline: i(s, "reg_offline"), regShutdown: i(s, "reg_shutdown"))
            }
            snap.cassa = c
        }
        snap.latencyMs = Int(Date().timeIntervalSince(t0) * 1000)
        return snap
    }
}
