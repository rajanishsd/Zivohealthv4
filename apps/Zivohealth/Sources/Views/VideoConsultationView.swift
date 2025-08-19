import SwiftUI

@available(iOS 15.0, *)
struct VideoConsultationView: View {
    @Environment(\.presentationMode) var presentationMode
    @StateObject private var viewModel = VideoConsultationViewModel()

    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Header
                VStack(spacing: 16) {
                    Image(systemName: "video.fill")
                        .font(.system(size: 60))
                        .foregroundColor(.blue)

                    Text("Immediate Video Consultation")
                        .font(.title2)
                        .fontWeight(.semibold)

                    Text("Connect with available doctors instantly through secure video calls")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                }
                .padding(.top, 20)
                .padding(.bottom, 30)
                .background(Color(.systemGray6))

                // Content
                ScrollView {
                    VStack(spacing: 24) {
                        // Quick Connect Options
                        VStack(spacing: 16) {
                            Text("Connect Options")
                                .font(.headline)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.horizontal)
                            
                            // Send to all available doctors
                            VideoConsultationActionCard(
                                icon: "person.2.circle.fill",
                                title: "Connect with Any Available Doctor",
                                subtitle: "Fastest connection",
                                description: "Send request to all available doctors - first to respond will connect",
                                color: .blue,
                                estimatedTime: "~30 sec",
                                buttonText: "Send to All"
                            ) {
                                viewModel.requestVideoCallToAll()
                            }
                        }
                        
                        // Available doctors section
                        if viewModel.isLoading {
                            VStack(spacing: 12) {
                                ProgressView()
                                    .scaleEffect(1.2)
                                Text("Finding available doctors...")
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                            }
                            .padding()
                        } else if !viewModel.availableDoctors.isEmpty {
                            VStack(alignment: .leading, spacing: 12) {
                                HStack {
                                    Text("Available Doctors (\(viewModel.availableDoctors.count))")
                                        .font(.headline)
                                    
                                    Spacer()
                                    
                                    if !viewModel.selectedDoctors.isEmpty {
                                        Button("Send to Selected (\(viewModel.selectedDoctors.count))") {
                                            viewModel.requestVideoCallToSelected()
                                        }
                                        .buttonStyle(.borderedProminent)
                                        .controlSize(.small)
                                    }
                                }
                                .padding(.horizontal)
                                
                                Text("Select specific doctors or tap 'Call' to connect directly")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                    .padding(.horizontal)
                                
                                ForEach(viewModel.availableDoctors) { doctor in
                                    VideoDoctorCard(
                                        doctor: doctor,
                                        isSelected: viewModel.selectedDoctors.contains(doctor.id),
                                        onSelect: {
                                            viewModel.toggleDoctorSelection(doctor)
                                        },
                                        onDirectCall: {
                                            viewModel.requestVideoCall(with: doctor)
                                        }
                                    )
                                    .padding(.horizontal)
                                }
                            }
                        } else if !viewModel.isLoading {
                            VStack(spacing: 16) {
                                Image(systemName: "exclamationmark.triangle")
                                    .font(.system(size: 40))
                                    .foregroundColor(.orange)
                                
                                Text("No Doctors Available")
                                    .font(.headline)
                                
                                Text("All doctors are currently busy. Please try again in a few minutes or schedule a consultation for later.")
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                                    .multilineTextAlignment(.center)
                                
                                Button("Refresh") {
                                    viewModel.loadAvailableDoctors()
                                }
                                .buttonStyle(.bordered)
                            }
                            .padding()
                        }
                        
                        if let error = viewModel.error {
                            VStack(spacing: 12) {
                                Image(systemName: "wifi.slash")
                                    .font(.system(size: 40))
                                    .foregroundColor(.red)
                                
                                Text("Connection Error")
                                    .font(.headline)
                                
                                Text(error)
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                                    .multilineTextAlignment(.center)
                                
                                Button("Try Again") {
                                    viewModel.loadAvailableDoctors()
                                }
                                .buttonStyle(.bordered)
                            }
                            .padding()
                        }
                    }
                    .padding(.vertical)
                }
                
                Spacer()
            }
            .navigationBarTitleDisplayMode(.inline)
            .navigationBarBackButtonHidden(true)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Back") {
                        presentationMode.wrappedValue.dismiss()
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Refresh") {
                        viewModel.loadAvailableDoctors()
                    }
                    .disabled(viewModel.isLoading)
                }
            }
        }
        .onAppear {
            viewModel.loadAvailableDoctors()
        }
        .sheet(isPresented: $viewModel.showingVideoCall) {
            if let doctor = viewModel.selectedDoctor {
                VideoCallView(doctor: doctor)
            }
        }
        .alert("Video Call Request", isPresented: $viewModel.showingCallRequest) {
            Button("Cancel", role: .cancel) {
                viewModel.cancelVideoCallRequest()
            }
        } message: {
            if viewModel.requestType == .all {
                Text("Sending video call request to all available doctors. First to respond will connect with you.")
            } else if viewModel.requestType == .selected {
                Text("Sending video call request to \(viewModel.selectedDoctors.count) selected doctors.")
            } else if let doctor = viewModel.selectedDoctor {
                Text("Requesting video call with \(doctor.fullName). Please wait for confirmation.")
            }
        }
    }
}

