import SwiftUI

struct ConsultationDetailView: View {
    let consultationRequest: ConsultationRequestWithDoctor
    @StateObject private var viewModel = ConsultationDetailViewModel()
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Header
                    ConsultationHeaderView(request: consultationRequest, viewModel: viewModel)
                    
                    // Patient Questions Section
                    PatientQuestionsSection(request: consultationRequest)
                    
                    // AI Response Section
                    AIResponseSection(context: consultationRequest.context)
                    
                    // AI Summary Section
                    AISummarySection(
                        request: consultationRequest,
                        viewModel: viewModel
                    )
                    
                    // Doctor Response Section
                    DoctorResponseSection(viewModel: viewModel, isCompleted: consultationRequest.status == "completed")
                    
                    // Prescriptions Section
                    PrescriptionsSection(viewModel: viewModel, isCompleted: consultationRequest.status == "completed")
                    
                    // Lab Tests Section
                    LabTestsSection(viewModel: viewModel, isCompleted: consultationRequest.status == "completed")
                    
                    // Action Buttons
                    if consultationRequest.status != "completed" {
                        ActionButtonsSection(
                            viewModel: viewModel,
                            onComplete: {
                                dismiss()
                            }
                        )
                    }
                }
                .padding()
            }
            .navigationTitle("Consultation Details")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Close") {
                        dismiss()
                    }
                }
            }
        }
        .sheet(isPresented: $viewModel.showingClinicalReport) {
            if let clinicalReport = viewModel.clinicalReport {
                ClinicalReportView(clinicalReport: clinicalReport)
            }
        }
        .onAppear {
            viewModel.loadConsultation(consultationRequest)
        }
    }
}

// MARK: - Header Section
struct ConsultationHeaderView: View {
    let request: ConsultationRequestWithDoctor
    @ObservedObject var viewModel: ConsultationDetailViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Request #\(request.id)")
                        .font(.title2)
                        .fontWeight(.bold)
                    
                    Text("Status: \(request.status.capitalized)")
                        .font(.subheadline)
                        .foregroundColor(statusColor)
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 4) {
                    Text(request.urgencyLevel.capitalized)
                        .font(.caption)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(urgencyColor)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                    
                    Text(request.createdAt.formatted(date: .abbreviated, time: .shortened))
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
            
            if viewModel.hasClinicalReport {
                HStack {
                    Spacer()
                    Button(action: {
                        viewModel.loadClinicalReport()
                    }) {
                        HStack(spacing: 4) {
                            Image(systemName: "doc.text.magnifyingglass")
                            Text("Clinical History")
                        }
                        .font(.caption)
                        .foregroundColor(.blue)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.blue.opacity(0.1))
                        .cornerRadius(6)
                    }
                    .disabled(viewModel.isLoadingClinicalReport)
                }
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
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

// MARK: - Patient Questions Section
struct PatientQuestionsSection: View {
    let request: ConsultationRequestWithDoctor
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "person.fill.questionmark")
                    .foregroundColor(.blue)
                Text("Patient Questions")
                    .font(.headline)
                    .fontWeight(.semibold)
            }
            
            Text(request.userQuestion)
                .font(.body)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(12)
        }
    }
}

// MARK: - AI Response Section
struct AIResponseSection: View {
    let context: String
    @State private var isExpanded = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "brain.head.profile")
                    .foregroundColor(.purple)
                Text("AI Response & Context")
                    .font(.headline)
                    .fontWeight(.semibold)
                
                Spacer()
                
                Button(action: {
                    withAnimation {
                        isExpanded.toggle()
                    }
                }) {
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .foregroundColor(.blue)
                }
            }
            
            if isExpanded {
                ScrollView {
                    Text(context)
                        .font(.body)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(maxHeight: 300)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(12)
            }
        }
    }
}

