import Foundation
import SwiftUI

@MainActor
final class AppViewModel: ObservableObject {
    private let store = SQLiteStore.shared
    private let api = DbApi.shared

    @Published var dbPath = ""
    @Published var status = "Ready"
    @Published var lastError = ""

    @Published var accountingDocs: [AccountingDoc] = []
    @Published var accountingItems: [AccountingItem] = []
    @Published var entries: [EntryRow] = []
    @Published var selectedDocId: Int64?

    @Published var receipts: [ReceiptRow] = []
    @Published var receiptItems: [ReceiptItemRow] = []
    @Published var selectedReceiptId: Int64?

    @Published var products: [ProductRow] = []
    @Published var purchases: [PurchaseRow] = []

    @Published var docNo = "DOC-\(Int(Date().timeIntervalSince1970))"
    @Published var counterparty = "Counterparty"
    @Published var lineDesc = "Primary document line"
    @Published var debitCode = "50"
    @Published var creditCode = "70"
    @Published var amount = "100"

    @Published var cashierBarcode = "594000000001"
    @Published var cashierQty = "1"
    @Published var payType: PayType = .cash

    @Published var sku = "NEW-001"
    @Published var productName = "New Product"
    @Published var adminBarcode = "594000009999"
    @Published var salePrice = "10"
    @Published var purchaseDocNo = "IN-\(Int(Date().timeIntervalSince1970))"
    @Published var supplier = "Default Supplier"
    @Published var purchaseQty = "10"
    @Published var purchaseCost = "7"

    @Published var accountingSimCaption = "Start simulation"
    @Published var cashierSimCaption = "Start simulation"
    @Published var adminSimCaption = "Start simulation"

    private var started = false
    private var userEditing = false

    private var accountingSimTask: Task<Void, Never>?
    private var cashierSimTask: Task<Void, Never>?
    private var adminSimTask: Task<Void, Never>?

    private var accountingSimPaused = false
    private var cashierSimPaused = false
    private var adminSimPaused = false

    func bootstrap() async {
        guard !started else { return }
        started = true

        do {
            try await api.bootstrap()
            dbPath = store.path()
            await enqueueStartupSelfTests()
            try await refreshAll()
            startBackgroundRefresh()
        } catch {
            status = "Bootstrap failed"
            lastError = error.localizedDescription
        }
    }

    func setEditing(_ editing: Bool) {
        userEditing = editing
    }

    func addAccountingDoc() {
        do {
            let amt = try parsePositive(amount)
            let line = AccountingDocLine(lineNo: 1, debitCode: debitCode.trimmed, creditCode: creditCode.trimmed, amount: amt, lineDesc: lineDesc.trimmed)
            Task {
                await api.enqueue(.accountingDoc(docNo: docNo.trimmed, docDate: Date(), counterparty: counterparty.trimmed, note: "Manual document", line: line))
            }
            docNo = "DOC-\(Int(Date().timeIntervalSince1970 * 1000))"
            status = "Accounting job enqueued"
        } catch {
            lastError = error.localizedDescription
        }
    }

    func sellReceipt() {
        do {
            let qty = try parsePositive(cashierQty)
            Task {
                await api.enqueue(.receiptByBarcode(barcode: cashierBarcode.trimmed, qty: qty, payType: payType.rawValue))
            }
            status = "Cashier job enqueued"
        } catch {
            lastError = error.localizedDescription
        }
    }

    func saveCard() {
        do {
            let price = try parsePositive(salePrice)
            Task {
                await api.enqueue(.productCard(sku: sku.trimmed, name: productName.trimmed, barcode: adminBarcode.trimmed, salePrice: price))
            }
            status = "Product card job enqueued"
        } catch {
            lastError = error.localizedDescription
        }
    }

