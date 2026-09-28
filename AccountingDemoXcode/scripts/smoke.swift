import Foundation

@main
struct SmokeRunner {
    static func main() async {
        let store = SQLiteStore.shared
        let api = DbApi.shared

        do {
            try await api.bootstrap()

            await api.enqueue(.accountingDoc(
                docNo: "SMOKE-ACC-\(Int(Date().timeIntervalSince1970))",
                docDate: Date(),
                counterparty: "Smoke",
                note: "Smoke test",
                line: AccountingDocLine(lineNo: 1, debitCode: "50", creditCode: "70", amount: 11.5, lineDesc: "Smoke line")
            ))
            await api.enqueue(.productCard(sku: "SMOKE-SKU", name: "Smoke Product", barcode: "599000000999", salePrice: 19.9))
            await api.enqueue(.purchaseDoc(docNo: "SMOKE-IN-\(Int(Date().timeIntervalSince1970))", docDate: Date(), supplier: "SmokeSupplier", sku: "SMOKE-SKU", name: "Smoke Product", barcode: "599000000999", qty: 2, cost: 10, salePrice: 19.9))
            await api.enqueue(.receiptByBarcode(barcode: "599000000999", qty: 1, payType: "cash"))

            try? await Task.sleep(nanoseconds: 1_000_000_000)

            let docs = try store.loadAccountingDocs()
            let products = try store.loadProducts()
            let purchases = try store.loadPurchases()
            let receipts = try store.loadReceipts()

            print("OK")
            print("db_path=\(store.path())")
            print("docs=\(docs.count)")
            print("products=\(products.count)")
            print("purchases=\(purchases.count)")
            print("receipts=\(receipts.count)")

            let lastError = await api.lastError()
            if !lastError.isEmpty {
                print("last_error=\(lastError)")
                exit(2)
            }
        } catch {
            print("FAIL: \(error.localizedDescription)")
            exit(1)
        }
    }
}
