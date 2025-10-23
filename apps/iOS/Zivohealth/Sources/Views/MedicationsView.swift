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
                    
                    // Grouped Prescriptions List Card
                    PrescriptionGroupsCard(
                        groups: viewModel.groups,
                        isLoading: viewModel.isLoading,
                        error: viewModel.error,
                        onRefresh: {
                            Task { await viewModel.loadPrescriptions() }
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

// MARK: - Grouped Prescriptions Card
struct PrescriptionGroupsCard: View {
    let groups: [PrescriptionGroup]
    let isLoading: Bool
    let error: String?
    let onRefresh: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                Image(systemName: "clipboard.text")
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
                HStack { Spacer(); ProgressView(); Spacer() }
                    .padding(.vertical, 24)
            } else if let error = error {
                VStack(spacing: 8) {
                    Text("Error loading prescriptions").font(.headline).foregroundColor(.secondary)
                    Text(error).font(.caption).foregroundColor(.secondary)
                    Button("Try Again", action: onRefresh).font(.caption).foregroundColor(.blue)
                }.frame(maxWidth: .infinity).padding(.vertical, 20)
            } else if groups.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "pills.circle").font(.system(size: 40)).foregroundColor(.gray)
                    Text("No Prescriptions Yet").font(.headline).foregroundColor(.secondary)
                    Text("Your prescriptions from doctor consultations will appear here")
                        .font(.caption).foregroundColor(.secondary).multilineTextAlignment(.center)
                }.frame(maxWidth: .infinity).padding(.vertical, 20)
            } else {
                VStack(spacing: 16) {
                    ForEach(groups, id: \.id) { group in
                        NavigationLink(destination: PrescriptionGroupDetailPage(group: group)) {
                            PrescriptionGroupCard(group: group)
                        }
                        .buttonStyle(PlainButtonStyle())
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

// MARK: - Prescription Group Card (Top Level)
struct PrescriptionGroupCard: View {
    let group: PrescriptionGroup
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header with doctor name
            HStack(alignment: .top, spacing: 12) {
                // Orange pills icon
                ZStack {
                    Circle()
                        .fill(Color.orange.opacity(0.2))
                        .frame(width: 44, height: 44)
                    
                    Image(systemName: "pills.fill")
                        .foregroundColor(.orange)
                        .font(.title3)
                }
                
                VStack(alignment: .leading, spacing: 4) {
                    Text("Dr. \(group.doctorName)")
                        .font(.headline)
                        .fontWeight(.semibold)
                        .lineLimit(2)
                    
                    if let date = group.prescribedAt {
                        Text(DateFormatter.prescriptionDateShort.string(from: date) + " at " + DateFormatter.prescriptionTime.string(from: date))
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                Spacer()
                
                Image(systemName: "chevron.right")
                    .foregroundColor(.secondary)
                    .font(.caption)
            }
            
                Divider()
                
                // List of medications (bullet points)
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(group.medications) { medication in
                        HStack(alignment: .top, spacing: 8) {
                            Text("•")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                            
                            VStack(alignment: .leading, spacing: 4) {
                                Text(medication.medicationName)
                                    .font(.subheadline)
                                    .fontWeight(.medium)
                                
                                if !medication.dosage.isEmpty || !medication.frequency.isEmpty {
                                    HStack(spacing: 8) {
                                        if !medication.dosage.isEmpty {
                                            HStack(spacing: 4) {
                                                Image(systemName: "pills")
                                                    .font(.caption2)
                                                    .foregroundColor(.blue)
                                                Text(medication.dosage)
                                                    .font(.caption)
                                                    .foregroundColor(.blue)
                                            }
                                        }
                                        
                                        if !medication.frequency.isEmpty {
                                            HStack(spacing: 4) {
                                                Image(systemName: "clock")
                                                    .font(.caption2)
                                                    .foregroundColor(.green)
                                                Text(medication.frequency)
                                                    .font(.caption)
                                                    .foregroundColor(.green)
                                            }
                                        }
                                    }
                                }
                            }
                            
                            Spacer()
                        }
                    }
                }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color(.systemGray5), lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.03), radius: 2, x: 0, y: 1)
    }
}

// MARK: - Individual Prescription Card
struct IndividualPrescriptionCard: View {
    let medication: PrescriptionMedication
    let doctorName: String
    let prescribedAt: Date?
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack(alignment: .top, spacing: 12) {
                // Orange pill icon
                ZStack {
                    Circle()
                        .fill(Color.orange.opacity(0.2))
                        .frame(width: 44, height: 44)
                    
                    Image(systemName: "pills.fill")
                        .foregroundColor(.orange)
                        .font(.title3)
                }
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(medication.medicationName)
                        .font(.headline)
                        .fontWeight(.semibold)
                        .lineLimit(2)
                    
                    if let date = prescribedAt {
                        Text("Prescribed: \(DateFormatter.prescriptionDateShort.string(from: date))")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                Spacer()
                
                Image(systemName: "chevron.right")
                    .foregroundColor(.secondary)
                    .font(.caption)
            }
            
            // Quantity and Frequency
            HStack(alignment: .top, spacing: 0) {
                // Quantity column
                VStack(alignment: .leading, spacing: 4) {
                    Text("Quantity")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(medication.dosage.isEmpty ? "-" : medication.dosage)
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .lineLimit(2)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                
                // Frequency column
                VStack(alignment: .leading, spacing: 4) {
                    Text("Frequency")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(medication.frequency.isEmpty ? "-" : medication.frequency)
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .lineLimit(2)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color(.systemGray5), lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.03), radius: 2, x: 0, y: 1)
    }
}

struct PrescriptionGroupRow: View {
    let group: PrescriptionGroup
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header with doctor name and date
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: "pills.fill")
                    .foregroundColor(.orange)
                    .font(.title2)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(group.doctorName)
                        .font(.headline)
                        .fontWeight(.semibold)
                    
                    if let date = group.prescribedAt {
                        Text(DateFormatter.prescriptionDate.string(from: date))
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                Spacer()
                
                Image(systemName: "chevron.right")
                    .foregroundColor(.secondary)
                    .font(.caption)
            }
            
            // Divider
            Divider()
            
            // List all medications with dosage and frequency
            VStack(alignment: .leading, spacing: 10) {
                ForEach(group.medications) { med in
                    HStack(alignment: .top, spacing: 8) {
                        // Bullet point
                        Text("•")
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .padding(.top, 2)
                        
                        VStack(alignment: .leading, spacing: 4) {
                            // Medication name
                            Text(med.medicationName)
                                .font(.subheadline)
                                .fontWeight(.medium)
                            
                            // Dosage and frequency
                            if !med.dosage.isEmpty || !med.frequency.isEmpty {
                                HStack(spacing: 8) {
                                    if !med.dosage.isEmpty {
                                        HStack(spacing: 4) {
                                            Image(systemName: "pills")
                                                .font(.caption2)
                                                .foregroundColor(.blue)
                                            Text(med.dosage)
                                                .font(.caption)
                                                .foregroundColor(.blue)
                                        }
                                        .padding(.horizontal, 6)
                                        .padding(.vertical, 3)
                                        .background(Color.blue.opacity(0.1))
                                        .cornerRadius(4)
                                    }
                                    
                                    if !med.frequency.isEmpty {
                                        HStack(spacing: 4) {
                                            Image(systemName: "clock")
                                                .font(.caption2)
                                                .foregroundColor(.green)
                                            Text(med.frequency)
                                                .font(.caption)
                                                .foregroundColor(.green)
                                        }
                                        .padding(.horizontal, 6)
                                        .padding(.vertical, 3)
                                        .background(Color.green.opacity(0.1))
                                        .cornerRadius(4)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 5, x: 0, y: 2)
    }
}

// MARK: - Individual Medication Detail View
struct PrescriptionMedicationDetailView: View {
    let medication: PrescriptionMedication
    let group: PrescriptionGroup
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 20) {
                    // Medication Icon
                    ZStack {
                        Circle()
                            .fill(Color.orange.opacity(0.2))
                            .frame(width: 80, height: 80)
                        
                        Image(systemName: "pills.fill")
                            .foregroundColor(.orange)
                            .font(.system(size: 40))
                    }
                    .padding(.top)
                    
                    // Medication Name
                    Text(medication.medicationName)
                        .font(.title2)
                        .fontWeight(.bold)
                        .multilineTextAlignment(.center)
                    
                    // Prescribed By
                    Text("Prescribed by \(group.doctorName)")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    if let date = group.prescribedAt {
                        Text(DateFormatter.prescriptionDate.string(from: date))
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    
                    Divider()
                        .padding(.horizontal)
                    
                    // Details Card
                    VStack(alignment: .leading, spacing: 16) {
                        // Quantity/Dosage
                        MedicationInfoRow(
                            title: "Quantity",
                            value: medication.dosage.isEmpty ? "Not specified" : medication.dosage,
                            icon: "pills"
                        )
                        
                        Divider()
                        
                        // Frequency
                        MedicationInfoRow(
                            title: "Frequency",
                            value: medication.frequency.isEmpty ? "Not specified" : medication.frequency,
                            icon: "clock"
                        )
                        
                        if !medication.instructions.isEmpty {
                            Divider()
                            
                            VStack(alignment: .leading, spacing: 8) {
                                HStack {
                                    Image(systemName: "note.text")
                                        .foregroundColor(.blue)
                                        .frame(width: 24)
                                    Text("Instructions")
                                        .font(.subheadline)
                                        .fontWeight(.semibold)
                                }
                                
                                Text(medication.instructions)
                                    .font(.body)
                                    .foregroundColor(.secondary)
                                    .padding(.leading, 32)
                            }
                        }
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(12)
                    .padding(.horizontal)
                    
                    // View Prescription Document (if available)
                    if let link = group.prescriptionImageLink, !link.isEmpty {
                        NavigationLink(destination: PrescriptionFileViewer(urlString: link)) {
                            HStack {
                                Image(systemName: "doc.text.fill")
                                    .foregroundColor(.blue)
                                Text("View Prescription Document")
                                    .font(.subheadline)
                                    .fontWeight(.medium)
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            .padding()
                            .background(Color(.systemBackground))
                            .cornerRadius(12)
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(Color(.systemGray5), lineWidth: 1)
                            )
                        }
                        .padding(.horizontal)
                    }
                    
                    Spacer()
                }
                .padding(.bottom, 20)
            }
            .background(Color(.systemGroupedBackground))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
}

struct MedicationInfoRow: View {
    let title: String
    let value: String
    let icon: String
    
    var body: some View {
        HStack(alignment: .top) {
            Image(systemName: icon)
                .foregroundColor(.blue)
                .frame(width: 24)
            
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text(value)
                    .font(.body)
                    .fontWeight(.medium)
            }
            
            Spacer()
        }
    }
}

// MARK: - Prescription Group Detail Page
struct PrescriptionGroupDetailPage: View {
    let group: PrescriptionGroup
    @State private var selectedMedication: PrescriptionMedication?
    @State private var showingDocumentViewer = false
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Doctor Header Card
                VStack(spacing: 12) {
                    // Doctor Icon
                    ZStack {
                        Circle()
                            .fill(Color.blue.opacity(0.2))
                            .frame(width: 60, height: 60)
                        
                        Image(systemName: "stethoscope")
                            .foregroundColor(.blue)
                            .font(.system(size: 28))
                    }
                    
                    Text("Dr. \(group.doctorName)")
                        .font(.title3)
                        .fontWeight(.bold)
                    
                    if let date = group.prescribedAt {
                        Text("Prescribed on " + DateFormatter.prescriptionDate.string(from: date))
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(12)
                .padding(.horizontal)
                .padding(.top)
                
                // View Prescription Document Button
                if let link = group.prescriptionImageLink, !link.isEmpty {
                    Button(action: {
                        showingDocumentViewer = true
                    }) {
                        HStack {
                            Image(systemName: "doc.text.fill")
                                .foregroundColor(.white)
                                .font(.title3)
                            
                            VStack(alignment: .leading, spacing: 4) {
                                Text("View Prescription Document")
                                    .font(.subheadline)
                                    .fontWeight(.semibold)
                                    .foregroundColor(.white)
                                Text("Tap to view PDF or Image")
                                    .font(.caption)
                                    .foregroundColor(.white.opacity(0.9))
                            }
                            
                            Spacer()
                            
                            Image(systemName: "arrow.right.circle.fill")
                                .foregroundColor(.white)
                                .font(.title3)
                        }
                        .padding()
                        .background(
                            LinearGradient(
                                gradient: Gradient(colors: [Color.blue, Color.blue.opacity(0.8)]),
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .cornerRadius(12)
                    }
                    .padding(.horizontal)
                    .sheet(isPresented: $showingDocumentViewer) {
                        NavigationView {
                            PrescriptionFileViewer(urlString: link)
                        }
                    }
                } else {
                    // Show placeholder when no document is uploaded
                    VStack(spacing: 8) {
                        HStack {
                            Image(systemName: "doc.text")
                                .foregroundColor(.gray)
                                .font(.title3)
                            
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Prescription Document")
                                    .font(.subheadline)
                                    .fontWeight(.semibold)
                                    .foregroundColor(.primary)
                                Text("No document uploaded")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            
                            Spacer()
                        }
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(12)
                    }
                    .padding(.horizontal)
                }
                
                // Medications Section
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Image(systemName: "pills.fill")
                            .foregroundColor(.orange)
                        Text("Medications (\(group.medications.count))")
                            .font(.headline)
                            .fontWeight(.bold)
                    }
                    .padding(.horizontal)
                    
                    VStack(spacing: 12) {
                        ForEach(group.medications) { medication in
                            IndividualPrescriptionCard(
                                medication: medication,
                                doctorName: group.doctorName,
                                prescribedAt: group.prescribedAt
                            )
                            .onTapGesture {
                                selectedMedication = medication
                            }
                        }
                    }
                    .padding(.horizontal)
                }
                
                Spacer(minLength: 20)
            }
            .padding(.bottom, 20)
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("Prescription Details")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(item: $selectedMedication) { medication in
            PrescriptionMedicationDetailView(medication: medication, group: group)
        }
    }
}

struct PrescriptionGroupDetailView: View, Identifiable {
    var id: String { group.id }
    let group: PrescriptionGroup
    
    var body: some View {
        NavigationView {
            List {
                if let link = group.prescriptionImageLink, !link.isEmpty {
                    Section(header: Text("Prescription Document")) {
                        NavigationLink(destination: PrescriptionFileViewer(urlString: link)) {
                            HStack { Image(systemName: "doc.text"); Text("View uploaded prescription") }
                        }
                    }
                }
                Section(header: Text("Medications")) {
                    ForEach(group.medications) { med in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(med.medicationName).font(.headline)
                            if !med.dosage.isEmpty || !med.frequency.isEmpty {
                                Text("\(med.dosage)\(med.dosage.isEmpty || med.frequency.isEmpty ? "" : ", ")\(med.frequency)")
                                    .font(.caption).foregroundColor(.secondary)
                            }
                            if !med.instructions.isEmpty {
                                Text(med.instructions).font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                }
            }
            .navigationTitle(group.doctorName)
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

struct PrescriptionFileViewer: View {
    let urlString: String
    @State private var isLoading = true
    @State private var loadError = false
    
    private var isPDF: Bool {
        guard let url = URL(string: urlString) else { return false }
        return url.pathExtension.lowercased() == "pdf"
    }
    
    var body: some View {
        VStack {
            if let url = URL(string: urlString) {
                if isPDF {
                    // PDF Viewer
                    ZStack {
                        PDFKitRepresentable(url: url, isLoading: $isLoading, loadError: $loadError)
                        
                        if isLoading {
                            VStack(spacing: 12) {
                                ProgressView()
                                Text("Loading prescription...")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        
                        if loadError {
                            VStack(spacing: 12) {
                                Image(systemName: "exclamationmark.triangle")
                                    .font(.largeTitle)
                                    .foregroundColor(.orange)
                                Text("Failed to load prescription")
                                    .font(.headline)
                                Text("Please check your connection and try again")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                    .multilineTextAlignment(.center)
                            }
                            .padding()
                        }
                    }
                } else {
                    // Image Viewer
                    ScrollView([.horizontal, .vertical]) {
                        AsyncImage(url: url) { phase in
                            switch phase {
                            case .success(let image):
                                image
                                    .resizable()
                                    .scaledToFit()
                            case .failure:
                                VStack(spacing: 12) {
                                    Image(systemName: "exclamationmark.triangle")
                                        .font(.largeTitle)
                                        .foregroundColor(.orange)
                                    Text("Failed to load prescription")
                                        .font(.headline)
                                    Text("Please check your connection and try again")
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                        .multilineTextAlignment(.center)
                                }
                                .padding()
                            case .empty:
                                VStack(spacing: 12) {
                                    ProgressView()
                                    Text("Loading prescription...")
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                            @unknown default:
                                EmptyView()
                            }
                        }
                    }
                }
            } else {
                VStack(spacing: 12) {
                    Image(systemName: "doc.badge.ellipsis")
                        .font(.largeTitle)
                        .foregroundColor(.gray)
                    Text("Invalid prescription link")
                        .font(.headline)
                }
                .padding()
            }
        }
        .navigationTitle("Prescription")
        .navigationBarTitleDisplayMode(.inline)
    }
}

import PDFKit
struct PDFKitRepresentable: UIViewRepresentable {
    let url: URL
    @Binding var isLoading: Bool
    @Binding var loadError: Bool
    
    func makeUIView(context: Context) -> PDFView {
        let pdfView = PDFView()
        pdfView.autoScales = true
        pdfView.displayMode = .singlePageContinuous
        pdfView.displayDirection = .vertical
        
        // Load PDF asynchronously
        DispatchQueue.global(qos: .userInitiated).async {
            if let document = PDFDocument(url: url) {
                DispatchQueue.main.async {
                    pdfView.document = document
                    isLoading = false
                }
            } else {
                DispatchQueue.main.async {
                    isLoading = false
                    loadError = true
                }
            }
        }
        
        return pdfView
    }
    
    func updateUIView(_ uiView: PDFView, context: Context) {
        // no-op
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
        @Published var groups: [PrescriptionGroup] = []
    @Published var isLoading = false
    @Published var error: String?
    
    private let networkService = NetworkService.shared
    
    func loadPrescriptions() async {
        isLoading = true
        error = nil
        
        do {
                async let flatTask = networkService.getPatientPrescriptions()
                async let groupTask = networkService.getPrescriptionGroups()
                let (fetchedPrescriptions, fetchedGroups) = try await (flatTask, groupTask)
                prescriptions = fetchedPrescriptions.sorted { $0.prescribedAt > $1.prescribedAt }
                groups = fetchedGroups.sorted { ($0.prescribedAt ?? .distantPast) > ($1.prescribedAt ?? .distantPast) }
                print("✅ [MedicationsViewModel] Loaded \(prescriptions.count) prescriptions; groups=\(groups.count)")
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

// MARK: - Date Formatter Extensions
extension DateFormatter {
    static let prescriptionDateShort: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM dd, yyyy"
        return formatter
    }()
    
    static let prescriptionTime: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "h:mm a"
        return formatter
    }()
} 