import SwiftUI
import AppKit

struct AppKitRootView: NSViewControllerRepresentable {
    @ObservedObject var viewModel: AppViewModel

    func makeNSViewController(context: Context) -> MainTabViewController {
        MainTabViewController(viewModel: viewModel)
    }

    func updateNSViewController(_ nsViewController: MainTabViewController, context: Context) {
        nsViewController.updateViewModel(viewModel)
    }
}

@MainActor
final class MainTabViewController: NSTabViewController {
    private var viewModel: AppViewModel

    init(viewModel: AppViewModel) {
        self.viewModel = viewModel
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        tabStyle = .toolbar
        transitionOptions = .crossfade

        let accounting = AccountingFormController(viewModel: viewModel)
        accounting.title = "Accounting"

        let cashier = CashierFormController(viewModel: viewModel)
        cashier.title = "Cashier"

        let admin = AdminFormController(viewModel: viewModel)
        admin.title = "Admin"

        addChild(accounting)
        addChild(cashier)
        addChild(admin)

        Task { await viewModel.bootstrap() }
    }

    func updateViewModel(_ vm: AppViewModel) {
        guard vm !== viewModel else { return }
        viewModel = vm
    }
}

@MainActor
class XibHostingController: NSViewController {
    private var hostingView: NSView?

    override func loadView() {
        if let nibName = nibName, let nib = NSNib(nibNamed: nibName, bundle: .main) {
            var topLevelObjects: NSArray?
            if nib.instantiate(withOwner: self, topLevelObjects: &topLevelObjects),
               let view = (topLevelObjects as? [Any])?.compactMap({ $0 as? NSView }).first {
                self.view = view
                return
            }
        }

        // Fallback to an empty view to avoid loadView exceptions when XIB wiring is incomplete.
        self.view = NSView(frame: .zero)
    }

    func installRootView<V: View>(_ rootView: V) {
        let host = NSHostingView(rootView: rootView)
        host.translatesAutoresizingMaskIntoConstraints = false

        // Replace static placeholder content from XIB with live runtime view.
        view.subviews.forEach { $0.removeFromSuperview() }

        view.addSubview(host)
        NSLayoutConstraint.activate([
            host.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            host.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            host.topAnchor.constraint(equalTo: view.topAnchor),
            host.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])

        hostingView = host
    }
}

@MainActor
final class AccountingFormController: XibHostingController {
    private let viewModel: AppViewModel

    init(viewModel: AppViewModel) {
        self.viewModel = viewModel
        super.init(nibName: "AccountingForm", bundle: .main)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        installRootView(AccountingTabView().environmentObject(viewModel))
    }
}

@MainActor
final class CashierFormController: XibHostingController {
    private let viewModel: AppViewModel

    init(viewModel: AppViewModel) {
        self.viewModel = viewModel
        super.init(nibName: "CashierForm", bundle: .main)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        installRootView(CashierTabView().environmentObject(viewModel))
    }
}

@MainActor
final class AdminFormController: XibHostingController {
    private let viewModel: AppViewModel

    init(viewModel: AppViewModel) {
        self.viewModel = viewModel
        super.init(nibName: "AdminForm", bundle: .main)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        installRootView(AdminTabView().environmentObject(viewModel))
    }
}
