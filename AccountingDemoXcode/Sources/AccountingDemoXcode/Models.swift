import Foundation

enum PayType: String, CaseIterable, Identifiable {
    case cash
    case card

    var id: String { rawValue }
}

struct Account: Identifiable {
    let id: Int64
    let code: String
    let name: String
}

struct AccountingDoc: Identifiable {
    let id: Int64
    let docNo: String
    let docDate: String
    let counterparty: String
    let note: String
}

struct AccountingItem: Identifiable {
    let id: Int64
    let lineNo: Int
    let debitCode: String
    let creditCode: String
    let amount: Double
    let lineDesc: String
}

struct EntryRow: Identifiable {
    let id: Int64
    let docDate: String
    let description: String
    let debit: String
    let credit: String
    let amount: Double
}

struct ProductRow: Identifiable {
    let id: Int64
    let sku: String
    let name: String
    let barcode: String
    let salePrice: Double
}

struct PurchaseRow: Identifiable {
    let id: Int64
    let docNo: String
    let docDate: String
    let supplier: String
    let sku: String
    let productName: String
    let qty: Double
    let cost: Double
    let lineTotal: Double
}

struct ReceiptRow: Identifiable {
    let id: Int64
    let receiptNo: String
    let createdAt: String
    let totalAmount: Double
    let payType: String
}

struct ReceiptItemRow: Identifiable {
    let id: Int64
    let productName: String
    let barcode: String
    let qty: Double
    let price: Double
    let lineTotal: Double
}

struct AccountingDocLine {
    let lineNo: Int
    let debitCode: String
    let creditCode: String
    let amount: Double
    let lineDesc: String
}

enum DbJob {
    case accountingDoc(docNo: String, docDate: Date, counterparty: String, note: String, line: AccountingDocLine)
    case receiptByBarcode(barcode: String, qty: Double, payType: String)
    case productCard(sku: String, name: String, barcode: String, salePrice: Double)
    case purchaseDoc(docNo: String, docDate: Date, supplier: String, sku: String, name: String, barcode: String, qty: Double, cost: Double, salePrice: Double)
}