@available(iOS 15.0, *)
struct VideoConsultationActionCard: View {
    let icon: String
    let title: String
    let subtitle: String
    let description: String
    let color: Color
    let estimatedTime: String
    let buttonText: String
    let action: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: icon)
                    .font(.title2)
                    .foregroundColor(color)
                
                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.headline)
                        .foregroundColor(.primary)
                    
                    Text(subtitle)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                VStack(alignment: .trailing) {
                    Text(estimatedTime)
                        .font(.caption)
                        .foregroundColor(color)
                        .fontWeight(.medium)
                }
            }
            
            Text(description)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.leading)
            
            Button(buttonText) {
                action()
            }
            .buttonStyle(.borderedProminent)
            .frame(maxWidth: .infinity)
        }
        .padding(16)
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(color.opacity(0.2), lineWidth: 1)
        )
        .shadow(color: Color.black.opacity(0.05), radius: 2, x: 0, y: 1)
        .padding(.horizontal)
    }
}

@available(iOS 15.0, *)
struct VideoDoctorCard: View {
    let doctor: Doctor
    let isSelected: Bool
    let onSelect: () -> Void
    let onDirectCall: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            // Selection checkbox
            Button(action: onSelect) {
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.title3)
                    .foregroundColor(isSelected ? .blue : .gray)
            }
            
            // Doctor avatar
            AsyncImage(url: URL(string: doctor.profileImageURL ?? "")) { image in
                image
                    .resizable()
                    .aspectRatio(contentMode: .fill)
            } placeholder: {
                Circle()
                    .fill(Color.blue.opacity(0.2))
                    .overlay(
                        Text(doctor.fullName.prefix(2).uppercased())
                            .font(.headline)
                            .foregroundColor(.blue)
                    )
            }
            .frame(width: 50, height: 50)
            .clipShape(Circle())
            
            VStack(alignment: .leading, spacing: 4) {
                Text(doctor.fullName)
                    .font(.headline)
                    .foregroundColor(.primary)
                
                Text(doctor.specialization)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                HStack(spacing: 8) {
                    HStack(spacing: 4) {
                        Circle()
                            .fill(Color.green)
                            .frame(width: 8, height: 8)
                        
                        Text("Available now")
                            .font(.caption)
                            .foregroundColor(.green)
                    }
                    
                    if doctor.rating > 0 {
                        HStack(spacing: 2) {
                            Image(systemName: "star.fill")
                                .font(.caption)
                                .foregroundColor(.orange)
                            Text(String(format: "%.1f", doctor.rating))
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }
            }
            
            Spacer()
            
            Button("Call") {
                onDirectCall()
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.small)
        }
        .padding(12)
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(isSelected ? Color.blue : Color.clear, lineWidth: 2)
        )
        .shadow(color: Color.black.opacity(0.05), radius: 2, x: 0, y: 1)
    }
}

