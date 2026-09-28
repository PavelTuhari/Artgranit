import Foundation
import SQLite3

private let SQLITE_TRANSIENT = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

enum StoreError: LocalizedError {
    case message(String)

    var errorDescription: String? {
        switch self {
        case .message(let text): return text
        }
    }
}

final class SQLiteStore {
    static let shared = SQLiteStore()

    private let dbPath: String
    private let dateFormatter: DateFormatter
    private let dateTimeFormatter: DateFormatter
    private let lockRetryCount = 40
    private let lockRetryDelay: TimeInterval = 0.025

    private init() {
        let baseDir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
            .appendingPathComponent("AccountingDemoXcode", isDirectory: true)
        try? FileManager.default.createDirectory(at: baseDir, withIntermediateDirectories: true)
        dbPath = baseDir.appendingPathComponent("bookkeeping_demo.db").path

        dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"

        dateTimeFormatter = DateFormatter()
        dateTimeFormatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
    }

    func path() -> String { dbPath }

    func bootstrap() throws {
        let db = try open()
        defer { sqlite3_close(db) }

        // Best-effort: if another process temporarily holds the file, do not fail bootstrap here.
        try? exec(db, "PRAGMA journal_mode = WAL")
        try exec(db, "PRAGMA foreign_keys = ON")
        try exec(db, "PRAGMA busy_timeout = 5000")

        try ensureSchema(db)
        try ensureSeeds(db)
    }

    func insertAccountingDocument(docNo: String, docDate: Date, counterparty: String, note: String, line: AccountingDocLine) throws {
        let db = try open()
        defer { sqlite3_close(db) }

        try begin(db)
        do {
            let docDateStr = dateFormatter.string(from: docDate)
            try run(db,
                "INSERT INTO accounting_docs(doc_no, doc_date, doc_type, counterparty, note) VALUES (?, ?, 'GENERAL', ?, ?)",
                binds: [.text(docNo), .text(docDateStr), .text(counterparty), .text(note)]
            )
            let docId = sqlite3_last_insert_rowid(db)

            let debitId = try accountIdByCode(db, code: line.debitCode)
            let creditId = try accountIdByCode(db, code: line.creditCode)

            try run(db,
                "INSERT INTO accounting_doc_items(doc_id, line_no, debit_code, credit_code, amount, line_desc) VALUES (?, ?, ?, ?, ?, ?)",
                binds: [.int64(docId), .int(line.lineNo), .text(line.debitCode), .text(line.creditCode), .double(line.amount), .text(line.lineDesc)]
            )
            let itemId = sqlite3_last_insert_rowid(db)

            try run(db,
                "INSERT INTO entries(doc_date, description, debit_account_id, credit_account_id, amount, doc_id, doc_item_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                binds: [.text(docDateStr), .text(line.lineDesc), .int64(debitId), .int64(creditId), .double(line.amount), .int64(docId), .int64(itemId)]
            )

            try commit(db)
        } catch {
            _ = rollback(db)
            throw error
        }
    }

    func insertProduct(sku: String, name: String, barcode: String, salePrice: Double) throws {
        let db = try open()
        defer { sqlite3_close(db) }

        try begin(db)
        do {
            try run(db, "INSERT INTO products(sku, name, is_active) VALUES (?, ?, 1)", binds: [.text(sku), .text(name)])
            let productId = sqlite3_last_insert_rowid(db)

            try run(db, "INSERT INTO product_barcodes(product_id, barcode, is_active) VALUES (?, ?, 1)", binds: [.int64(productId), .text(barcode)])
            try run(db, "INSERT INTO price_list(product_id, price, valid_from, is_active) VALUES (?, ?, ?, 1)", binds: [.int64(productId), .double(salePrice), .text(dateFormatter.string(from: Date()))])

            try commit(db)
        } catch {
            _ = rollback(db)
            throw error
        }
    }

