import SwiftUI

struct StatusHeaderView: View {
    @EnvironmentObject private var vm: AppViewModel

    var body: some View {
        HStack(spacing: 16) {
            Text("DB: \(vm.dbPath)")
                .font(.caption)
                .lineLimit(1)
            Text("Status: \(vm.status)")
                .font(.caption)
            if !vm.lastError.isEmpty {
                Text("Error: \(vm.lastError)")
                    .font(.caption)
                    .foregroundStyle(.red)
            }
        }
        .padding(.horizontal)
        .padding(.top, 4)
    }
}

struct AccountingTabView: View {
    @EnvironmentObject private var vm: AppViewModel

    enum InputFocus: Hashable {
        case docNo, counterparty, lineDesc, debit, credit, amount
    }

    @FocusState private var focusedField: InputFocus?

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            StatusHeaderView()

            HStack {
                TextField("DocNo", text: $vm.docNo)
                    .focused($focusedField, equals: .docNo)
                TextField("Counterparty", text: $vm.counterparty)
                    .focused($focusedField, equals: .counterparty)
                TextField("Line", text: $vm.lineDesc)
                    .focused($focusedField, equals: .lineDesc)
                TextField("Debit", text: $vm.debitCode)
                    .frame(width: 80)
                    .focused($focusedField, equals: .debit)
                TextField("Credit", text: $vm.creditCode)
                    .frame(width: 80)
                    .focused($focusedField, equals: .credit)
                TextField("Amount", text: $vm.amount)
                    .frame(width: 90)
                    .focused($focusedField, equals: .amount)
                Button("Add document") { vm.addAccountingDoc() }
                Button(vm.accountingSimCaption) { vm.toggleAccountingSimulation() }
            }
            .textFieldStyle(.roundedBorder)
            .padding(.horizontal)

            HStack(spacing: 8) {
                List(selection: $vm.selectedDocId) {
                    ForEach(vm.accountingDocs) { doc in
                        VStack(alignment: .leading, spacing: 2) {
                            Text("\(doc.docNo) | \(doc.docDate)")
                                .font(.system(.body, design: .monospaced))
                            Text("\(doc.counterparty) | \(doc.note)")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        .tag(Optional(doc.id))
                    }
                }
                .onChange(of: vm.selectedDocId) { newValue in
                    Task { await vm.selectDoc(newValue) }
                }

                List(vm.accountingItems) { item in
                    Text("#\(item.lineNo)  D\(item.debitCode) C\(item.creditCode)  \(item.amount, specifier: "%.2f")  \(item.lineDesc)")
                        .font(.system(.body, design: .monospaced))
                }

                List(vm.entries) { entry in
                    Text("\(entry.docDate)  D\(entry.debit) C\(entry.credit)  \(entry.amount, specifier: "%.2f")  \(entry.description)")
                        .font(.system(.body, design: .monospaced))
                }
            }
            .padding(.horizontal)
        }
        .padding(.vertical, 8)
        .onChange(of: focusedField) { field in
            vm.setEditing(field != nil)
        }
    }
}

struct CashierTabView: View {
    @EnvironmentObject private var vm: AppViewModel

    enum InputFocus: Hashable {
        case cashierBarcode, cashierQty
    }

    @FocusState private var focusedField: InputFocus?

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            StatusHeaderView()

            HStack {
                TextField("Barcode", text: $vm.cashierBarcode)
                    .focused($focusedField, equals: .cashierBarcode)
                TextField("Qty", text: $vm.cashierQty)
                    .frame(width: 90)
                    .focused($focusedField, equals: .cashierQty)
                Picker("Pay", selection: $vm.payType) {
                    ForEach(PayType.allCases) { type in
                        Text(type.rawValue).tag(type)
                    }
                }
                .pickerStyle(.segmented)
                .frame(width: 180)
                Button("Sell") { vm.sellReceipt() }
                Button(vm.cashierSimCaption) { vm.toggleCashierSimulation() }
            }
            .textFieldStyle(.roundedBorder)
            .padding(.horizontal)

            HStack(spacing: 8) {
                List(selection: $vm.selectedReceiptId) {
                    ForEach(vm.receipts) { rec in
                        Text("\(rec.receiptNo) | \(rec.createdAt) | \(rec.totalAmount, specifier: "%.2f") | \(rec.payType)")
                            .font(.system(.body, design: .monospaced))
                            .tag(Optional(rec.id))
                    }
                }
                .onChange(of: vm.selectedReceiptId) { newValue in
                    Task { await vm.selectReceipt(newValue) }
                }

                List(vm.receiptItems) { item in
                    Text("\(item.productName) | \(item.barcode) | \(item.qty, specifier: "%.2f") x \(item.price, specifier: "%.2f") = \(item.lineTotal, specifier: "%.2f")")
                        .font(.system(.body, design: .monospaced))
                }
            }
            .padding(.horizontal)
        }
        .padding(.vertical, 8)
        .onChange(of: focusedField) { field in
            vm.setEditing(field != nil)
        }
    }
}

struct AdminTabView: View {
    @EnvironmentObject private var vm: AppViewModel

    enum InputFocus: Hashable {
        case sku, name, adminBarcode, salePrice, purchaseDocNo, supplier, purchaseQty, purchaseCost
    }

    @FocusState private var focusedField: InputFocus?

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            StatusHeaderView()

            HStack {
                TextField("SKU", text: $vm.sku)
                    .focused($focusedField, equals: .sku)
                TextField("Name", text: $vm.productName)
                    .focused($focusedField, equals: .name)
                TextField("Barcode", text: $vm.adminBarcode)
                    .focused($focusedField, equals: .adminBarcode)
                TextField("Sale price", text: $vm.salePrice)
                    .frame(width: 90)
                    .focused($focusedField, equals: .salePrice)
                Button("Save card") { vm.saveCard() }
            }
            .textFieldStyle(.roundedBorder)
            .padding(.horizontal)

            HStack {
                TextField("Purchase doc", text: $vm.purchaseDocNo)
                    .focused($focusedField, equals: .purchaseDocNo)
                TextField("Supplier", text: $vm.supplier)
                    .focused($focusedField, equals: .supplier)
                TextField("Qty", text: $vm.purchaseQty)
                    .frame(width: 80)
                    .focused($focusedField, equals: .purchaseQty)
                TextField("Cost", text: $vm.purchaseCost)
                    .frame(width: 80)
                    .focused($focusedField, equals: .purchaseCost)
                Button("Add purchase") { vm.addPurchase() }
                Button(vm.adminSimCaption) { vm.toggleAdminSimulation() }
            }
            .textFieldStyle(.roundedBorder)
            .padding(.horizontal)

            HStack(spacing: 8) {
                List(vm.products) { p in
                    Text("\(p.sku) | \(p.name) | \(p.barcode) | \(p.salePrice, specifier: "%.2f")")
                        .font(.system(.body, design: .monospaced))
                }

                List(vm.purchases) { p in
                    Text("\(p.docNo) | \(p.docDate) | \(p.supplier) | \(p.sku) | \(p.qty, specifier: "%.2f") x \(p.cost, specifier: "%.2f") = \(p.lineTotal, specifier: "%.2f")")
                        .font(.system(.body, design: .monospaced))
                }
            }
            .padding(.horizontal)
        }
        .padding(.vertical, 8)
        .onChange(of: focusedField) { field in
            vm.setEditing(field != nil)
        }
    }
}
