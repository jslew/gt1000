import SwiftUI

public struct ContentView: View {
    @State private var diagnostics = GT1000Diagnostics.shared
    @State private var midiManager: MIDIManager
    @State private var bpm: Double = 120
    @State private var tunerAssignInstalled = false
    @State private var pendingTunerControlTask: Task<Void, Never>?
    @State private var patchSnapshot = GT1000PatchSnapshot()
    @State private var patchInspectorStatus = "No patch data read yet"
    @State private var diagnosticsRevision = 0
    @State private var latestDiagnosticMessage = "No diagnostics yet"
    @State private var didRunLaunchAutomation = false
    
    public init() {
        let diagnostics = GT1000Diagnostics.shared
        _diagnostics = State(initialValue: diagnostics)
        _midiManager = State(initialValue: MIDIManager(diagnostics: diagnostics))
    }
    
    public var body: some View {
        VStack(spacing: 20) {
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Circle()
                        .fill(midiManager.isConnected ? Color.green : Color.red)
                        .frame(width: 10, height: 10)

                    Text(midiManager.isConnected ? "Connected to \(midiManager.connectedDeviceName ?? "GT-1000")" : "Disconnected")
                        .font(.headline)
                        .accessibilityIdentifier("connection-status")

                    Spacer()
                }

                TextField(
                    "Latest Diagnostic",
                    text: $latestDiagnosticMessage
                )
                    .textFieldStyle(.plain)
                    .disabled(true)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .accessibilityIdentifier("diagnostics-latest-message")
            }
            .padding()
            .background(Color.secondary.opacity(0.1))
            .cornerRadius(10)
            
            HStack {
                if midiManager.isConnected {
                    Button(action: initializeCommunication) {
                        Label("Initialize", systemImage: "bolt.fill")
                    }
                    .buttonStyle(.bordered)
                    .tint(.orange)
                    .accessibilityIdentifier("initialize-button")
                }
                
                Button("List All Ports") {
                    listAllPorts()
                }
                .buttonStyle(.bordered)
                .accessibilityIdentifier("list-ports-button")
            }
            
            Divider()
            
