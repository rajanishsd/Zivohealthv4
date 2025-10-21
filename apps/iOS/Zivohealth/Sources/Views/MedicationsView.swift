import SwiftUI
import Combine

struct MedicationsView: View {
    var body: some View {
        if #available(iOS 16.0, *) {
            MedicationsViewModern()
        } else {
            MedicationsViewLegacy()
        }
    }
}

// MARK: - Modern iOS 16+ View
@available(iOS 16.0, *)
struct MedicationsViewModern: View {
    @StateObject private var viewModel = MedicationsViewModel()
    @State private var navigateToUploadPrescription = false
    
    var body: some View {
        GeometryReader { geometry in
            ScrollView {
                VStack(spacing: 0) {
                    // Scrollable header
                    MedicationsHeaderView(topInset: geometry.safeAreaInsets.top)
                
                VStack(spacing: 20) {
                    // Medications Overview Card
                    MedicationsOverviewCard(prescriptions: viewModel.prescriptions)
                    
                    // Upload Prescription button (prominent)
                    uploadPrescriptionCard
                    
                    // Active Medications Card
                    ActiveMedicationsCard(prescriptions: viewModel.prescriptions)
                    
                    // Prescriptions List Card
                    PrescriptionsListCard(
                        prescriptions: viewModel.prescriptions,
                        isLoading: viewModel.isLoading,
                        error: viewModel.error,
                        onRefresh: {
                            Task {
                                await viewModel.loadPrescriptions()
                            }
                        }
                    )
                    
                    Spacer(minLength: 100)
                }
                .padding(.horizontal)
                .padding(.top, 8)
            }
        }
        .background(Color(.systemGray6))
        .ignoresSafeArea(.container, edges: .top)
        .task {
            await viewModel.loadPrescriptions()
        }
        .refreshable {
            await viewModel.loadPrescriptions()
        }
        .background(
            NavigationLink(
                destination: UploadPrescriptionView(),
                isActive: $navigateToUploadPrescription,
                label: { EmptyView() }
            )
            .hidden()
        )
    }
    .navigationBarHidden(true)
    }
    
    private var uploadPrescriptionCard: some View {
        Button(action: { navigateToUploadPrescription = true }) {
            HStack(spacing: 8) {
                Image(systemName: "doc.badge.plus")
                    .font(.title3)
                Text("Upload Prescription")
                    .font(.headline)
                    .fontWeight(.semibold)
            }
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(Color.green)
            .cornerRadius(12)
        }
        .buttonStyle(.plain)
        .padding(.horizontal)
    }
}

// MARK: - Legacy iOS 15 View
struct MedicationsViewLegacy: View {
    @StateObject private var viewModel = MedicationsViewModel()
    @State private var navigateToUploadPrescription = false
    
    var body: some View {
        GeometryReader { geometry in
            ScrollView {
                VStack(spacing: 0) {
                    // Scrollable header
                    MedicationsHeaderView(topInset: geometry.safeAreaInsets.top)
                
                VStack(spacing: 20) {
                    // Medications Overview Card
                    MedicationsOverviewCard(prescriptions: viewModel.prescriptions)
                    
                    // Upload Prescription button (prominent)
                    uploadPrescriptionCard
                    
                    // Active Medications Card
                    ActiveMedicationsCard(prescriptions: viewModel.prescriptions)
                    
                    // Prescriptions List Card
                    PrescriptionsListCard(
                        prescriptions: viewModel.prescriptions,
                        isLoading: viewModel.isLoading,
                        error: viewModel.error,
                        onRefresh: {
                            Task {
                                await viewModel.loadPrescriptions()
                            }
                        }
                    )
                    
                    Spacer(minLength: 100)
                }
                .padding(.horizontal)
                .padding(.top, 8)
            }
        }
        .background(Color(.systemGray6))
        .ignoresSafeArea(.container, edges: .top)
        .onAppear {
            Task {
                await viewModel.loadPrescriptions()
            }
        }
        .background(
            NavigationLink(
                destination: UploadPrescriptionView(),
                isActive: $navigateToUploadPrescription,
                label: { EmptyView() }
            )
            .hidden()
        )
    }
    .navigationBarHidden(true)
    }
    
