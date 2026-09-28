// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "AccountingDemoXcode",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "AccountingDemoXcode", targets: ["AccountingDemoXcode"])
    ],
    targets: [
        .executableTarget(
            name: "AccountingDemoXcode",
            exclude: [
                "Info.plist"
            ],
            linkerSettings: [
                .linkedFramework("SwiftUI"),
                .linkedFramework("AppKit"),
                .linkedLibrary("sqlite3")
            ]
        )
    ]
)
