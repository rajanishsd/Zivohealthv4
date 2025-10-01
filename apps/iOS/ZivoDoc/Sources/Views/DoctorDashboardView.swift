import SwiftUI

struct DoctorDashboardView: View {
    @StateObject private var viewModel = DoctorDashboardViewModel()
    @State private var selectedConsultation: ConsultationRequestResponse?
    @State private var showingConsultationDetail = false
    @State private var showingRoleSelection = false
    @AppStorage("userMode") private var userMode: UserMode = .doctor
    let onSwitchRole: () -> Void

    private func createConsultationWithDoctor(from consultation: ConsultationRequestResponse) -> ConsultationRequestWithDoctor {
        let doctor = Doctor(
            id: consultation.doctorId,
            fullName: "Current Doctor",
            specialization: "General Medicine",
            yearsExperience: 5,
            rating: 4.5,
            totalConsultations: 100,
            bio: "Current treating doctor",
            isAvailable: true
        )
        
        return ConsultationRequestWithDoctor(
            id: consultation.id,
            userId: consultation.userId,
            doctorId: consultation.doctorId,
            chatSessionId: consultation.chatSessionId,
            clinicalReportId: consultation.clinicalReportId,
            context: consultation.context,
            userQuestion: consultation.userQuestion,
            status: consultation.status,
            urgencyLevel: consultation.urgencyLevel,
            createdAt: consultation.createdAt,
            acceptedAt: consultation.acceptedAt,
            completedAt: consultation.completedAt,
            doctorNotes: consultation.doctorNotes,
            doctor: doctor
        )
    }

    var body: some View {
        VStack(spacing: 0) {
            // Header Stats
            DoctorStatsHeaderView(viewModel: viewModel)

            // Consultation Requests List
            ScrollView {
                LazyVStack(spacing: 16) {
                    ForEach(viewModel.visibleConsultationRequests) { request in
                        ConsultationRequestCard(
                            request: request,
                            onAccept: {
                                viewModel.acceptConsultationRequest(request.id) {
                                    // After successful acceptance, show the detail view
                                    selectedConsultation = request
                                    showingConsultationDetail = true
                                }
                            },
                            onReject: {
                                viewModel.rejectConsultationRequest(request.id)
                            },
                            onDelete: {
                                viewModel.hideConsultationRequest(request.id)
                            }
                        )
                        .onTapGesture {
                            // Allow tapping on accepted and completed consultations to view details
                            if request.status.lowercased() == "accepted" || request.status.lowercased() == "completed" {
                                selectedConsultation = request
                                showingConsultationDetail = true
                            }
                        }
                    }
                }
                .padding(.horizontal)
                .padding(.bottom, 20)
            }
            .refreshable {
                viewModel.loadConsultationRequests()
            }
        }
        .navigationTitle("Doctor Dashboard")
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                // Menu with other actions - 3 dots
                Menu {
                    Button(action: {
                        viewModel.clearAllHiddenRequests()
                    }) {
                        Label("Show All Hidden Requests", systemImage: "eye")
                    }
                    
                    Button(action: {
                        viewModel.loadConsultationRequests()
                    }) {
                        Label("Refresh", systemImage: "arrow.clockwise")
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                        .font(.title2)
                        .foregroundColor(.blue)
                }
            }
        }
        .onAppear {
            if userMode != .doctor {
                userMode = .doctor
                NetworkService.shared.handleRoleChange()
            }
            viewModel.loadConsultationRequests()
        }
        .sheet(isPresented: $showingConsultationDetail) {
            if let consultation = selectedConsultation {
                ConsultationDetailView(consultationRequest: createConsultationWithDoctor(from: consultation))
            }
        }
        .sheet(isPresented: $showingRoleSelection) {
            RoleSelectionSheet(
                currentRole: userMode,
                onRoleSelected: { newRole in
                    userMode = newRole
                    NetworkService.shared.handleRoleChange()
                    showingRoleSelection = false
                }
            )
        }
        .overlay(
            Group {
                if viewModel.isLoading {
                    ProgressView("Loading consultation requests...")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .background(Color(.systemBackground).opacity(0.8))
                }
                
                if let error = viewModel.error {
                    VStack {
                        Text("❌ \(error)")
                            .font(.caption)
                            .foregroundColor(.red)
                            .multilineTextAlignment(.center)
                            .padding()

                        Button("Retry") {
                            viewModel.loadConsultationRequests()
                        }
                        .font(.caption)
                        .foregroundColor(.blue)
                    }
                    .background(Color(.systemBackground))
                    .cornerRadius(8)
                    .padding()
                }
            }
        )
    }
}