    func insertPurchase(docNo: String, docDate: Date, supplier: String, sku: String, name: String, barcode: String, qty: Double, cost: Double, salePrice: Double) throws {
        let db = try open()
        defer { sqlite3_close(db) }

        if qty <= 0 || cost <= 0 {
            throw StoreError.message("Qty and cost must be > 0")
        }

        try begin(db)
        do {
            let existingByBarcode = try productIdByBarcode(db, barcode: barcode)
            let existingBySku = try productIdBySKU(db, sku: sku)
            let productId: Int64

            if let pid = existingByBarcode ?? existingBySku {
                productId = pid
                try run(db, "UPDATE products SET sku = ?, name = ?, is_active = 1 WHERE id = ?", binds: [.text(sku), .text(name), .int64(productId)])
            } else {
                try run(db, "INSERT INTO products(sku, name, is_active) VALUES (?, ?, 1)", binds: [.text(sku), .text(name)])
                productId = sqlite3_last_insert_rowid(db)
            }

            if existingByBarcode == nil {
                try run(db, "INSERT OR IGNORE INTO product_barcodes(product_id, barcode, is_active) VALUES (?, ?, 1)", binds: [.int64(productId), .text(barcode)])
            }

            if salePrice > 0 {
                try run(db, "UPDATE price_list SET is_active = 0 WHERE product_id = ?", binds: [.int64(productId)])
                try run(db, "INSERT INTO price_list(product_id, price, valid_from, is_active) VALUES (?, ?, ?, 1)", binds: [.int64(productId), .double(salePrice), .text(dateFormatter.string(from: docDate))])
            }

            try run(db, "INSERT INTO purchase_docs(doc_no, doc_date, supplier, note) VALUES (?, ?, ?, '')", binds: [.text(docNo), .text(dateFormatter.string(from: docDate)), .text(supplier)])
            let docId = sqlite3_last_insert_rowid(db)
            try run(db, "INSERT INTO purchase_doc_items(doc_id, product_id, qty, cost, line_total) VALUES (?, ?, ?, ?, ?)", binds: [.int64(docId), .int64(productId), .double(qty), .double(cost), .double(qty * cost)])

            try commit(db)
        } catch {
            _ = rollback(db)
            throw error
        }
    }

    func insertReceiptByBarcode(barcode: String, qty: Double, payType: String) throws {
        let db = try open()
        defer { sqlite3_close(db) }

        let lookupSQL = """
        SELECT p.id, p.name,
               COALESCE((SELECT pl.price FROM price_list pl WHERE pl.product_id = p.id AND pl.is_active = 1 ORDER BY pl.id DESC LIMIT 1), 0) AS price
        FROM product_barcodes b
        JOIN products p ON p.id = b.product_id
        WHERE b.barcode = ? AND b.is_active = 1 AND p.is_active = 1
        LIMIT 1
        """

        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, lookupSQL, -1, &stmt, nil) == SQLITE_OK else {
            throw StoreError.message(lastError(db))
        }
        defer { sqlite3_finalize(stmt) }

        sqlite3_bind_text(stmt, 1, barcode, -1, SQLITE_TRANSIENT)

        guard sqlite3_step(stmt) == SQLITE_ROW else {
            throw StoreError.message("Barcode not found: \(barcode)")
        }

        let productId = sqlite3_column_int64(stmt, 0)
        let productName = String(cString: sqlite3_column_text(stmt, 1))
        let price = sqlite3_column_double(stmt, 2)
        let total = price * qty
        let receiptNo = String(Int(Date().timeIntervalSince1970 * 1000))