    private var uploadPrescriptionCard: some View {
        Button(action: { navigateToUploadPrescription = true }) {
            HStack(spacing: 8) {
                Image(systemName: "doc.badge.plus")
                    .font(.title3)
                Text("Upload Prescription")
                    .font(.headline)
                    .fontWeight(.semibold)
            }
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(Color.green)
            .cornerRadius(12)
        }
        .buttonStyle(.plain)
        .padding(.horizontal)
    }
}

// MARK: - Medications Overview Card
struct MedicationsOverviewCard: View {
    let prescriptions: [PrescriptionWithSession]
    
    private var activeMedications: [PrescriptionWithSession] {
        // Consider medications prescribed within the last 90 days as potentially active
        let ninetyDaysAgo = Calendar.current.date(byAdding: .day, value: -90, to: Date()) ?? Date()
        return prescriptions.filter { $0.prescribedAt >= ninetyDaysAgo }
    }
    
    private var totalMedications: Int {
        prescriptions.count
    }
    
    private var uniqueMedications: Set<String> {
        Set(prescriptions.map { $0.medicationName.lowercased() })
    }
    
    var body: some View {
        VStack(spacing: 20) {
            // Header
            HStack {
                Image(systemName: "pills.fill")
                    .foregroundColor(.blue)
                    .font(.title2)
                Text("Medications Overview")
                    .font(.title3)
                    .fontWeight(.semibold)
                Spacer()
                Text("Latest Data")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            // Statistics
            HStack(spacing: 20) {
                VStack {
                    Text("\(activeMedications.count)")
                        .font(.title)
                        .fontWeight(.bold)
                        .foregroundColor(.green)
                    Text("Active")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Divider()
                    .frame(height: 40)
                
                VStack {
                    Text("\(totalMedications)")
                        .font(.title)
                        .fontWeight(.bold)
                        .foregroundColor(.blue)
                    Text("Total")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Divider()
                    .frame(height: 40)
                
                VStack {
                    Text("\(uniqueMedications.count)")
                        .font(.title)
                        .fontWeight(.bold)
                        .foregroundColor(.purple)
                    Text("Unique")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            // Progress description
            Text(progressDescription)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.05), radius: 5, x: 0, y: 2)
    }
    
    private var progressDescription: String {
        if prescriptions.isEmpty {
            return "No prescriptions found. Your medications from doctor consultations will appear here."
        } else if !activeMedications.isEmpty {
            return "You have \(activeMedications.count) active medication\(activeMedications.count == 1 ? "" : "s") to manage."
        } else {
            return "All prescriptions are from previous consultations. Consult your doctor for current medications."
        }
    }
}

// MARK: - Active Medications Card
struct ActiveMedicationsCard: View {
    let prescriptions: [PrescriptionWithSession]
    
    private var activeMedications: [PrescriptionWithSession] {
        // Consider medications prescribed within the last 90 days as potentially active
        let ninetyDaysAgo = Calendar.current.date(byAdding: .day, value: -90, to: Date()) ?? Date()
        return prescriptions.filter { $0.prescribedAt >= ninetyDaysAgo }
            .sorted { $0.prescribedAt > $1.prescribedAt }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                Image(systemName: "clock.fill")
                    .foregroundColor(.green)
                    .font(.title2)
                Text("Active Medications")
                    .font(.title3)
                    .fontWeight(.semibold)
                Spacer()
                Text("\(activeMedications.count)")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(.green)
            }
            
            if activeMedications.isEmpty {
                // Empty state
                VStack(spacing: 12) {
                    Image(systemName: "pills.circle")
                        .font(.system(size: 40))
                        .foregroundColor(.gray)
                    
                    Text("No Active Medications")
                        .font(.headline)
                        .foregroundColor(.secondary)
                    
                    Text("Medications prescribed within the last 90 days will appear here")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 20)
            } else {
                // Active medications list
                LazyVStack(spacing: 12) {
                    ForEach(activeMedications.prefix(3), id: \.id) { prescription in
                        ActiveMedicationRow(prescription: prescription)
                    }
                    
                    if activeMedications.count > 3 {
                        Text("+ \(activeMedications.count - 3) more medications")
                            .font(.caption)
                            .foregroundColor(.blue)
                            .padding(.top, 8)
                    }
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.05), radius: 5, x: 0, y: 2)
    }
}

// MARK: - Active Medication Row
struct ActiveMedicationRow: View {
    let prescription: PrescriptionWithSession
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(prescription.medicationName)
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                if !prescription.dosage.isEmpty || !prescription.frequency.isEmpty {
                    Text("\(prescription.dosage)\(prescription.dosage.isEmpty || prescription.frequency.isEmpty ? "" : ", ")\(prescription.frequency)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Text("Prescribed by \(prescription.doctorName)")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            VStack(alignment: .trailing, spacing: 4) {
                Text("Active")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(.green)
                
                Text(formatDate(prescription.prescribedAt))
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding(.vertical, 8)
        .padding(.horizontal, 12)
        .background(Color(.systemGray6))
        .cornerRadius(8)
    }
    
    private func formatDate(_ date: Date) -> String {
        let formatter = RelativeDateTimeFormatter()
        formatter.dateTimeStyle = .named
        return formatter.localizedString(for: date, relativeTo: Date())
    }
}

// MARK: - Prescriptions List Card
struct PrescriptionsListCard: View {
    let prescriptions: [PrescriptionWithSession]
    let isLoading: Bool
    let error: String?
    let onRefresh: () -> Void
    
    @State private var selectedPrescription: PrescriptionWithSession?
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                Image(systemName: "list.bullet.clipboard")
                    .foregroundColor(.blue)
                    .font(.title2)
                Text("All Prescriptions")
                    .font(.title3)
                    .fontWeight(.semibold)
                Spacer()
                Button(action: onRefresh) {
                    Image(systemName: "arrow.clockwise")
                        .foregroundColor(.blue)
                }
            }
            
            if isLoading {
                // Loading state
                HStack {
                    Spacer()
                    VStack(spacing: 12) {
                        ProgressView()
                        Text("Loading prescriptions...")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    Spacer()
                }
                .padding(.vertical, 40)
                
            } else if let error = error {
                // Error state
                VStack(spacing: 12) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.system(size: 40))
                        .foregroundColor(.orange)
                    
                    Text("Error loading prescriptions")
                        .font(.headline)
                        .foregroundColor(.secondary)
                    
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                    
                    Button("Try Again", action: onRefresh)
                        .font(.caption)
                        .foregroundColor(.blue)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 20)
                
            } else if prescriptions.isEmpty {
                // Empty state
                VStack(spacing: 12) {
                    Image(systemName: "pills.circle")
                        .font(.system(size: 40))
                        .foregroundColor(.gray)
                    
                    Text("No Prescriptions Yet")
                        .font(.headline)
                        .foregroundColor(.secondary)
                    
                    Text("Your prescriptions from doctor consultations will appear here")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 20)
                
            } else {
                // Prescriptions list
                LazyVStack(spacing: 12) {
                    ForEach(prescriptions, id: \.id) { prescription in
                        PrescriptionCard(prescription: prescription)
                            .onTapGesture {
                                selectedPrescription = prescription
                            }
                    }
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.05), radius: 5, x: 0, y: 2)
        .sheet(item: $selectedPrescription) { prescription in
            PrescriptionDetailView(prescriptionWithSession: prescription, onContinueChat: {
                selectedPrescription = nil
                // Handle chat continuation if needed
            })
        }
    }
}

// MARK: - Prescription Card
struct PrescriptionCard: View {
    let prescription: PrescriptionWithSession
    