struct ConsultationRequestCard: View {
    let request: ConsultationRequestResponse
    let onAccept: () -> Void
    let onReject: () -> Void
    let onDelete: (() -> Void)?
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header with context menu indicator
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Request #\(request.id)")
                        .font(Font.headline.weight(.semibold))

                    Text("Status: \(request.status.capitalized)")
                        .font(.subheadline)
                        .foregroundColor(statusColor)
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 4) {
                    HStack(spacing: 8) {
                        Text(request.urgencyLevel.capitalized)
                            .font(.caption)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(urgencyColor)
                            .foregroundColor(.white)
                            .cornerRadius(8)
                        
                        // Context menu indicator
                        if onDelete != nil {
                            Image(systemName: "ellipsis")
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .padding(4)
                                .background(Color(.systemGray5))
                                .clipShape(Circle())
                        }
                    }

                    Text(request.createdAt.formatted(date: .abbreviated, time: .shortened))
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }

            // Patient Question
            VStack(alignment: .leading, spacing: 6) {
                Text("Patient Question:")
                    .font(Font.subheadline.weight(.medium))
                    .foregroundColor(.primary)

                Text(request.userQuestion)
                    .font(.body)
                    .foregroundColor(.secondary)
                    .lineLimit(3)
            }

            // Action buttons (only show for pending requests)
            if request.status.lowercased() == "pending" {
                HStack(spacing: 12) {
                    Button(action: onReject) {
                        HStack {
                            Image(systemName: "xmark")
                            Text("Decline")
                        }
                        .font(.subheadline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(Color.red)
                        .cornerRadius(12)
                    }

                    Button(action: onAccept) {
                        HStack {
                            Image(systemName: "checkmark")
                            Text("Accept")
                        }
                        .font(.subheadline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(Color.green)
                        .cornerRadius(12)
                    }
                }
            } else {
                // Show status for non-pending requests
                HStack {
                    Image(systemName: statusIcon)
                        .foregroundColor(statusColor)
                    Text("Request \(request.status.capitalized)")
                        .font(Font.subheadline.weight(.medium))
                        .foregroundColor(statusColor)
                    
                    Spacer()
                    
                    if request.status.lowercased() == "accepted" || request.status.lowercased() == "completed" {
                        Text("Tap to view details")
                            .font(.caption)
                            .foregroundColor(.blue)
                    }
                }
                .padding(.vertical, 8)
            }
            
            // Help text for context menu
            if onDelete != nil {
                HStack {
                    Image(systemName: "hand.tap")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text("Long press to hide request")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Spacer()
                }
                .padding(.top, 4)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: Color.black.opacity(0.1), radius: 8, x: 0, y: 2)
        .contextMenu {
            if let onDelete = onDelete {
                Button(action: onDelete) {
                    Label("Hide Request", systemImage: "eye.slash")
                }
                .foregroundColor(.red)
                
                Button(action: {
                    // Copy request ID for reference
                    UIPasteboard.general.string = "Request #\(request.id)"
                }) {
                    Label("Copy Request ID", systemImage: "doc.on.doc")
                }
            }
        }
    }

    private var statusColor: Color {
        switch request.status.lowercased() {
        case "pending": return .orange
        case "accepted": return .green
        case "completed": return .blue
        case "rejected": return .red
        default: return .gray
        }
    }
    
    private var statusIcon: String {
        switch request.status.lowercased() {
        case "pending": return "clock"
        case "accepted": return "checkmark.circle"
        case "completed": return "checkmark.circle.fill"
        case "rejected": return "xmark.circle"
        default: return "questionmark.circle"
        }
    }

    private var urgencyColor: Color {
        switch request.urgencyLevel.lowercased() {
        case "urgent": return .red
        case "high": return .orange
        case "normal": return .blue
        case "low": return .gray
        default: return .blue
        }
    }
}

// MARK: - Doctor Stats Header
struct DoctorStatsHeaderView: View {
    @ObservedObject var viewModel: DoctorDashboardViewModel
    
