import SwiftUI

public struct ContentView: View {
    @State private var midiManager = MIDIManager()
    @State private var bpm: Double = 120
    @State private var tunerAssignInstalled = false
    @State private var pendingTunerControlTask: Task<Void, Never>?
    
    public init() {}
    
    public var body: some View {
        VStack(spacing: 20) {
            HStack {
                Circle()
                    .fill(midiManager.isConnected ? Color.green : Color.red)
                    .frame(width: 10, height: 10)
                
                Text(midiManager.isConnected ? "Connected to \(midiManager.connectedDeviceName ?? "GT-1000")" : "Disconnected")
                    .font(.headline)
                
                Spacer()
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
                }
                
                Button("List All Ports") {
                    midiManager.listAllPorts()
                }
                .buttonStyle(.bordered)
            }
            
            Divider()
            
            VStack(alignment: .leading, spacing: 15) {
                Text("Verification Controls")
                    .font(.title3)
                
                HStack {
                    Button("Identify") { sendIdentityRequest() }
                    Button("Req Name") { requestPatchName() }
                    Button("Toggle Tuner") { toggleTuner() }
                    Button("Next Patch") { sendProgramChange() }
                }
                .buttonStyle(.bordered)
                .disabled(!midiManager.isConnected)

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
            }
            .padding()
            
            Spacer()
            
            Text("GT-1000 v4.0.1 Scaffold")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding()
        .frame(minWidth: 400, minHeight: 300)
        .onAppear {
            midiManager.updateConnectionStatus()
        }
    }
    
    @State private var tunerOn = false

    func initializeCommunication() {
        installTunerAssign()
    }
    
    func toggleTuner() {
        let nextTunerState = !tunerOn
        let shouldDelayControlChange = !tunerAssignInstalled || pendingTunerControlTask != nil

        tunerOn = nextTunerState

        if !tunerAssignInstalled {
            installTunerAssign()
        }

        scheduleTunerControlChange(isOn: nextTunerState, delayed: shouldDelayControlChange)
    }

    func sendIdentityRequest() {
        midiManager.sendSysEx(GT1000SysEx.identityRequest())
    }

    func requestPatchName() {
        let message = GT1000SysEx.buildRequestData(
            address: GT1000SysEx.Address.temporaryPatchName,
            size: [0x00, 0x00, 0x00, 0x10]
        )
        midiManager.sendSysEx(message)
    }

    func sendProgramChange() {
        tunerAssignInstalled = false
        midiManager.sendProgramChange(patch: 0x01)
    }

    func sendBPM() {
        let data = GT1000SysEx.bpmData(for: bpm)
        sendDataSet(address: GT1000SysEx.Address.temporaryPatchMasterBPM, data: data)
        sendDataSet(address: GT1000SysEx.Address.systemMetronomeBPM, data: data)
    }

    func installTunerAssign() {
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

            midiManager.sendControlChangeOnAllChannels(
                controller: GT1000SysEx.Assign.tunerControlChange,
                value: isOn ? 127 : 0
            )
            pendingTunerControlTask = nil
        }
    }

    func sendDataSet(address: [UInt8], data: [UInt8]) {
        let message = GT1000SysEx.buildDataSet(address: address, data: data)
        midiManager.sendSysEx(message)
    }
}

#Preview {
    ContentView()
}