// MARK: - AI Summary Section
struct AISummarySection: View {
    let request: ConsultationRequestWithDoctor
    @ObservedObject var viewModel: ConsultationDetailViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "doc.text.magnifyingglass")
                    .foregroundColor(.green)
                Text("AI Medical Summary")
                    .font(.headline)
                    .fontWeight(.semibold)
                
                Spacer()
                
                if !viewModel.hasSummary {
                    Button(action: {
                        viewModel.generateSummary()
                    }) {
                        HStack(spacing: 6) {
                            if viewModel.isGeneratingSummary {
                                ProgressView()
                                    .scaleEffect(0.8)
                            } else {
                                Image(systemName: "brain.head.profile")
                            }
                            Text(viewModel.isGeneratingSummary ? "Generating..." : "Generate Summary")
                        }
                        .font(.caption)
                        .foregroundColor(.white)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(viewModel.isGeneratingSummary ? Color.gray : Color.green)
                        .cornerRadius(8)
                    }
                    .disabled(viewModel.isGeneratingSummary)
                }
            }
            
            if let summary = viewModel.aiSummary {
                ScrollView {
                    Text(summary)
                        .font(.body)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .textSelection(.enabled)
                }
                .frame(maxHeight: 400)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(12)
                
                // Copy button
                HStack {
                    Spacer()
                    Button(action: {
                        UIPasteboard.general.string = summary
                        viewModel.showCopyConfirmation()
                    }) {
                        HStack(spacing: 4) {
                            Image(systemName: "doc.on.clipboard")
                            Text("Copy Summary")
                        }
                        .font(.caption)
                        .foregroundColor(.blue)
                    }
                }
            } else if !viewModel.hasSummary {
                Text("Generate an AI summary to get structured medical analysis with Questions, Proposed Solutions, and Precautions.")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(12)
            }
        }
    }
}

// MARK: - Doctor Response Section
struct DoctorResponseSection: View {
    @ObservedObject var viewModel: ConsultationDetailViewModel
    let isCompleted: Bool
    
    init(viewModel: ConsultationDetailViewModel, isCompleted: Bool = false) {
        self.viewModel = viewModel
        self.isCompleted = isCompleted
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "person.crop.circle.badge.checkmark")
                    .foregroundColor(.blue)
                Text("Doctor Response")
                    .font(.headline)
                    .fontWeight(.semibold)
                
                if isCompleted {
                    Spacer()
                    Text("Completed")
                        .font(.caption)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.blue.opacity(0.2))
                        .foregroundColor(.blue)
                        .cornerRadius(8)
                }
            }
            
            if isCompleted {
                // Read-only view for completed consultations
                ScrollView {
                    Text(viewModel.doctorResponse.isEmpty ? "No response provided" : viewModel.doctorResponse)
                        .font(.body)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .textSelection(.enabled)
                }
                .frame(minHeight: 150)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(12)
            } else {
                // Editable view for active consultations
                TextEditor(text: $viewModel.doctorResponse)
                    .frame(minHeight: 150)
                    .padding(8)
                    .background(Color(.systemGray6))
                    .cornerRadius(12)
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(Color(.systemGray4), lineWidth: 1)
                    )
                
                if viewModel.doctorResponse.isEmpty {
                    Text("Provide your professional medical response to the patient's questions...")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .padding(.horizontal, 4)
                }
            }
        }
    }
}

// MARK: - Prescriptions Section
struct PrescriptionsSection: View {
    @ObservedObject var viewModel: ConsultationDetailViewModel
    let isCompleted: Bool
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "pills")
                    .foregroundColor(.red)
                Text("Drug Prescriptions")
                    .font(.headline)
                    .fontWeight(.semibold)
                
                Spacer()
                
                if !isCompleted {
                    Button(action: viewModel.addPrescription) {
                        Image(systemName: "plus.circle.fill")
                            .foregroundColor(.blue)
                    }
                }
            }
            
            if viewModel.prescriptions.isEmpty {
                Text(isCompleted ? "No prescriptions provided." : "No prescriptions added. Click + to add medications.")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(12)
            } else {
                ForEach(viewModel.prescriptions.indices, id: \.self) { index in
                    if isCompleted {
                        ReadOnlyPrescriptionCard(prescription: viewModel.prescriptions[index])
                    } else {
                        EditablePrescriptionCard(
                            prescription: $viewModel.prescriptions[index],
                            onDelete: {
                                viewModel.removePrescription(at: index)
                            }
                        )
                    }
                }
            }
        }
    }
}