    private var isRecent: Bool {
        let thirtyDaysAgo = Calendar.current.date(byAdding: .day, value: -30, to: Date()) ?? Date()
        return prescription.prescribedAt >= thirtyDaysAgo
    }
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 8) {
                // Medication name
                Text(prescription.medicationName)
                    .font(.headline)
                    .fontWeight(.semibold)
                
                // Dosage and frequency
                if !prescription.dosage.isEmpty || !prescription.frequency.isEmpty {
                    HStack {
                        if !prescription.dosage.isEmpty {
                            Text(prescription.dosage)
                                .font(.subheadline)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(Color.blue.opacity(0.1))
                                .foregroundColor(.blue)
                                .cornerRadius(6)
                        }
                        
                        if !prescription.frequency.isEmpty {
                            Text(prescription.frequency)
                                .font(.subheadline)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(Color.green.opacity(0.1))
                                .foregroundColor(.green)
                                .cornerRadius(6)
                        }
                    }
                }
                
                // Doctor and date
                VStack(alignment: .leading, spacing: 2) {
                    Text("Prescribed by \(prescription.doctorName)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Text(formatDate(prescription.prescribedAt))
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                // Instructions (if available)
                if !prescription.instructions.isEmpty {
                    Text(prescription.instructions)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(2)
                        .padding(.top, 4)
                }
            }
            
            Spacer()
            
            VStack {
                if isRecent {
                    Text("Recent")
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(.green)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.green.opacity(0.1))
                        .cornerRadius(6)
                }
                
                Image(systemName: "chevron.right")
                    .foregroundColor(.secondary)
                    .font(.caption)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
    
    private func formatDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .none
        return formatter.string(from: date)
    }
}

// MARK: - Medications ViewModel
@MainActor
class MedicationsViewModel: ObservableObject {
    @Published var prescriptions: [PrescriptionWithSession] = []
    @Published var isLoading = false
    @Published var error: String?
    
