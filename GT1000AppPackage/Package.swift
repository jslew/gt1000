// swift-tools-version: 6.1
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription

let package = Package(
    name: "GT1000AppFeature",
    platforms: [.macOS(.v15)],
    products: [
        // Products define the executables and libraries a package produces, making them visible to other packages.
        .library(
            name: "GT1000AppFeature",
            targets: ["GT1000AppFeature"]
        ),
    ],
    targets: [
        // Targets are the basic building blocks of a package, defining a module or a test suite.
        // Targets can depend on other targets in this package and products from dependencies.
        .target(
            name: "GT1000AppFeature"
        ),
        .testTarget(
            name: "GT1000AppFeatureTests",
            dependencies: [
                "GT1000AppFeature"
            ]
        ),
    ]
)