            VStack(alignment: .leading, spacing: 15) {
                Text("Verification Controls")
                    .font(.title3)
                
                HStack {
                    Button("Identify") { sendIdentityRequest() }
                        .accessibilityIdentifier("identify-button")
                    Button("Req Name") { requestPatchName() }
                        .accessibilityIdentifier("request-name-button")
                    Button("Read Patch") { readCurrentPatch() }
                        .accessibilityIdentifier("read-patch-button")
                    Button("Toggle Tuner") { toggleTuner() }
                        .accessibilityIdentifier("toggle-tuner-button")
                    Button("Next Patch") { sendProgramChange() }
                        .accessibilityIdentifier("next-patch-button")
                }
                .buttonStyle(.bordered)
                .disabled(!midiManager.isConnected)

                VStack(alignment: .leading, spacing: 8) {
                    Text("Patch Inspector")
                        .font(.title3)

                    Text(patchInspectorStatus)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .accessibilityIdentifier("patch-inspector-status")

                    Text(patchSnapshot.signalChainSummary)
                        .font(.system(.body, design: .monospaced))
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .accessibilityIdentifier("patch-summary")
                }

                Divider()

                Text("Test Control: Master BPM")
                    .font(.title3)
                
                HStack {
                    Slider(value: $bpm, in: 40...250, step: 1)
                    Text("\(Int(bpm)) BPM")
                        .frame(width: 80)
                }
                
                Button(action: sendBPM) {
                    Label("Update GT-1000 BPM", systemImage: "metronome")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(!midiManager.isConnected)
                .accessibilityIdentifier("update-bpm-button")

                Divider()

                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text("Diagnostics")
                            .font(.title3)

                        Spacer()

                        Button("Clear Log") {
                            diagnostics.clear()
                            refreshDiagnostics()
                        }
                        .buttonStyle(.bordered)
                        .accessibilityIdentifier("clear-log-button")
                    }

                    Text(diagnostics.entries.last?.message ?? "No diagnostics yet")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    ScrollView {
                        let diagnosticsText = diagnostics.entries.isEmpty
                            ? "No diagnostics yet"
                            : diagnostics.entries.map(\.formattedText).joined(separator: "\n")

                        Text(diagnosticsText)
                            .font(.system(.caption, design: .monospaced))
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .accessibilityIdentifier("diagnostics-log")
                            .accessibilityLabel(diagnosticsText)
                    }
                    .frame(minHeight: 120, maxHeight: 180)
                    .background(Color.secondary.opacity(0.08))
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                }
            }
            .padding()
            
            Spacer()
            
            Text("GT-1000 v4.0.1 Scaffold")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding()
        .frame(minWidth: 640, minHeight: 720)
        .onAppear {
            midiManager.updateConnectionStatus()
            midiManager.listAllPorts()
            refreshDiagnostics()
            runLaunchAutomationIfRequested()
        }
        .onChange(of: midiManager.lastReceivedMessage) { _, message in
            applyIncomingMessageToPatchSnapshot(message)
        }
    }
    
    @State private var tunerOn = false

    func listAllPorts() {
        midiManager.listAllPorts()
        refreshDiagnostics()
    }

    func initializeCommunication() {
        diagnostics.info("Initialize requested")
        installTunerAssign()
        refreshDiagnostics()
    }
    
    func toggleTuner() {
        let nextTunerState = !tunerOn
        let shouldDelayControlChange = !tunerAssignInstalled || pendingTunerControlTask != nil

        tunerOn = nextTunerState
        diagnostics.info("Toggle tuner requested: \(nextTunerState ? "on" : "off")")

        if !tunerAssignInstalled {
            installTunerAssign()
        }

        scheduleTunerControlChange(isOn: nextTunerState, delayed: shouldDelayControlChange)
        refreshDiagnostics()
    }

    func sendIdentityRequest() {
        diagnostics.info("Identity request queued")
        midiManager.sendSysEx(GT1000SysEx.identityRequest())
        refreshDiagnostics()
    }

    func requestPatchName() {
        diagnostics.info("Patch name read requested")
        sendPatchRead(GT1000SysEx.PatchReadPlan.patchName)
        refreshDiagnostics()
    }

    func readCurrentPatch() {
        patchSnapshot = GT1000PatchSnapshot()
        patchInspectorStatus = "Requested current patch snapshot"
        diagnostics.info("Current patch snapshot read requested")

        for request in GT1000SysEx.PatchReadPlan.initialSnapshotReads {
            sendPatchRead(request)
        }
        refreshDiagnostics()
    }

    func sendProgramChange() {
        tunerAssignInstalled = false
        diagnostics.info("Program change requested: patch 1")
        midiManager.sendProgramChange(patch: 0x01)
        refreshDiagnostics()
    }

    func sendBPM() {
        let data = GT1000SysEx.bpmData(for: bpm)
        diagnostics.info("BPM update requested: \(Int(bpm)) BPM")
        sendDataSet(address: GT1000SysEx.Address.temporaryPatchMasterBPM, data: data)
        sendDataSet(address: GT1000SysEx.Address.systemMetronomeBPM, data: data)
        refreshDiagnostics()
    }

    func installTunerAssign() {
        diagnostics.info("Installing tuner Assign 16 mapping")
        sendDataSet(
            address: GT1000SysEx.Address.temporaryAssign16,
            data: GT1000SysEx.Assign.tunerControlChangeData
        )
        tunerAssignInstalled = true
    }

    func scheduleTunerControlChange(isOn: Bool, delayed: Bool) {
        pendingTunerControlTask?.cancel()

        pendingTunerControlTask = Task { @MainActor in
            if delayed {
                try? await Task.sleep(for: .milliseconds(250))
            }

            guard !Task.isCancelled else { return }

            diagnostics.info("Sending tuner CC#\(GT1000SysEx.Assign.tunerControlChange) \(isOn ? 127 : 0) on all channels")
            midiManager.sendControlChangeOnAllChannels(
                controller: GT1000SysEx.Assign.tunerControlChange,
                value: isOn ? 127 : 0
            )
            pendingTunerControlTask = nil
            refreshDiagnostics()
        }
    }

    func sendDataSet(address: [UInt8], data: [UInt8]) {
        let message = GT1000SysEx.buildDataSet(address: address, data: data)
        midiManager.sendSysEx(message)
    }

    func sendPatchRead(_ request: GT1000SysEx.PatchReadRequest) {
        diagnostics.info("Sending patch read \(request.label)")
        midiManager.sendSysEx(request.message)
    }

    func applyIncomingMessageToPatchSnapshot(_ message: [UInt8]) {
        guard !message.isEmpty else { return }

        do {
            let decoder = GT1000PatchSnapshotDecoder()
            let nextSnapshot = try decoder.applying(message: message, to: patchSnapshot)
            if nextSnapshot != patchSnapshot {
                patchSnapshot = nextSnapshot
                patchInspectorStatus = "Updated from GT-1000 reply"
                diagnostics.info("Decoded patch reply from \(Self.hexString(message))")
                refreshDiagnostics()
            }
        } catch GT1000SysEx.ParseError.unsupportedCommand(_) {
            return
        } catch {
            patchInspectorStatus = "Ignored unrecognized patch reply"
            diagnostics.warning("Ignored unrecognized patch reply \(Self.hexString(message)): \(error)")
            refreshDiagnostics()
        }
    }

    func refreshDiagnostics() {
        latestDiagnosticMessage = diagnostics.entries.last?.message ?? "No diagnostics yet"
        diagnosticsRevision += 1
    }

    func runLaunchAutomationIfRequested() {
        guard !didRunLaunchAutomation else { return }

        let commandsValue = Self.launchAutomationCommandsValue()
        let commands = commandsValue
            .split(separator: ",")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        guard !commands.isEmpty else { return }
        didRunLaunchAutomation = true

        Task { @MainActor in
            try? await Task.sleep(for: .milliseconds(200))

            for command in commands {
                switch command {
                case "listPorts":
                    listAllPorts()
                case "identify":
                    sendIdentityRequest()
                case "readPatch":
                    readCurrentPatch()
                case "requestPatchName":
                    requestPatchName()
                default:
                    diagnostics.warning("Unknown launch automation command: \(command)")
                    refreshDiagnostics()
                }

                try? await Task.sleep(for: .milliseconds(100))
            }
        }
    }

    static func launchAutomationCommandsValue() -> String {
        let arguments = ProcessInfo.processInfo.arguments
        if let flagIndex = arguments.firstIndex(of: "--gt1000-automation-commands"),
           arguments.indices.contains(arguments.index(after: flagIndex)) {
            return arguments[arguments.index(after: flagIndex)]
        }

        if let userDefaultCommands = UserDefaults.standard.string(forKey: "GT1000AutomationCommands") {
            return userDefaultCommands
        }

        return ProcessInfo.processInfo.environment["GT1000_AUTOMATION_COMMANDS", default: ""]
    }

    static func hexString(_ message: [UInt8]) -> String {
        message.map { String(format: "%02X", $0) }.joined(separator: " ")
    }
}

#Preview {
    ContentView()
}