        try begin(db)
        do {
            try run(db, "INSERT INTO sales_receipts(receipt_no, created_at, total_amount, pay_type) VALUES (?, ?, ?, ?)", binds: [.text(receiptNo), .text(dateTimeFormatter.string(from: Date())), .double(total), .text(payType)])
            let rid = sqlite3_last_insert_rowid(db)
            try run(db, "INSERT INTO sales_receipt_items(receipt_id, product_id, product_name, barcode, qty, price, line_total) VALUES (?, ?, ?, ?, ?, ?, ?)", binds: [.int64(rid), .int64(productId), .text(productName), .text(barcode), .double(qty), .double(price), .double(total)])
            try commit(db)
        } catch {
            _ = rollback(db)
            throw error
        }
    }

    func loadAccountingDocs() throws -> [AccountingDoc] {
        let db = try open()
        defer { sqlite3_close(db) }

        let sql = "SELECT id, doc_no, doc_date, COALESCE(counterparty, ''), COALESCE(note, '') FROM accounting_docs ORDER BY id DESC LIMIT 300"
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw StoreError.message(lastError(db))
        }
        defer { sqlite3_finalize(stmt) }

        var rows: [AccountingDoc] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            rows.append(AccountingDoc(
                id: sqlite3_column_int64(stmt, 0),
                docNo: string(stmt, col: 1),
                docDate: string(stmt, col: 2),
                counterparty: string(stmt, col: 3),
                note: string(stmt, col: 4)
            ))
        }
        return rows
    }

    func loadAccountingItems(docId: Int64) throws -> [AccountingItem] {
        let db = try open()
        defer { sqlite3_close(db) }

        let sql = "SELECT id, line_no, debit_code, credit_code, amount, COALESCE(line_desc, '') FROM accounting_doc_items WHERE doc_id = ? ORDER BY line_no"
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw StoreError.message(lastError(db))
        }
        defer { sqlite3_finalize(stmt) }

        sqlite3_bind_int64(stmt, 1, docId)

        var rows: [AccountingItem] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            rows.append(AccountingItem(
                id: sqlite3_column_int64(stmt, 0),
                lineNo: Int(sqlite3_column_int(stmt, 1)),
                debitCode: string(stmt, col: 2),
                creditCode: string(stmt, col: 3),
                amount: sqlite3_column_double(stmt, 4),
                lineDesc: string(stmt, col: 5)
            ))
        }
        return rows
    }

    func loadEntries(docId: Int64) throws -> [EntryRow] {
        let db = try open()
        defer { sqlite3_close(db) }

        let sql = """
        SELECT e.id, e.doc_date, e.description,
               COALESCE(a1.code, ''), COALESCE(a2.code, ''), e.amount
        FROM entries e
        LEFT JOIN accounts a1 ON a1.id = e.debit_account_id
        LEFT JOIN accounts a2 ON a2.id = e.credit_account_id
        WHERE e.doc_id = ?
        ORDER BY e.id
        """

        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw StoreError.message(lastError(db))
        }
        defer { sqlite3_finalize(stmt) }

        sqlite3_bind_int64(stmt, 1, docId)

        var rows: [EntryRow] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            rows.append(EntryRow(
                id: sqlite3_column_int64(stmt, 0),
                docDate: string(stmt, col: 1),
                description: string(stmt, col: 2),
                debit: string(stmt, col: 3),
                credit: string(stmt, col: 4),
                amount: sqlite3_column_double(stmt, 5)
            ))
        }
        return rows
    }

    func loadProducts() throws -> [ProductRow] {
        let db = try open()
        defer { sqlite3_close(db) }

        let sql = """
        SELECT p.id, COALESCE(p.sku, ''), p.name, COALESCE(b.barcode, ''),
               COALESCE((SELECT pl.price FROM price_list pl WHERE pl.product_id = p.id AND pl.is_active = 1 ORDER BY pl.id DESC LIMIT 1),0)
        FROM products p
        LEFT JOIN product_barcodes b ON b.product_id = p.id AND b.is_active = 1
        ORDER BY p.id DESC
        LIMIT 300
        """

        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw StoreError.message(lastError(db))
        }
        defer { sqlite3_finalize(stmt) }

        var rows: [ProductRow] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            rows.append(ProductRow(
                id: sqlite3_column_int64(stmt, 0),
                sku: string(stmt, col: 1),
                name: string(stmt, col: 2),
                barcode: string(stmt, col: 3),
                salePrice: sqlite3_column_double(stmt, 4)
            ))
        }
        return rows
    }

    func loadPurchases() throws -> [PurchaseRow] {
        let db = try open()
        defer { sqlite3_close(db) }

        let sql = """
        SELECT d.id, d.doc_no, d.doc_date, COALESCE(d.supplier, ''), COALESCE(p.sku, ''), p.name,
               i.qty, i.cost, i.line_total
        FROM purchase_docs d
        JOIN purchase_doc_items i ON i.doc_id = d.id
        JOIN products p ON p.id = i.product_id
        ORDER BY d.id DESC
        LIMIT 300
        """

        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw StoreError.message(lastError(db))
        }
        defer { sqlite3_finalize(stmt) }

        var rows: [PurchaseRow] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            rows.append(PurchaseRow(
                id: sqlite3_column_int64(stmt, 0),
                docNo: string(stmt, col: 1),
                docDate: string(stmt, col: 2),
                supplier: string(stmt, col: 3),
                sku: string(stmt, col: 4),
                productName: string(stmt, col: 5),
                qty: sqlite3_column_double(stmt, 6),
                cost: sqlite3_column_double(stmt, 7),
                lineTotal: sqlite3_column_double(stmt, 8)
            ))
        }
        return rows
    }

    func loadReceipts() throws -> [ReceiptRow] {
        let db = try open()
        defer { sqlite3_close(db) }

        let sql = "SELECT id, receipt_no, created_at, total_amount, pay_type FROM sales_receipts ORDER BY id DESC LIMIT 250"
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw StoreError.message(lastError(db))
        }
        defer { sqlite3_finalize(stmt) }

        var rows: [ReceiptRow] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            rows.append(ReceiptRow(
                id: sqlite3_column_int64(stmt, 0),
                receiptNo: string(stmt, col: 1),
                createdAt: string(stmt, col: 2),
                totalAmount: sqlite3_column_double(stmt, 3),
                payType: string(stmt, col: 4)
            ))
        }
        return rows
    }

    func loadReceiptItems(receiptId: Int64) throws -> [ReceiptItemRow] {
        let db = try open()
        defer { sqlite3_close(db) }

        let sql = "SELECT id, product_name, COALESCE(barcode, ''), qty, price, line_total FROM sales_receipt_items WHERE receipt_id = ? ORDER BY id"
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw StoreError.message(lastError(db))
        }
        defer { sqlite3_finalize(stmt) }

        sqlite3_bind_int64(stmt, 1, receiptId)

        var rows: [ReceiptItemRow] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            rows.append(ReceiptItemRow(
                id: sqlite3_column_int64(stmt, 0),
                productName: string(stmt, col: 1),
                barcode: string(stmt, col: 2),
                qty: sqlite3_column_double(stmt, 3),
                price: sqlite3_column_double(stmt, 4),
                lineTotal: sqlite3_column_double(stmt, 5)
            ))
        }
        return rows
    }

    private func ensureSchema(_ db: OpaquePointer?) throws {
        try exec(db, "CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, account_type TEXT NOT NULL)")
        try exec(db, "CREATE TABLE IF NOT EXISTS accounting_docs (id INTEGER PRIMARY KEY AUTOINCREMENT, doc_no TEXT NOT NULL UNIQUE, doc_date TEXT NOT NULL, doc_type TEXT NOT NULL, counterparty TEXT, note TEXT)")
        try exec(db, "CREATE TABLE IF NOT EXISTS accounting_doc_items (id INTEGER PRIMARY KEY AUTOINCREMENT, doc_id INTEGER NOT NULL, line_no INTEGER NOT NULL, debit_code TEXT NOT NULL, credit_code TEXT NOT NULL, amount NUMERIC NOT NULL, line_desc TEXT, FOREIGN KEY (doc_id) REFERENCES accounting_docs(id))")
        try exec(db, "CREATE TABLE IF NOT EXISTS entries (id INTEGER PRIMARY KEY AUTOINCREMENT, doc_date TEXT NOT NULL, description TEXT NOT NULL, debit_account_id INTEGER NOT NULL, credit_account_id INTEGER NOT NULL, amount NUMERIC NOT NULL, doc_id INTEGER, doc_item_id INTEGER, FOREIGN KEY (debit_account_id) REFERENCES accounts(id), FOREIGN KEY (credit_account_id) REFERENCES accounts(id))")

        try exec(db, "CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, name TEXT NOT NULL, is_active INTEGER NOT NULL DEFAULT 1)")
        try exec(db, "CREATE TABLE IF NOT EXISTS product_barcodes (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, barcode TEXT NOT NULL UNIQUE, is_active INTEGER NOT NULL DEFAULT 1, FOREIGN KEY (product_id) REFERENCES products(id))")
        try exec(db, "CREATE TABLE IF NOT EXISTS price_list (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, price NUMERIC NOT NULL, valid_from TEXT NOT NULL, is_active INTEGER NOT NULL DEFAULT 1, FOREIGN KEY (product_id) REFERENCES products(id))")

        try exec(db, "CREATE TABLE IF NOT EXISTS purchase_docs (id INTEGER PRIMARY KEY AUTOINCREMENT, doc_no TEXT NOT NULL UNIQUE, doc_date TEXT NOT NULL, supplier TEXT, note TEXT)")
        try exec(db, "CREATE TABLE IF NOT EXISTS purchase_doc_items (id INTEGER PRIMARY KEY AUTOINCREMENT, doc_id INTEGER NOT NULL, product_id INTEGER NOT NULL, qty NUMERIC NOT NULL, cost NUMERIC NOT NULL, line_total NUMERIC NOT NULL, FOREIGN KEY (doc_id) REFERENCES purchase_docs(id), FOREIGN KEY (product_id) REFERENCES products(id))")

        try exec(db, "CREATE TABLE IF NOT EXISTS sales_receipts (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, total_amount NUMERIC NOT NULL, pay_type TEXT NOT NULL)")
        try exec(db, "CREATE TABLE IF NOT EXISTS sales_receipt_items (id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_id INTEGER NOT NULL, product_id INTEGER NOT NULL, product_name TEXT NOT NULL, barcode TEXT, qty NUMERIC NOT NULL, price NUMERIC NOT NULL, line_total NUMERIC NOT NULL, FOREIGN KEY (receipt_id) REFERENCES sales_receipts(id))")
    }

    private func ensureSeeds(_ db: OpaquePointer?) throws {
        let accountCount = try scalarCount(db, sql: "SELECT COUNT(*) FROM accounts")
        if accountCount == 0 {
            try exec(db, "INSERT INTO accounts(code, name, account_type) VALUES ('10', 'Materials', 'Active')")
            try exec(db, "INSERT INTO accounts(code, name, account_type) VALUES ('50', 'Cash', 'Active')")
            try exec(db, "INSERT INTO accounts(code, name, account_type) VALUES ('60', 'Payables', 'Passive')")
            try exec(db, "INSERT INTO accounts(code, name, account_type) VALUES ('62', 'Receivables', 'Active')")
            try exec(db, "INSERT INTO accounts(code, name, account_type) VALUES ('70', 'Payroll', 'Passive')")
            try exec(db, "INSERT INTO accounts(code, name, account_type) VALUES ('90', 'Sales', 'Passive')")
        }

        let productCount = try scalarCount(db, sql: "SELECT COUNT(*) FROM products")
        if productCount == 0 {
            try begin(db)
            do {
                try run(db, "INSERT INTO products(sku, name, is_active) VALUES ('WATER-05', 'Water 0.5L', 1)", binds: [])
                let p1 = sqlite3_last_insert_rowid(db)
                try run(db, "INSERT INTO product_barcodes(product_id, barcode, is_active) VALUES (?, '594000000001', 1)", binds: [.int64(p1)])
                try run(db, "INSERT INTO price_list(product_id, price, valid_from, is_active) VALUES (?, 12.00, ?, 1)", binds: [.int64(p1), .text(dateFormatter.string(from: Date()))])

                try run(db, "INSERT INTO products(sku, name, is_active) VALUES ('COF-ESP', 'Coffee Espresso', 1)", binds: [])
                let p2 = sqlite3_last_insert_rowid(db)
                try run(db, "INSERT INTO product_barcodes(product_id, barcode, is_active) VALUES (?, '594000000002', 1)", binds: [.int64(p2)])
                try run(db, "INSERT INTO price_list(product_id, price, valid_from, is_active) VALUES (?, 35.00, ?, 1)", binds: [.int64(p2), .text(dateFormatter.string(from: Date()))])

                try commit(db)
            } catch {
                _ = rollback(db)
                throw error
            }
        }
    }

    private func accountIdByCode(_ db: OpaquePointer?, code: String) throws -> Int64 {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, "SELECT id FROM accounts WHERE code = ?", -1, &stmt, nil) == SQLITE_OK else {
            throw StoreError.message(lastError(db))
        }
        defer { sqlite3_finalize(stmt) }

        sqlite3_bind_text(stmt, 1, code, -1, SQLITE_TRANSIENT)
        if sqlite3_step(stmt) == SQLITE_ROW {
            return sqlite3_column_int64(stmt, 0)
        }
        throw StoreError.message("Account not found: \(code)")
    }

    private func productIdByBarcode(_ db: OpaquePointer?, barcode: String) throws -> Int64? {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, "SELECT product_id FROM product_barcodes WHERE barcode = ? LIMIT 1", -1, &stmt, nil) == SQLITE_OK else {
            throw StoreError.message(lastError(db))
        }
        defer { sqlite3_finalize(stmt) }

        sqlite3_bind_text(stmt, 1, barcode, -1, SQLITE_TRANSIENT)
        if sqlite3_step(stmt) == SQLITE_ROW {
            return sqlite3_column_int64(stmt, 0)
        }
        return nil
    }

    private func productIdBySKU(_ db: OpaquePointer?, sku: String) throws -> Int64? {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, "SELECT id FROM products WHERE sku = ? LIMIT 1", -1, &stmt, nil) == SQLITE_OK else {
            throw StoreError.message(lastError(db))
        }
        defer { sqlite3_finalize(stmt) }

        sqlite3_bind_text(stmt, 1, sku, -1, SQLITE_TRANSIENT)
        if sqlite3_step(stmt) == SQLITE_ROW {
            return sqlite3_column_int64(stmt, 0)
        }
        return nil
    }

    private func scalarCount(_ db: OpaquePointer?, sql: String) throws -> Int {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw StoreError.message(lastError(db))
        }
        defer { sqlite3_finalize(stmt) }

        guard sqlite3_step(stmt) == SQLITE_ROW else {
            return 0
        }
        return Int(sqlite3_column_int(stmt, 0))
    }

    private func open() throws -> OpaquePointer? {
        var db: OpaquePointer?
        if sqlite3_open(dbPath, &db) != SQLITE_OK {
            defer { sqlite3_close(db) }
            throw StoreError.message(lastError(db))
        }
        sqlite3_busy_timeout(db, 7000)
        _ = sqlite3_exec(db, "PRAGMA foreign_keys = ON", nil, nil, nil)
        return db
    }

    private func begin(_ db: OpaquePointer?) throws {
        try exec(db, "BEGIN IMMEDIATE TRANSACTION")
    }

    private func commit(_ db: OpaquePointer?) throws {
        try exec(db, "COMMIT")
    }

    @discardableResult
    private func rollback(_ db: OpaquePointer?) -> Bool {
        sqlite3_exec(db, "ROLLBACK", nil, nil, nil) == SQLITE_OK
    }

    private func exec(_ db: OpaquePointer?, _ sql: String) throws {
        for _ in 0..<lockRetryCount {
            var err: UnsafeMutablePointer<Int8>?
            if sqlite3_exec(db, sql, nil, nil, &err) == SQLITE_OK {
                return
            }

            let message = err.map { String(cString: $0) } ?? lastError(db)
            sqlite3_free(err)
            if isLockError(message) {
                Thread.sleep(forTimeInterval: lockRetryDelay)
                continue
            }
            throw StoreError.message(message)
        }
        throw StoreError.message("database is locked")
    }

    private func run(_ db: OpaquePointer?, _ sql: String, binds: [Bind]) throws {
        for _ in 0..<lockRetryCount {
            var stmt: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
                let message = lastError(db)
                if isLockError(message) {
                    Thread.sleep(forTimeInterval: lockRetryDelay)
                    continue
                }
                throw StoreError.message(message)
            }
            defer { sqlite3_finalize(stmt) }

            for (idx, bind) in binds.enumerated() {
                let i = Int32(idx + 1)
                switch bind {
                case .text(let value): sqlite3_bind_text(stmt, i, value, -1, SQLITE_TRANSIENT)
                case .double(let value): sqlite3_bind_double(stmt, i, value)
                case .int(let value): sqlite3_bind_int(stmt, i, Int32(value))
                case .int64(let value): sqlite3_bind_int64(stmt, i, value)
                }
            }

            if sqlite3_step(stmt) == SQLITE_DONE {
                return
            }

            let message = lastError(db)
            if isLockError(message) {
                Thread.sleep(forTimeInterval: lockRetryDelay)
                continue
            }
            throw StoreError.message(message)
        }
        throw StoreError.message("database is locked")
    }

    private func lastError(_ db: OpaquePointer?) -> String {
        String(cString: sqlite3_errmsg(db))
    }

    private func isLockError(_ message: String) -> Bool {
        let lower = message.lowercased()
        return lower.contains("database is locked")
            || lower.contains("database table is locked")
            || lower.contains("busy")
            || lower.contains("locked")
    }

    private func string(_ stmt: OpaquePointer?, col: Int32) -> String {
        guard let c = sqlite3_column_text(stmt, col) else { return "" }
        return String(cString: c)
    }
}

private enum Bind {
    case text(String)
    case double(Double)
    case int(Int)
    case int64(Int64)
}