// MARK: - Lab Tests Section
struct LabTestsSection: View {
    @ObservedObject var viewModel: ConsultationDetailViewModel
    let isCompleted: Bool
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "testtube.2")
                    .foregroundColor(.orange)
                Text("Suggested Lab Tests")
                    .font(.headline)
                    .fontWeight(.semibold)
                
                Spacer()
                
                if !isCompleted {
                    Button(action: viewModel.addLabTest) {
                        Image(systemName: "plus.circle.fill")
                            .foregroundColor(.blue)
                    }
                }
            }
            
            if viewModel.labTests.isEmpty {
                Text(isCompleted ? "No lab tests suggested." : "No lab tests suggested. Click + to add test recommendations.")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(12)
            } else {
                ForEach(viewModel.labTests.indices, id: \.self) { index in
                    if isCompleted {
                        ReadOnlyLabTestCard(labTest: viewModel.labTests[index])
                    } else {
                        LabTestCard(
                            labTest: $viewModel.labTests[index],
                            onDelete: {
                                viewModel.removeLabTest(at: index)
                            }
                        )
                    }
                }
            }
        }
    }
}

// MARK: - Action Buttons
struct ActionButtonsSection: View {
    @ObservedObject var viewModel: ConsultationDetailViewModel
    let onComplete: () -> Void
    
    var body: some View {
        VStack(spacing: 12) {
            Button(action: {
                viewModel.saveAndComplete {
                    onComplete()
                }
            }) {
                HStack {
                    if viewModel.isSaving {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                            .scaleEffect(0.8)
                    } else {
                        Image(systemName: "checkmark.circle.fill")
                    }
                    Text(viewModel.isSaving ? "Saving..." : "Complete Consultation")
                }
                .font(.headline)
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
                .background(viewModel.canComplete ? Color.green : Color.gray)
                .cornerRadius(12)
            }
            .disabled(!viewModel.canComplete || viewModel.isSaving)
            
            if let error = viewModel.error {
                Text("❌ \(error)")
                    .font(.caption)
                    .foregroundColor(.red)
                    .padding(.horizontal)
            }
        }
    }
}