    private let networkService = NetworkService.shared
    
    func loadPrescriptions() async {
        isLoading = true
        error = nil
        
        do {
            let fetchedPrescriptions = try await networkService.getPatientPrescriptions()
            prescriptions = fetchedPrescriptions.sorted { $0.prescribedAt > $1.prescribedAt }
            print("✅ [MedicationsViewModel] Loaded \(prescriptions.count) prescriptions from backend")
        } catch {
            self.error = "Failed to load prescriptions: \(error.localizedDescription)"
            print("❌ [MedicationsViewModel] Error loading prescriptions: \(error)")
        }
        
        isLoading = false
    }
}

// MARK: - Medications Header
struct MedicationsHeaderView: View {
    let topInset: CGFloat
    @Environment(\.dismiss) private var dismiss
    
    private var brandRedGradient: Gradient {
        Gradient(colors: [
            Color.zivoRed,                 // darker (left)
            Color.zivoRed.opacity(0.7)     // lighter (right)
        ])
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Top spacer for status bar
            Color.clear
                .frame(height: topInset)
            
            // Card content with back button
            ZStack(alignment: .topLeading) {
                LinearGradient(
                    gradient: brandRedGradient,
                    startPoint: .leading,
                    endPoint: .trailing
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                
                ZStack {
                    // Centered title and subtitle with offset to move down
                    VStack(spacing: 4) {
                        Text("Medications")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(.white)
                        
                        Text("Manage your prescriptions and medications")
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.9))
                    }
                    .offset(y: 15)
                    
                    // Back button on the left, vertically centered
                    HStack {
                        Button(action: {
                            dismiss()
                        }) {
                            Image(systemName: "arrow.backward")
                                .font(.system(size: 20, weight: .semibold))
                                .foregroundColor(.white)
                        }
                        .padding(.leading, 20)
                        
                        Spacer()
                    }
                    .offset(y: 10)
                    
                    // Pills icon on the right, vertically centered
                    HStack {
                        Spacer()
                        
                        Image(systemName: "pills.fill")
                            .font(.system(size: 40))
                            .foregroundColor(.white.opacity(0.9))
                            .padding(.trailing, 20)
                    }
                }
                .padding(.vertical, 20)
            }
            .frame(height: 110)
            .cornerRadius(20)
            .padding(.horizontal, 16)
            .padding(.top, 8)
        }
        .frame(height: 110 + topInset + 8)
        .ignoresSafeArea(.container, edges: .top)
    }
} 