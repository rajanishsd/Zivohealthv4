import SwiftUI
import LiveKit

@available(iOS 15.0, *)
struct VideoCallView: View {
    let doctor: Doctor
    @Environment(\.presentationMode) var presentationMode
    @StateObject private var viewModel = VideoCallViewModel()

    var body: some View {
        ZStack {
            // Video background
            Color.black
                .ignoresSafeArea()

            // Doctor video placeholder
            VStack {
                Spacer()
                
                // Doctor info overlay
                VStack(spacing: 8) {
                    AsyncImage(url: URL(string: doctor.profileImageURL ?? "")) { image in
                        image
                            .resizable()
                            .aspectRatio(contentMode: .fill)
                    } placeholder: {
                        Circle()
                            .fill(Color.gray.opacity(0.3))
                            .overlay(
                                Text(doctor.fullName.prefix(1))
                                    .font(.title)
                                    .foregroundColor(.white)
                            )
                    }
                    .frame(width: 80, height: 80)
                    .clipShape(Circle())
                    
                    Text(doctor.fullName)
                        .font(.headline)
                        .foregroundColor(.white)
                    
                    Text(doctor.specialization)
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.8))
                    
                    if !viewModel.callDuration.isEmpty {
                        Text(viewModel.callDuration)
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.7))
                    }
                }
                .padding()
                .background(Color.black.opacity(0.3))
                .cornerRadius(16)
                .padding(.top, 50)
                
                Spacer()
                
                // Control buttons
                HStack(spacing: 40) {
                    // Mute button
                    Button(action: {
                        viewModel.toggleMute()
                    }) {
                        Image(systemName: viewModel.isMuted ? "mic.slash.fill" : "mic.fill")
                            .font(.title2)
                            .foregroundColor(.white)
                            .frame(width: 60, height: 60)
                            .background(viewModel.isMuted ? Color.red : Color.white.opacity(0.2))
                            .clipShape(Circle())
                    }
                    
                    // End call button
                    Button(action: {
                        viewModel.endCall()
                        presentationMode.wrappedValue.dismiss()
                    }) {
                        Image(systemName: "phone.down.fill")
                            .font(.title2)
                            .foregroundColor(.white)
                            .frame(width: 60, height: 60)
                            .background(Color.red)
                            .clipShape(Circle())
                    }
                    
                    // Camera button
                    Button(action: {
                        viewModel.toggleCamera()
                    }) {
                        Image(systemName: viewModel.isCameraEnabled ? "video.fill" : "video.slash.fill")
                            .font(.title2)
                            .foregroundColor(.white)
                            .frame(width: 60, height: 60)
                            .background(viewModel.isCameraEnabled ? Color.white.opacity(0.2) : Color.red)
                            .clipShape(Circle())
                    }
                }
                .padding(.bottom, 50)
            }

            // Connection status overlay
            if viewModel.connectionStatus != .connected {
                VStack(spacing: 16) {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        .scaleEffect(1.5)
                    
                    Text(viewModel.connectionStatus == .connecting ? "Connecting..." : "Disconnected")
                        .font(.headline)
                        .foregroundColor(.white)
                    
                    Text("Please wait while we establish the connection")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.8))
                        .multilineTextAlignment(.center)
                }
                .padding()
                .background(Color.black.opacity(0.7))
                .cornerRadius(16)
                .padding()
            }
        }
        .onAppear {
            viewModel.startCall(with: doctor)
        }
        .onDisappear {
            viewModel.endCall()
        }
    }
}

@available(iOS 15.0, *)
@MainActor
class VideoCallViewModel: ObservableObject {
    @Published var isMuted = false
    @Published var isCameraEnabled = true
    @Published var connectionStatus: ConnectionStatus = .connecting
    @Published var callDuration = ""
    
    private var callTimer: Timer?
    private let networkService = NetworkService.shared
    private let room = Room()
    private var callStartTime: Date?
    
    enum ConnectionStatus {
        case connecting
        case connected
        case disconnected
    }
    
    init() {
        print("🎥 [VideoCall] ViewModel initialized")
    }
    
    deinit {
        print("🎥 [VideoCall] ViewModel deinitialized")
        callTimer?.invalidate()
    }

    func startCall(with doctor: Doctor) {
        print("📞 [VideoCall] Starting call with \(doctor.fullName)")
        connectionStatus = .connecting
        let roomName = "consultation-\(doctor.id)"
        Task {
            await connectToLiveKit(roomName: roomName, role: "doctor")
        }
    }

    func endCall() {
        print("📞 [VideoCall] Ending call")
        Task { @MainActor in
            await room.disconnect()
            connectionStatus = .disconnected
            callTimer?.invalidate()
            callTimer = nil
        }
    }

    func toggleMute() {
        isMuted.toggle()
        print("🎤 [VideoCall] Mute toggled: \(isMuted)")
    }

    func toggleCamera() {
        isCameraEnabled.toggle()
        print("📷 [VideoCall] Camera toggled: \(isCameraEnabled)")
    }

    private func startCallTimer() {
        callStartTime = Date()
        callTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in
            Task { @MainActor in
                self.updateCallDuration()
            }
        }
    }

    private func connectToLiveKit(roomName: String, role: String) async {
        do {
            let url = try await networkService.getLiveKitURL()
            let identity = "\(role)-\(UUID().uuidString.prefix(8))"
            let token = try await networkService.createLiveKitToken(
                room: roomName,
                identity: String(identity),
                name: nil,
                metadata: ["role": role],
                ttlSeconds: 3600
            )
            try await room.connect(url: url, token: token)
            await MainActor.run {
                self.connectionStatus = .connected
                self.startCallTimer()
            }
        } catch {
            print("❌ [VideoCall] LiveKit connect error: \(error)")
            await MainActor.run {
                self.connectionStatus = .disconnected
            }
        }
    }

    private func updateCallDuration() {
        guard let startTime = callStartTime else { return }

        let elapsed = Int(Date().timeIntervalSince(startTime))
        let minutes = elapsed / 60
        let seconds = elapsed % 60

        callDuration = String(format: "%02d:%02d", minutes, seconds)
    }
}

#Preview {
    VideoCallView(doctor: Doctor(
        id: 1,
        fullName: "Dr. Sarah Johnson",
        specialization: "General Medicine",
        yearsExperience: 12,
        rating: 4.8,
        totalConsultations: 1250,
        bio: "Experienced general practitioner",
        isAvailable: true
    ))
}