// MARK: - Supporting Views
struct ReadOnlyPrescriptionCard: View {
    let prescription: Prescription
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "pills.fill")
                    .foregroundColor(.red)
                
                Text(prescription.medicationName.isEmpty ? "Medication" : prescription.medicationName)
                    .font(.headline)
                    .fontWeight(.semibold)
                
                Spacer()
            }
            
            if !prescription.dosage.isEmpty {
                HStack {
                    Text("Dosage:")
                        .font(.subheadline)
                        .fontWeight(.medium)
                    Text(prescription.dosage)
                        .font(.subheadline)
                    Spacer()
                }
            }
            
            if !prescription.frequency.isEmpty {
                HStack {
                    Text("Frequency:")
                        .font(.subheadline)
                        .fontWeight(.medium)
                    Text(prescription.frequency)
                        .font(.subheadline)
                    Spacer()
                }
            }
            
            if !prescription.instructions.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Instructions:")
                        .font(.subheadline)
                        .fontWeight(.medium)
                    Text(prescription.instructions)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct EditablePrescriptionCard: View {
    @Binding var prescription: Prescription
    let onDelete: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("💊 Prescription")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Spacer()
                
                Button(action: onDelete) {
                    Image(systemName: "trash")
                        .foregroundColor(.red)
                }
            }
            
            TextField("Medication name", text: $prescription.medicationName)
                .textFieldStyle(RoundedBorderTextFieldStyle())
            
            HStack {
                TextField("Dosage", text: $prescription.dosage)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                
                TextField("Frequency", text: $prescription.frequency)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
            }
            
            TextField("Instructions", text: $prescription.instructions)
                .textFieldStyle(RoundedBorderTextFieldStyle())
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct LabTestCard: View {
    @Binding var labTest: LabTest
    let onDelete: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("🧪 Lab Test")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Spacer()
                
                Button(action: onDelete) {
                    Image(systemName: "trash")
                        .foregroundColor(.red)
                }
            }
            
            TextField("Test name", text: $labTest.testName)
                .textFieldStyle(RoundedBorderTextFieldStyle())
            
            TextField("Reason for test", text: $labTest.reason)
                .textFieldStyle(RoundedBorderTextFieldStyle())
            
            TextField("Instructions", text: $labTest.instructions)
                .textFieldStyle(RoundedBorderTextFieldStyle())
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct ReadOnlyLabTestCard: View {
    let labTest: LabTest
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("🧪 Lab Test")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Spacer()
            }
            
            Text(labTest.testName)
                .font(.body)
                .fontWeight(.semibold)
            
            if !labTest.reason.isEmpty {
                Text("Reason: \(labTest.reason)")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            if !labTest.instructions.isEmpty {
                Text("Instructions: \(labTest.instructions)")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

// MARK: - Data Models
struct LabTest: Identifiable {
    let id = UUID()
    var testName: String = ""
    var reason: String = ""
    var instructions: String = ""
}

// MARK: - ViewModel
@MainActor
class ConsultationDetailViewModel: ObservableObject {
    @Published var aiSummary: String?
    @Published var doctorResponse: String = ""
    @Published var prescriptions: [Prescription] = []
    @Published var labTests: [LabTest] = []
    @Published var clinicalReport: ClinicalReport?
    
    @Published var isGeneratingSummary = false
    @Published var isSaving = false
    @Published var isLoadingClinicalReport = false
    @Published var error: String?
    @Published var showingClinicalReport = false
    
    private var consultationRequest: ConsultationRequestWithDoctor?
    private let networkService = NetworkService.shared
    
    var hasSummary: Bool {
        aiSummary != nil && !aiSummary!.isEmpty
    }
    
    var canComplete: Bool {
        !doctorResponse.isEmpty
    }
    
    var hasClinicalReport: Bool {
        consultationRequest?.clinicalReportId != nil
    }
    
    func loadConsultation(_ request: ConsultationRequestWithDoctor) {
        consultationRequest = request
        
        // Load existing doctor notes if available
        if let doctorNotes = request.doctorNotes, !doctorNotes.isEmpty {
            // Parse the doctor notes to extract different sections
            parseDoctorNotes(doctorNotes)
        }
    }
    
    func loadClinicalReport() {
        guard let request = consultationRequest,
              request.clinicalReportId != nil else {
            error = "No clinical report available for this consultation"
            return
        }
        
        isLoadingClinicalReport = true
        error = nil
        
        Task {
            do {
                let report = try await networkService.getClinicalReport(for: request.id)
                
                await MainActor.run {
                    self.clinicalReport = report
                    self.isLoadingClinicalReport = false
                    self.showingClinicalReport = true
                }
            } catch {
                await MainActor.run {
                    self.error = "Failed to load clinical report: \(error.localizedDescription)"
                    self.isLoadingClinicalReport = false
                }
            }
        }
    }
    
    private func parseDoctorNotes(_ notes: String) {
        // Split the notes into sections
        let sections = notes.components(separatedBy: "\n\n")
        var mainResponse = ""
        var parsedPrescriptions: [Prescription] = []
        var parsedLabTests: [LabTest] = []
        
        for section in sections {
            if section.contains("## Prescribed Medications:") {
                // Parse prescriptions
                let lines = section.components(separatedBy: "\n")
                for line in lines {
                    if line.hasPrefix("• ") {
                        let prescriptionText = String(line.dropFirst(2))
                        let components = prescriptionText.components(separatedBy: " - ")
                        
                        var prescription = Prescription()
                        prescription.medicationName = components.first ?? ""
                        
                        if components.count > 1 {
                            let dosageAndFreq = components[1]
                            if dosageAndFreq.contains("(") && dosageAndFreq.contains(")") {
                                let parts = dosageAndFreq.components(separatedBy: " (")
                                prescription.dosage = parts.first ?? ""
                                prescription.frequency = parts.last?.replacingOccurrences(of: ")", with: "") ?? ""
                            } else {
                                prescription.dosage = dosageAndFreq
                            }
                        }
                        
                        parsedPrescriptions.append(prescription)
                    } else if line.contains("Instructions:") {
                        // Add instructions to the last prescription
                        if !parsedPrescriptions.isEmpty {
                            let instructionText = line.replacingOccurrences(of: "  Instructions: ", with: "")
                            parsedPrescriptions[parsedPrescriptions.count - 1].instructions = instructionText
                        }
                    }
                }
            } else if section.contains("## Recommended Lab Tests:") {
                // Parse lab tests
                let lines = section.components(separatedBy: "\n")
                for line in lines {
                    if line.hasPrefix("• ") {
                        let testText = String(line.dropFirst(2))
                        let components = testText.components(separatedBy: " - ")
                        
                        var labTest = LabTest()
                        labTest.testName = components.first ?? ""
                        
                        if components.count > 1 {
                            labTest.reason = components[1]
                        }
                        
                        parsedLabTests.append(labTest)
                    } else if line.contains("Instructions:") {
                        // Add instructions to the last lab test
                        if !parsedLabTests.isEmpty {
                            let instructionText = line.replacingOccurrences(of: "  Instructions: ", with: "")
                            parsedLabTests[parsedLabTests.count - 1].instructions = instructionText
                        }
                    }
                }
            } else if !section.contains("##") && !section.isEmpty {
                // This is the main doctor response
                if mainResponse.isEmpty {
                    mainResponse = section
                } else {
                    mainResponse += "\n\n" + section
                }
            }
        }
        
        // Update the published properties
        doctorResponse = mainResponse
        prescriptions = parsedPrescriptions
        labTests = parsedLabTests
        
        // Set aiSummary to the full notes for display
        aiSummary = notes
    }
    
    func generateSummary() {
        guard let request = consultationRequest else { return }
        
        isGeneratingSummary = true
        error = nil
        
        Task {
            do {
                let updatedRequest = try await networkService.generateConsultationSummary(
                    requestId: request.id
                )
                
                await MainActor.run {
                    self.aiSummary = updatedRequest.doctorNotes
                    self.isGeneratingSummary = false
                }
            } catch {
                await MainActor.run {
                    self.error = "Failed to generate summary: \(error.localizedDescription)"
                    self.isGeneratingSummary = false
                }
            }
        }
    }
    
    func addPrescription() {
        prescriptions.append(Prescription())
    }
    
    func removePrescription(at index: Int) {
        prescriptions.remove(at: index)
    }
    
    func addLabTest() {
        labTests.append(LabTest())
    }
    
    func removeLabTest(at index: Int) {
        labTests.remove(at: index)
    }
    
    func showCopyConfirmation() {
        // Could add haptic feedback or toast notification here
    }
    
    func saveAndComplete(completion: @escaping () -> Void) {
        guard let request = consultationRequest else { return }
        
        isSaving = true
        error = nil
        
        // Debug: Print current state before saving
        print("🚀 [ConsultationDetailView] Starting saveAndComplete...")
        print("🚀 [ConsultationDetailView] Doctor response: \(doctorResponse.count) characters")
        print("🚀 [ConsultationDetailView] Prescriptions count: \(prescriptions.count)")
        for (index, prescription) in prescriptions.enumerated() {
            print("🚀 [ConsultationDetailView] Prescription \(index): '\(prescription.medicationName)' - '\(prescription.dosage)'")
        }
        
        // Create comprehensive response
        var fullResponse = doctorResponse
        
        if !prescriptions.isEmpty {
            fullResponse += "\n\n## Prescribed Medications:\n"
            for prescription in prescriptions {
                if !prescription.medicationName.isEmpty {
                    fullResponse += "• \(prescription.medicationName)"
                    if !prescription.dosage.isEmpty {
                        fullResponse += " - \(prescription.dosage)"
                    }
                    if !prescription.frequency.isEmpty {
                        fullResponse += " (\(prescription.frequency))"
                    }
                    if !prescription.instructions.isEmpty {
                        fullResponse += "\n  Instructions: \(prescription.instructions)"
                    }
                    fullResponse += "\n"
                }
            }
        }
        
        if !labTests.isEmpty {
            fullResponse += "\n\n## Recommended Lab Tests:\n"
            for test in labTests {
                if !test.testName.isEmpty {
                    fullResponse += "• \(test.testName)"
                    if !test.reason.isEmpty {
                        fullResponse += " - \(test.reason)"
                    }
                    if !test.instructions.isEmpty {
                        fullResponse += "\n  Instructions: \(test.instructions)"
                    }
                    fullResponse += "\n"
                }
            }
        }
        
        Task {
            do {
                _ = try await networkService.updateConsultationRequestStatus(
                    requestId: request.id,
                    status: "completed",
                    notes: fullResponse
                )
                
                await MainActor.run {
                    print("✅ [ConsultationDetailView] Backend update successful, now saving prescriptions...")
                    
                    // Save prescriptions to the backend database
                    Task {
                        await self.savePrescriptionsToBackend()
                    }
                    
                    print("✅ [ConsultationDetailView] All operations completed successfully")
                    
                    self.isSaving = false
                    completion()
                }
            } catch {
                await MainActor.run {
                    self.error = "Failed to save consultation: \(error.localizedDescription)"
                    self.isSaving = false
                    print("❌ [ConsultationDetailView] Error saving: \(error)")
                }
            }
        }
    }
    
    private func savePrescriptionsToBackend() async {
        guard let request = consultationRequest else {
            print("❌ [ConsultationDetailView] No consultation request available")
            return
        }
        
        // Filter out empty prescriptions
        let validPrescriptions = prescriptions.filter { !$0.medicationName.isEmpty }
        
        if validPrescriptions.isEmpty {
            print("⚠️ [ConsultationDetailView] No valid prescriptions to save")
            return
        }
        
        print("💊 [ConsultationDetailView] Saving \(validPrescriptions.count) prescriptions to backend...")
        print("💊 [ConsultationDetailView] Consultation ID: \(request.id)")
        print("💊 [ConsultationDetailView] Chat Session ID: \(request.chatSessionId ?? -1)")
        print("💊 [ConsultationDetailView] Doctor: \(request.doctor.fullName)")
        
        // Create properly structured prescriptions with doctor info
        var structuredPrescriptions: [Prescription] = []
        
        for (index, prescription) in validPrescriptions.enumerated() {
            let structuredPrescription = Prescription(
                medicationName: prescription.medicationName,
                dosage: prescription.dosage,
                frequency: prescription.frequency.isEmpty ? "As directed" : prescription.frequency,
                instructions: prescription.instructions.isEmpty ? "Follow doctor's instructions" : prescription.instructions,
                prescribedBy: request.doctor.fullName
            )
            structuredPrescriptions.append(structuredPrescription)
            print("✅ [ConsultationDetailView] Prescription \(index + 1): \(structuredPrescription.medicationName)")
        }
        
        do {
            // Save prescriptions to backend via API
            try await networkService.savePrescriptionsForConsultation(
                requestId: request.id,
                prescriptions: structuredPrescriptions
            )
            
            await MainActor.run {
                print("✅ [ConsultationDetailView] Successfully saved \(structuredPrescriptions.count) prescriptions to backend")
            }
        } catch {
            await MainActor.run {
                print("❌ [ConsultationDetailView] Error saving prescriptions to backend: \(error)")
                self.error = "Failed to save prescriptions: \(error.localizedDescription)"
            }
        }
    }
}

// MARK: - Clinical Report View
struct ClinicalReportView: View {
    let clinicalReport: ClinicalReport
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Header
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Clinical Report")
                            .font(.title)
                            .fontWeight(.bold)
                        
                        Text("Generated: \(clinicalReport.createdAt.formatted(date: .abbreviated, time: .shortened))")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    
                    // Patient Question
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Patient Question")
                            .font(.headline)
                            .foregroundColor(.blue)
                        
                        Text(clinicalReport.userQuestion)
                            .font(.body)
                            .padding()
                            .background(Color(.systemGray6))
                            .cornerRadius(12)
                    }
                    
                    // AI Response
                    VStack(alignment: .leading, spacing: 8) {
                        Text("AI Response")
                            .font(.headline)
                            .foregroundColor(.green)
                        
                        Text(clinicalReport.aiResponse)
                            .font(.body)
                            .padding()
                            .background(Color(.systemGray6))
                            .cornerRadius(12)
                    }
                    
                    // Comprehensive Clinical Context
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Clinical Context Used by AI")
                            .font(.headline)
                            .foregroundColor(.orange)
                        
                        ScrollView {
                            Text(clinicalReport.comprehensiveContext)
                                .font(.body)
                                .lineSpacing(4)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .textSelection(.enabled)
                        }
                        .frame(maxHeight: 400)
                        .padding(16)
                        .background(Color(.systemGray6))
                        .cornerRadius(12)
                    }
                    

                }
                .padding()
            }
            .navigationTitle("Clinical Report")
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

#Preview {
    ConsultationDetailView(
        consultationRequest: ConsultationRequestWithDoctor(
            id: 1,
            userId: 1,
            doctorId: 2,
            chatSessionId: 1,
            clinicalReportId: nil,
            context: "Sample context",
            userQuestion: "Sample question",
            status: "accepted",
            urgencyLevel: "normal",
            createdAt: Date(),
            acceptedAt: Date(),
            completedAt: nil,
            doctorNotes: nil,
            doctor: Doctor(
                id: 1,
                fullName: "Dr. Smith",
                specialization: "Cardiology",
                yearsExperience: 10,
                rating: 4.8,
                totalConsultations: 100,
                bio: "Sample bio",
                isAvailable: true
            )
        )
    )
} 