@available(iOS 15.0, *)
@MainActor
class VideoConsultationViewModel: ObservableObject {
    @Published var availableDoctors: [Doctor] = []
    @Published var selectedDoctors: Set<Int> = []
    @Published var isLoading = false
    @Published var error: String?
    @Published var showingVideoCall = false
    @Published var showingCallRequest = false
    @Published var selectedDoctor: Doctor?
    @Published var requestType: RequestType = .individual

    enum RequestType {
        case individual
        case selected
        case all
    }

    private let networkService = NetworkService.shared

    func loadAvailableDoctors() {
        print("🎥 [VideoConsultation] Loading available doctors for immediate video consultation")
        isLoading = true
        error = nil

        Task {
            do {
                // Get doctors available for immediate video consultation
                let doctors = try await networkService.findDoctorsByContext("immediate video consultation available now")

                await MainActor.run {
                    self.availableDoctors = doctors.filter { $0.isAvailable }
                    self.isLoading = false
                    self.selectedDoctors.removeAll() // Clear selection when refreshing
                    print("✅ [VideoConsultation] Found \(self.availableDoctors.count) available doctors for immediate consultation")
                }
            } catch {
                await MainActor.run {
                    self.error = error.localizedDescription
                    self.isLoading = false
                    print("❌ [VideoConsultation] Error loading doctors: \(error)")
                }
            }
        }
    }

    func toggleDoctorSelection(_ doctor: Doctor) {
        if selectedDoctors.contains(doctor.id) {
            selectedDoctors.remove(doctor.id)
            print("🔄 [VideoConsultation] Deselected \(doctor.fullName)")
        } else {
            selectedDoctors.insert(doctor.id)
            print("✅ [VideoConsultation] Selected \(doctor.fullName)")
        }
    }

    func requestVideoCall(with doctor: Doctor) {
        print("📞 [VideoConsultation] Requesting immediate video call with \(doctor.fullName)")
        selectedDoctor = doctor
        requestType = .individual
        showingCallRequest = true

        // Simulate call request process
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            self.showingCallRequest = false
            self.showingVideoCall = true
        }
    }

    func requestVideoCallToSelected() {
        guard !selectedDoctors.isEmpty else { return }
        
        let selectedDoctorsList = self.availableDoctors.filter { self.selectedDoctors.contains($0.id) }
        print("📞 [VideoConsultation] Requesting video call to \(selectedDoctors.count) selected doctors")
        
        requestType = .selected
        showingCallRequest = true

        // Simulate sending request to selected doctors
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
            // For demo, pick the first selected doctor as the one who responded
            if let firstSelected = selectedDoctorsList.first {
                self.selectedDoctor = firstSelected
                self.showingCallRequest = false
                self.showingVideoCall = true
            }
        }
    }

    func requestVideoCallToAll() {
        print("📞 [VideoConsultation] Requesting video call to all \(self.availableDoctors.count) available doctors")
        
        requestType = .all
        showingCallRequest = true

        // Simulate sending request to all doctors
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            // For demo, pick a random available doctor as the one who responded
            if let randomDoctor = self.availableDoctors.randomElement() {
                self.selectedDoctor = randomDoctor
                self.showingCallRequest = false
                self.showingVideoCall = true
            }
        }
    }

    func cancelVideoCallRequest() {
        print("❌ [VideoConsultation] Video call request cancelled")
        showingCallRequest = false
        selectedDoctor = nil
        requestType = .individual
    }
}

#Preview {
    VideoConsultationView()
}
