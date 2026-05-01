# GT1000App - macOS App

A modern macOS application using a **workspace + SPM package** architecture for clean separation between app shell and feature code.

## Project Architecture

```
GT1000App/
├── GT1000App.xcworkspace/              # Open this file in Xcode
├── GT1000App.xcodeproj/                # App shell project
├── GT1000App/                          # App target (minimal)
│   ├── Assets.xcassets/                # App-level assets (icons, colors)
│   ├── GT1000AppApp.swift              # App entry point
│   ├── GT1000App.entitlements          # App sandbox settings
│   └── GT1000App.xctestplan            # Test configuration
├── GT1000AppPackage/                   # 🚀 Primary development area
│   ├── Package.swift                   # Package configuration
│   ├── Sources/GT1000AppFeature/       # Your feature code
│   └── Tests/GT1000AppFeatureTests/    # Unit tests
└── GT1000AppUITests/                   # UI automation tests
```

## Key Architecture Points

### Workspace + SPM Structure
- **App Shell**: `GT1000App/` contains minimal app lifecycle code
- **Feature Code**: `GT1000AppPackage/Sources/GT1000AppFeature/` is where most development happens
- **Separation**: Business logic lives in the SPM package, app target just imports and displays it

### Buildable Folders (Xcode 16)
- Files added to the filesystem automatically appear in Xcode
- No need to manually add files to project targets
- Reduces project file conflicts in teams

### App Sandbox
The app is sandboxed by default with basic file access permissions. Modify `GT1000App.entitlements` to add capabilities as needed.

## Development Notes

### Code Organization
Most development happens in `GT1000AppPackage/Sources/GT1000AppFeature/` - organize your code as you prefer.

### Public API Requirements
Types exposed to the app target need `public` access:
```swift
public struct SettingsView: View {
    public init() {}
    
    public var body: some View {
        // Your view code
    }
}
```

### Adding Dependencies
Edit `GT1000AppPackage/Package.swift` to add SPM dependencies:
```swift
dependencies: [
    .package(url: "https://github.com/example/SomePackage", from: "1.0.0")
],
targets: [
    .target(
        name: "GT1000AppFeature",
        dependencies: ["SomePackage"]
    ),
]
```

### Test Structure
- **Unit Tests**: `GT1000AppPackage/Tests/GT1000AppFeatureTests/` (Swift Testing framework)
- **UI Tests**: `GT1000AppUITests/` (XCUITest framework)
- **Test Plan**: `GT1000App.xctestplan` coordinates all tests

## Configuration

### XCConfig Build Settings
Build settings are managed through **XCConfig files** in `Config/`:
- `Config/Shared.xcconfig` - Common settings (bundle ID, versions, deployment target)
- `Config/Debug.xcconfig` - Debug-specific settings  
- `Config/Release.xcconfig` - Release-specific settings
- `Config/Tests.xcconfig` - Test-specific settings

### App Sandbox & Entitlements
The app is sandboxed by default with basic file access. Edit `GT1000App/GT1000App.entitlements` to add capabilities:
```xml
<key>com.apple.security.files.user-selected.read-write</key>
<true/>
<key>com.apple.security.network.client</key>
<true/>
<!-- Add other entitlements as needed -->
```

## macOS-Specific Features

### Window Management
Add multiple windows and settings panels:
```swift
@main
struct GT1000AppApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        
        Settings {
            SettingsView()
        }
    }
}
```

### Asset Management
- **App-Level Assets**: `GT1000App/Assets.xcassets/` (app icon with multiple sizes, accent color)
- **Feature Assets**: Add `Resources/` folder to SPM package if needed

### SPM Package Resources
To include assets in your feature package:
```swift
.target(
    name: "GT1000AppFeature",
    dependencies: [],
    resources: [.process("Resources")]
)
```

## Notes

### Generated with XcodeBuildMCP
This project was scaffolded using [XcodeBuildMCP](https://github.com/cameroncooke/XcodeBuildMCP), which provides tools for AI-assisted macOS development workflows.