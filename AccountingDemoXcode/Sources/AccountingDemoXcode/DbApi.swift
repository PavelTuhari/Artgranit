import Foundation

actor DbApi {
    static let shared = DbApi(store: .shared)

    private let store: SQLiteStore
    private var queue: [DbJob] = []
    private var processing = false
    private var versionValue: Int64 = 0
    private var lastErrorValue = ""

    init(store: SQLiteStore) {
        self.store = store
    }

    func bootstrap() throws {
        try store.bootstrap()
    }

    func enqueue(_ job: DbJob) {
        queue.append(job)
        if !processing {
            processing = true
            Task { await self.processLoop() }
        }
    }

    func version() -> Int64 { versionValue }
    func lastError() -> String { lastErrorValue }
    func isBusy() -> Bool { processing || !queue.isEmpty }
    func queueSize() -> Int { queue.count }

    private func processLoop() async {
        while !queue.isEmpty {
            let job = queue.removeFirst()
            do {
                try executeWithRetry(job)
                versionValue += 1
                lastErrorValue = ""
            } catch {
                lastErrorValue = error.localizedDescription
            }
        }
        processing = false
    }

    private func executeWithRetry(_ job: DbJob) throws {
        for attempt in 1...25 {
            do {
                try execute(job)
                return
            } catch {
                let message = error.localizedDescription.lowercased()
                let isLocked = message.contains("locked") || message.contains("busy")
                if isLocked && attempt < 25 {
                    Thread.sleep(forTimeInterval: Double(attempt) * 0.015)
                    continue
                }
                throw error
            }
        }
    }

    private func execute(_ job: DbJob) throws {
        switch job {
        case .accountingDoc(let docNo, let docDate, let counterparty, let note, let line):
            try store.insertAccountingDocument(docNo: docNo, docDate: docDate, counterparty: counterparty, note: note, line: line)
        case .receiptByBarcode(let barcode, let qty, let payType):
            try store.insertReceiptByBarcode(barcode: barcode, qty: qty, payType: payType)
        case .productCard(let sku, let name, let barcode, let salePrice):
            try store.insertProduct(sku: sku, name: name, barcode: barcode, salePrice: salePrice)
        case .purchaseDoc(let docNo, let docDate, let supplier, let sku, let name, let barcode, let qty, let cost, let salePrice):
            try store.insertPurchase(docNo: docNo, docDate: docDate, supplier: supplier, sku: sku, name: name, barcode: barcode, qty: qty, cost: cost, salePrice: salePrice)
        }
    }
}