    var body: some View {
        VStack(spacing: 16) {
            HStack(spacing: 20) {
                StatCard(
                    title: "Pending",
                    count: viewModel.pendingCount,
                    color: .orange,
                    icon: "clock"
                )
                
                StatCard(
                    title: "Accepted",
                    count: viewModel.acceptedCount,
                    color: .green,
                    icon: "checkmark.circle"
                )
                
                StatCard(
                    title: "Completed",
                    count: viewModel.completedCount,
                    color: .blue,
                    icon: "checkmark.circle.fill"
                )
            }
            .padding(.horizontal)
        }
        .padding(.vertical)
        .background(Color(.systemGray6))
    }
}

struct StatCard: View {
    let title: String
    let count: Int
    let color: Color
    let icon: String
    
    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(color)
            
            Text("\(count)")
                .font(.title2)
                .fontWeight(.bold)
                .foregroundColor(.primary)
            
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(Color(.systemBackground))
        .cornerRadius(12)
    }
}

// Role Selection Sheet for quick switching
struct RoleSelectionSheet: View {
    let currentRole: UserMode
    let onRoleSelected: (UserMode) -> Void
    @Environment(\.presentationMode) var presentationMode
    @State private var selectedRole: UserMode
    
    init(currentRole: UserMode, onRoleSelected: @escaping (UserMode) -> Void) {
        self.currentRole = currentRole
        self.onRoleSelected = onRoleSelected
        self._selectedRole = State(initialValue: currentRole)
    }
    
    var body: some View {
        NavigationView {
            VStack(spacing: 30) {
                // Header
                VStack(spacing: 16) {
                    Image(systemName: "arrow.triangle.2.circlepath.circle.fill")
                        .font(.system(size: 60))
                        .foregroundColor(.blue)
                    
                    Text("Switch Role")
                        .font(.title2)
                        .fontWeight(.semibold)
                    
                    Text("Current: \(currentRole == .patient ? "Patient" : "Doctor")")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                
                // Role Options
                VStack(spacing: 16) {
                    RoleOptionCard(
                        role: .patient,
                        title: "Patient",
                        subtitle: "Access healthcare services",
                        icon: "person.circle.fill",
                        isSelected: selectedRole == .patient
                    ) {
                        selectedRole = .patient
                    }
                    
                    RoleOptionCard(
                        role: .doctor,
                        title: "Doctor",
                        subtitle: "Manage patient consultations",
                        icon: "stethoscope.circle.fill",
                        isSelected: selectedRole == .doctor
                    ) {
                        selectedRole = .doctor
                    }
                }
                
                Spacer()
                
                // Switch Button
                if selectedRole != currentRole {
                    Button(action: {
                        onRoleSelected(selectedRole)
                    }) {
                        HStack {
                            Text("Switch to \(selectedRole == .patient ? "Patient" : "Doctor")")
                            Image(systemName: "arrow.right")
                        }
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.blue)
                        .cornerRadius(12)
                    }
                    .padding(.horizontal)
                }
            }
            .padding()
            .navigationTitle("Switch Role")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Cancel") {
                        presentationMode.wrappedValue.dismiss()
                    }
                }
            }
        }
    }
}

// Role Option Card for the sheet
struct RoleOptionCard: View {
    let role: UserMode
    let title: String
    let subtitle: String
    let icon: String
    let isSelected: Bool
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 16) {
                Image(systemName: icon)
                    .font(.title2)
                    .foregroundColor(isSelected ? .white : .blue)
                    .frame(width: 40)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.headline)
                        .foregroundColor(isSelected ? .white : .primary)
                    
                    Text(subtitle)
                        .font(.subheadline)
                        .foregroundColor(isSelected ? .white.opacity(0.8) : .secondary)
                }
                
                Spacer()
                
                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.title2)
                        .foregroundColor(.white)
                }
            }
            .padding()
            .background(isSelected ? Color.blue : Color(.systemGray6))
            .cornerRadius(12)
        }
        .buttonStyle(PlainButtonStyle())
    }
}

@MainActor
class DoctorDashboardViewModel: ObservableObject {
    @Published var consultationRequests: [ConsultationRequestResponse] = []
    @Published var isLoading = false
    @Published var error: String?

    private let networkService = NetworkService.shared
    private let hiddenRequestsKey = "hidden_consultation_requests"
    
    // MARK: - Hidden Requests Management
    private var hiddenRequestIds: Set<Int> {
        get {
            let array = UserDefaults.standard.array(forKey: hiddenRequestsKey) as? [Int] ?? []
            return Set(array)
        }
        set {
            UserDefaults.standard.set(Array(newValue), forKey: hiddenRequestsKey)
        }
    }
    
