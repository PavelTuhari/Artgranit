import SwiftUI
import AppKit

@main
struct AccountingDemoXcodeApp: App {
    @StateObject private var viewModel = AppViewModel()
    
    init() {
        // SwiftPM executable launched from Xcode may not have a full app bundle metadata set.
        // Disable automatic tabbing to avoid AppKit indexing warnings.
        NSWindow.allowsAutomaticWindowTabbing = false
    }

    var body: some Scene {
        WindowGroup("Accounting Demo (SQLite)") {
            AppKitRootView(viewModel: viewModel)
                .frame(minWidth: 1100, minHeight: 700)
        }
    }
}