    func addPurchase() {
        do {
            let qty = try parsePositive(purchaseQty)
            let cost = try parsePositive(purchaseCost)
            let sPrice = try parsePositive(salePrice)
            Task {
                await api.enqueue(.purchaseDoc(docNo: purchaseDocNo.trimmed, docDate: Date(), supplier: supplier.trimmed, sku: sku.trimmed, name: productName.trimmed, barcode: adminBarcode.trimmed, qty: qty, cost: cost, salePrice: sPrice))
            }
            purchaseDocNo = "IN-\(Int(Date().timeIntervalSince1970 * 1000))"
            status = "Purchase job enqueued"
        } catch {
            lastError = error.localizedDescription
        }
    }

    func toggleAccountingSimulation() {
        if accountingSimTask == nil {
            startAccountingSimulation()
            return
        }
        accountingSimPaused.toggle()
        accountingSimCaption = accountingSimPaused ? "Resume simulation" : "Pause simulation"
    }

    func toggleCashierSimulation() {
        if cashierSimTask == nil {
            startCashierSimulation()
            return
        }
        cashierSimPaused.toggle()
        cashierSimCaption = cashierSimPaused ? "Resume simulation" : "Pause simulation"
    }

    func toggleAdminSimulation() {
        if adminSimTask == nil {
            startAdminSimulation()
            return
        }
        adminSimPaused.toggle()
        adminSimCaption = adminSimPaused ? "Resume simulation" : "Pause simulation"
    }

    func selectDoc(_ id: Int64?) async {
        selectedDocId = id
        guard let id else {
            accountingItems = []
            entries = []
            return
        }
        do {
            accountingItems = try store.loadAccountingItems(docId: id)
            entries = try store.loadEntries(docId: id)
        } catch {
            lastError = error.localizedDescription
        }
    }

    func selectReceipt(_ id: Int64?) async {
        selectedReceiptId = id
        guard let id else {
            receiptItems = []
            return
        }
        do {
            receiptItems = try store.loadReceiptItems(receiptId: id)
        } catch {
            lastError = error.localizedDescription
        }
    }

    private func startAccountingSimulation() {
        accountingSimPaused = false
        accountingSimCaption = "Pause simulation"

        accountingSimTask = Task {
            var n = 1
            while !Task.isCancelled {
                if accountingSimPaused {
                    try? await Task.sleep(nanoseconds: 200_000_000)
                    continue
                }

                let line = AccountingDocLine(
                    lineNo: 1,
                    debitCode: "50",
                    creditCode: "70",
                    amount: Double(Int.random(in: 50...450)),
                    lineDesc: "Line from primary doc #\(n)"
                )
                await api.enqueue(.accountingDoc(
                    docNo: "SIM-ACC-\(Int(Date().timeIntervalSince1970 * 1000))-\(n)",
                    docDate: Date(),
                    counterparty: "Client \(n)",
                    note: "Simulation",
                    line: line
                ))
                n += 1
                try? await Task.sleep(nanoseconds: 120_000_000)
            }
        }
    }

    private func startCashierSimulation() {
        cashierSimPaused = false
        cashierSimCaption = "Pause simulation"

        cashierSimTask = Task {
            while !Task.isCancelled {
                if cashierSimPaused {
                    try? await Task.sleep(nanoseconds: 200_000_000)
                    continue
                }

                let batch = Int.random(in: 2...5)
                for _ in 0..<batch {
                    let barcode = Bool.random() ? "594000000001" : "594000000002"
                    let qty = Double(Int.random(in: 1...5))
                    let pay = Bool.random() ? "cash" : "card"
                    await api.enqueue(.receiptByBarcode(barcode: barcode, qty: qty, payType: pay))
                    try? await Task.sleep(nanoseconds: 80_000_000)
                }
                try? await Task.sleep(nanoseconds: 120_000_000)
            }
        }
    }