    // Filter out hidden requests for display
    var visibleConsultationRequests: [ConsultationRequestResponse] {
        consultationRequests.filter { !hiddenRequestIds.contains($0.id) }
    }
    
    // MARK: - Computed Properties for Stats
    var pendingCount: Int {
        visibleConsultationRequests.filter { $0.status.lowercased() == "pending" }.count
    }
    
    var acceptedCount: Int {
        visibleConsultationRequests.filter { $0.status.lowercased() == "accepted" }.count
    }
    
    var completedCount: Int {
        visibleConsultationRequests.filter { $0.status.lowercased() == "completed" }.count
    }

    func loadConsultationRequests() {
        print("🏥 [DoctorDashboardViewModel] Loading consultation requests")
        
        isLoading = true
        error = nil

        Task {
            do {
                let requests = try await networkService.getDoctorConsultationRequests()
                await MainActor.run {
                    self.consultationRequests = requests
                    self.isLoading = false
                    print("✅ [DoctorDashboardViewModel] Loaded \(requests.count) consultation requests (\(self.visibleConsultationRequests.count) visible)")
                }
            } catch {
                await MainActor.run {
                    self.error = "Failed to load consultation requests: \(error.localizedDescription)"
                    self.isLoading = false
                    print("❌ [DoctorDashboardViewModel] Error loading requests: \(error)")
                }
            }
        }
    }

    func acceptConsultationRequest(_ requestId: Int, completion: @escaping () -> Void) {
        print("✅ [DoctorDashboardViewModel] Accepting request \(requestId)")

        isLoading = true
        error = nil

        Task {
            do {
                let updatedRequest = try await networkService.updateConsultationRequestStatus(
                    requestId: requestId,
                    status: "accepted",
                    notes: nil
                )

                await MainActor.run {
                    // Update the consultation request in the list
                    if let index = consultationRequests.firstIndex(where: { $0.id == requestId }) {
                        consultationRequests[index] = updatedRequest
                    }

                    isLoading = false
                    print("✅ [DoctorDashboardViewModel] Request \(requestId) accepted successfully")
                    completion()
                }
            } catch {
                await MainActor.run {
                    self.error = "Failed to accept consultation request: \(error.localizedDescription)"
                    isLoading = false
                    print("❌ [DoctorDashboardViewModel] Error accepting request: \(error)")
                }
            }
        }
    }

    func rejectConsultationRequest(_ requestId: Int) {
        print("❌ [DoctorDashboardViewModel] Rejecting request \(requestId)")

        isLoading = true
        error = nil

        Task {
            do {
                let updatedRequest = try await networkService.updateConsultationRequestStatus(
                    requestId: requestId,
                    status: "rejected",
                    notes: nil
                )

                await MainActor.run {
                    // Update the consultation request in the list
                    if let index = consultationRequests.firstIndex(where: { $0.id == requestId }) {
                        consultationRequests[index] = updatedRequest
                    }

                    isLoading = false
                    print("✅ [DoctorDashboardViewModel] Request \(requestId) rejected successfully")
                }
            } catch {
                await MainActor.run {
                    self.error = "Failed to reject consultation request: \(error.localizedDescription)"
                    isLoading = false
                    print("❌ [DoctorDashboardViewModel] Error rejecting request: \(error)")
                }
            }
        }
    }

    func hideConsultationRequest(_ requestId: Int) {
        print("👁️‍🗨️ [DoctorDashboardViewModel] Hiding request \(requestId) from local view")
        
        var hidden = hiddenRequestIds
        hidden.insert(requestId)
        hiddenRequestIds = hidden
        
        // Trigger UI update
        objectWillChange.send()
        
        print("✅ [DoctorDashboardViewModel] Request \(requestId) hidden from local view")
    }
    
    func unhideConsultationRequest(_ requestId: Int) {
        print("👁️ [DoctorDashboardViewModel] Unhiding request \(requestId)")
        
        var hidden = hiddenRequestIds
        hidden.remove(requestId)
        hiddenRequestIds = hidden
        
        // Trigger UI update
        objectWillChange.send()
        
        print("✅ [DoctorDashboardViewModel] Request \(requestId) unhidden")
    }
    
    func clearAllHiddenRequests() {
        hiddenRequestIds = Set<Int>()
        objectWillChange.send()
        print("🗑️ [DoctorDashboardViewModel] Cleared all hidden requests")
    }
}

#Preview {
    DoctorDashboardView(onSwitchRole: {})
}
