import XCTest

final class GT1000AppUITests: XCTestCase {

    override func setUpWithError() throws {
        // Put setup code here. This method is called before the invocation of each test method in the class.

        // In UI tests it is usually best to stop immediately when a failure occurs.
        continueAfterFailure = false

        // In UI tests it’s important to set the initial state - such as interface orientation - required for your tests before they run. The setUp method is a good place to do this.
    }

    override func tearDownWithError() throws {
        // Put teardown code here. This method is called after the invocation of each test method in the class.
    }

    @MainActor
    func testDiagnosticsSmokeFlow() throws {
        let app = XCUIApplication()
        app.launchArguments += [
            "--gt1000-automation-commands", "listPorts",
            "-GT1000AutomationCommands", "listPorts"
        ]
        app.launch()

        XCTAssertTrue(app.staticTexts["connection-status"].waitForExistence(timeout: 5))

        XCTAssertTrue(app.buttons["List All Ports"].waitForExistence(timeout: 2))
        let diagnosticsLog = app.staticTexts["diagnostics-log"]
        XCTAssertTrue(diagnosticsLog.waitForExistence(timeout: 2))
        XCTAssertTrue(wait(forValueOf: app.textFields["diagnostics-latest-message"], toContain: "MIDI port inventory complete"))
    }

    @MainActor
    func testLiveGT1000ControlsWhenRequested() throws {
        let app = XCUIApplication()
        app.launchArguments += [
            "--gt1000-automation-commands", "identify,readPatch",
            "-GT1000AutomationCommands", "identify,readPatch"
        ]
        app.launch()

        XCTAssertTrue(app.staticTexts["connection-status"].waitForExistence(timeout: 5))

        XCTAssertTrue(wait(forValueOf: app.textFields["diagnostics-latest-message"], toContain: "Decoded patch reply"))
    }

    @MainActor
    private func wait(
        forValueOf element: XCUIElement,
        toContain expectedText: String,
        timeout: TimeInterval = 3,
        file: StaticString = #filePath,
        line: UInt = #line
    ) -> Bool {
        let deadline = Date().addingTimeInterval(timeout)
        var latestValue = ""

        repeat {
            latestValue = element.value as? String ?? ""
            if latestValue.contains(expectedText) {
                return true
            }

            RunLoop.current.run(until: Date().addingTimeInterval(0.1))
        } while Date() < deadline

        XCTFail(
            "Expected \(element) value to contain \(expectedText). exists=\(element.exists), value=\(latestValue)",
            file: file,
            line: line
        )

        return false
    }
}