    private func startAdminSimulation() {
        adminSimPaused = false
        adminSimCaption = "Pause simulation"

        adminSimTask = Task {
            var n = 1
            while !Task.isCancelled {
                if adminSimPaused {
                    try? await Task.sleep(nanoseconds: 200_000_000)
                    continue
                }

                let simSku = "SIM-\(String(format: "%04d", n))"
                let simName = "Sim Product \(n)"
                let simBarcode = "5948\(String(format: "%08d", Int.random(in: 0...99_999_999)))"
                let simSalePrice = Double(Int.random(in: 5...55))
                let simQty = Double(Int.random(in: 1...20))
                let simCost = Double(Int.random(in: 3...33))

                await api.enqueue(.productCard(sku: simSku, name: simName, barcode: simBarcode, salePrice: simSalePrice))
                await api.enqueue(.purchaseDoc(
                    docNo: "IN-SIM-\(Int(Date().timeIntervalSince1970 * 1000))-\(n)",
                    docDate: Date(),
                    supplier: "Supplier \(n)",
                    sku: simSku,
                    name: simName,
                    barcode: simBarcode,
                    qty: simQty,
                    cost: simCost,
                    salePrice: simSalePrice
                ))

                n += 1
                try? await Task.sleep(nanoseconds: 120_000_000)
            }
        }
    }

    private func isSimulationRunning() -> Bool {
        accountingSimTask != nil || cashierSimTask != nil || adminSimTask != nil
    }

    private func refreshAll() async throws {
        accountingDocs = try store.loadAccountingDocs()
        if selectedDocId == nil { selectedDocId = accountingDocs.first?.id }

        if let docId = selectedDocId {
            accountingItems = try store.loadAccountingItems(docId: docId)
            entries = try store.loadEntries(docId: docId)
        }

        receipts = try store.loadReceipts()
        if selectedReceiptId == nil { selectedReceiptId = receipts.first?.id }
        if let receiptId = selectedReceiptId {
            receiptItems = try store.loadReceiptItems(receiptId: receiptId)
        }

        products = try store.loadProducts()
        purchases = try store.loadPurchases()
    }

    private func startBackgroundRefresh() {
        Task {
            var seenVersion = await api.version()
            while true {
                try? await Task.sleep(nanoseconds: 300_000_000)
                let version = await api.version()
                let busy = await api.isBusy()
                let queueCount = await api.queueSize()
                let err = await api.lastError()

                if err != lastError { lastError = err }
                status = busy ? "Processing queue... (\(queueCount))" : "Ready"

                if version != seenVersion {
                    seenVersion = version
                    if userEditing && !isSimulationRunning() {
                        continue
                    }
                    do {
                        try await refreshAll()
                    } catch {
                        lastError = error.localizedDescription
                    }
                }
            }
        }
    }

    private func enqueueStartupSelfTests() async {
        let stamp = Int(Date().timeIntervalSince1970)
        await api.enqueue(.accountingDoc(
            docNo: "SELF-ACC-\(stamp)",
            docDate: Date(),
            counterparty: "SelfTest",
            note: "Startup selftest",
            line: AccountingDocLine(lineNo: 1, debitCode: "50", creditCode: "70", amount: 1, lineDesc: "Selftest line")
        ))
        await api.enqueue(.receiptByBarcode(barcode: "594000000001", qty: 1, payType: "cash"))
        await api.enqueue(.productCard(sku: "SELF-\(stamp)", name: "Self Product", barcode: "596\(stamp)", salePrice: 1))
        await api.enqueue(.purchaseDoc(docNo: "SELF-IN-\(stamp)", docDate: Date(), supplier: "SelfSupplier", sku: "SELF-PUR-\(stamp)", name: "Self Purchase Product", barcode: "597\(stamp)", qty: 1, cost: 2, salePrice: 3))
    }

    private func parsePositive(_ value: String) throws -> Double {
        let normalized = value.trimmed.replacingOccurrences(of: ",", with: ".")
        guard let number = Double(normalized), number > 0 else {
            throw StoreError.message("Invalid numeric value: \(value)")
        }
        return number
    }
}

private extension String {
    var trimmed: String { trimmingCharacters(in: .whitespacesAndNewlines) }
}
