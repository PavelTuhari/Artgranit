import SwiftUI
import BackgroundTasks
import UserNotifications

@main
struct TBControlApp: App {
    @StateObject private var store = MonitorStore.shared
    @StateObject private var settings = AppSettings.shared
    @Environment(\.scenePhase) private var phase

    static let refreshTaskID = "md.una.tbcontrol.refresh"

    init() {
        // Фоновое обновление (ТЗ §4): опрос + уведомления, когда приложение закрыто
        BGTaskScheduler.shared.register(forTaskWithIdentifier: Self.refreshTaskID, using: nil) { task in
            Self.scheduleRefresh()
            let t = task as! BGAppRefreshTask
            let work = Task { @MainActor in
                await MonitorStore.shared.refresh()
                t.setTaskCompleted(success: true)
            }
            t.expirationHandler = { work.cancel() }
        }
        UNUserNotificationCenter.current().delegate = NotificationDelegate.shared
    }

    static func scheduleRefresh() {
        let req = BGAppRefreshTaskRequest(identifier: refreshTaskID)
        req.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60)
        try? BGTaskScheduler.shared.submit(req)
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(store)
                .environmentObject(settings)
                .onAppear { store.requestNotificationPermission(); store.start() }
                .onChange(of: phase) { _, p in
                    switch p {
                    case .active: store.start()
                    case .background: store.stop(); Self.scheduleRefresh()
                    default: break
                    }
                }
        }
    }
}

/// Показывать баннер уведомления даже когда приложение открыто
final class NotificationDelegate: NSObject, UNUserNotificationCenterDelegate {
    static let shared = NotificationDelegate()
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent n: UNNotification) async -> UNNotificationPresentationOptions {
        [.banner, .sound, .badge, .list]
    }
}
