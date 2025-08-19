import SwiftUI
import Foundation

struct PrescriptionsView: View {
    @StateObject private var viewModel = PrescriptionsViewModel()
    @StateObject private var chatViewModel = ChatViewModel.shared
    @StateObject private var historyManager = ChatHistoryManager.shared
    @Environment(\.dismiss) private var dismiss

    @State private var selectedPrescription: PrescriptionWithSession?
    
    var body: some View {
        NavigationView {
            VStack {
                if viewModel.isLoading {
                    // Loading state
                    VStack(spacing: 20) {
                        ProgressView()
                            .scaleEffect(1.5)
                        
                        Text("Loading your prescriptions...")
                            .font(.body)
                            .foregroundColor(.secondary)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    
                } else if viewModel.prescriptions.isEmpty {
                    // Empty state
                    VStack(spacing: 20) {
                        Image(systemName: "pills.circle")
                            .font(.system(size: 60))
                            .foregroundColor(.gray)
                        
                        Text("No Prescriptions Yet")
                            .font(.title2)
                            .fontWeight(.semibold)
                        
                        Text("Your prescriptions from doctor consultations will appear here")
                            .font(.body)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    
                } else {
                    // Prescriptions list
                    List {
                        ForEach(viewModel.prescriptions, id: \.id) { prescriptionWithSession in
                            PrescriptionWithSessionCard(
                                prescriptionWithSession: prescriptionWithSession,
                                onTapChat: {
                                    openChatForPrescription(prescriptionWithSession)
                                }
                            )
                            .onTapGesture {
                                selectedPrescription = prescriptionWithSession
                            }
                        }
                    }
                    .listStyle(PlainListStyle())
                    .refreshable {
                        await viewModel.loadPrescriptions()
                    }
                }
                
                if let error = viewModel.error {
                    Text("❌ \(error)")
                        .font(.caption)
                        .foregroundColor(.red)
                        .padding()
                }
            }
            .navigationTitle("My Prescriptions")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Close") {
                        dismiss()
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: {
                        Task {
                            await viewModel.loadPrescriptions()
                        }
                    }) {
                        Image(systemName: "arrow.clockwise")
                    }
                }
            }
            .task {
                await viewModel.loadPrescriptions()
            }
        }
        .sheet(item: $selectedPrescription) { prescription in
            PrescriptionDetailView(prescriptionWithSession: prescription, onContinueChat: {
                selectedPrescription = nil
                openChatForPrescription(prescription)
            })
        }

    }
    
    private func openChatForPrescription(_ prescriptionWithSession: PrescriptionWithSession) {
        print("🗨️ [PrescriptionsView] Opening chat for prescription from \(prescriptionWithSession.doctorName)")
        
        Task {
            await setupChatForPrescription(prescriptionWithSession)
        }
        
        // Dismiss this view and post notification to switch to chat tab
        dismiss()
        
        // Post notification to switch to chat tab
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            NotificationCenter.default.post(name: Notification.Name("SwitchToChatTab"), object: nil)
        }
    }
    
    private func setupChatForPrescription(_ prescriptionWithSession: PrescriptionWithSession) async {
        print("🔧 [PrescriptionsView] Setting up chat for prescription")
        
        // If prescription has a chat session ID, load that session; otherwise create a new one
        if let existingSessionId = prescriptionWithSession.chatSessionId {
            print("🔄 [PrescriptionsView] Loading existing chat session: \(existingSessionId)")
            await MainActor.run {
                chatViewModel.switchToSession(existingSessionId)
            }
            print("✅ [PrescriptionsView] Loaded existing chat session for \(prescriptionWithSession.medicationName)")
        } else {
            print("🆕 [PrescriptionsView] Creating new chat session for prescription")
            
            // Create a new session with prescription context
            let sessionTitle = prescriptionWithSession.sessionTitle ?? "Chat with \(prescriptionWithSession.doctorName)"
            
            if let newSessionId = await historyManager.createNewSession(title: sessionTitle) {
                await MainActor.run {
                    chatViewModel.switchToSession(newSessionId)
                    
                    // Add prescription info as context message
                    let contextMessage = ChatMessage(
                        role: .assistant,
                        content: """
**Prescription Information:**

**Medication:** \(prescriptionWithSession.medicationName)
**Prescribed by:** \(prescriptionWithSession.doctorName)  
**Dosage:** \(prescriptionWithSession.dosage.isEmpty ? "As directed" : prescriptionWithSession.dosage)
**Frequency:** \(prescriptionWithSession.frequency.isEmpty ? "As directed" : prescriptionWithSession.frequency)
**Instructions:** \(prescriptionWithSession.instructions.isEmpty ? "Follow doctor's instructions" : prescriptionWithSession.instructions)
**Date:** \(DateFormatter.prescriptionDate.string(from: prescriptionWithSession.prescribedAt))

How can I help you with questions about this prescription?
""",
                        timestamp: Date()
                    )
                    
                    // Add the context message to the session
                    chatViewModel.messages = [contextMessage]
                    
                    print("✅ [PrescriptionsView] Chat setup complete for \(prescriptionWithSession.medicationName)")
                }
            } else {
                print("❌ [PrescriptionsView] Failed to create new session")
            }
        }
    }
}

// ViewModel for managing prescriptions data
@MainActor
class PrescriptionsViewModel: ObservableObject {
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
            print("✅ [PrescriptionsViewModel] Loaded \(prescriptions.count) prescriptions from backend")
        } catch {
            self.error = "Failed to load prescriptions: \(error.localizedDescription)"
            print("❌ [PrescriptionsViewModel] Error loading prescriptions: \(error)")
        }
        
        isLoading = false
    }
}

struct PrescriptionWithSessionCard: View {
    let prescriptionWithSession: PrescriptionWithSession
    let onTapChat: () -> Void
    
    private var prescription: Prescription {
        prescriptionWithSession.prescription
    }
    
    private var prescribedDate: String {
        DateFormatter.prescriptionDate.string(from: prescription.prescribedAt)
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(prescription.medicationName)
                        .font(.headline)
                        .fontWeight(.semibold)
                        .foregroundColor(.primary)
                    
                    Text("Prescribed by \(prescriptionWithSession.doctorName)")
                        .font(.subheadline)
                        .foregroundColor(.blue)
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 2) {
                    Image(systemName: "pills.fill")
                        .font(.title2)
                        .foregroundColor(.orange)
                    
                    Text(prescribedDate)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
            
            // Medication details
            VStack(alignment: .leading, spacing: 8) {
                if !prescription.dosage.isEmpty {
                    MedicationDetailRow(
                        icon: "scalemass",
                        title: "Dosage",
                        value: prescription.dosage
                    )
                }
                
                if !prescription.frequency.isEmpty {
                    MedicationDetailRow(
                        icon: "clock",
                        title: "Frequency",
                        value: prescription.frequency
                    )
                }
                
                if !prescription.instructions.isEmpty {
                    MedicationDetailRow(
                        icon: "text.alignleft",
                        title: "Instructions",
                        value: prescription.instructions
                    )
                }
            }
            
            // Session info and chat button
            VStack(spacing: 8) {
                HStack {
                    Image(systemName: "message.circle")
                        .font(.caption)
                        .foregroundColor(.gray)
                    
                    if let sessionTitle = prescriptionWithSession.sessionTitle, !sessionTitle.isEmpty {
                        Text("From: \(sessionTitle)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    } else {
                        Text("From consultation")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    
                    Spacer()
                }
                
                // Chat button
                Button(action: onTapChat) {
                    HStack {
                        Image(systemName: "message.fill")
                        Text("Ask About This Prescription")
                    }
                    .font(.caption)
                    .foregroundColor(.white)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(Color.blue)
                    .cornerRadius(8)
                }
            }
            .padding(.top, 4)
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.1), radius: 4, x: 0, y: 2)
    }
}

struct MedicationDetailRow: View {
    let icon: String
    let title: String
    let value: String
    
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .font(.caption)
                .foregroundColor(.blue)
                .frame(width: 16)
            
            Text(title + ":")
                .font(.caption)
                .fontWeight(.medium)
                .foregroundColor(.secondary)
            
            Text(value)
                .font(.caption)
                .foregroundColor(.primary)
            
            Spacer()
        }
    }
}

// Extension for date formatting
extension DateFormatter {
    static let prescriptionDate: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter
    }()
}

// Detailed view for prescription with chat history
struct PrescriptionDetailView: View {
    let prescriptionWithSession: PrescriptionWithSession
    let onContinueChat: () -> Void
    
    @Environment(\.dismiss) private var dismiss
    @State private var messages: [ChatMessage] = []
    @State private var isLoadingMessages = true
    
    private var prescription: Prescription {
        prescriptionWithSession.prescription
    }
    
    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Prescription Details Section
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        // Prescription Header
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Image(systemName: "pills.fill")
                                    .font(.title2)
                                    .foregroundColor(.orange)
                                
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(prescription.medicationName)
                                        .font(.title2)
                                        .fontWeight(.bold)
                                        .foregroundColor(.primary)
                                    
                                    Text("Prescribed by \(prescriptionWithSession.doctorName)")
                                        .font(.subheadline)
                                        .foregroundColor(.blue)
                                }
                                
                                Spacer()
                            }
                            
                            Text("Prescribed on \(DateFormatter.prescriptionDate.string(from: prescription.prescribedAt))")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(12)
                        
                        // Medication Details
                        VStack(alignment: .leading, spacing: 16) {
                            Text("Medication Details")
                                .font(.headline)
                                .fontWeight(.semibold)
                            
                                                         VStack(alignment: .leading, spacing: 12) {
                                 if !prescription.dosage.isEmpty {
                                     PrescriptionDetailRow(title: "Dosage", value: prescription.dosage, icon: "scalemass")
                                 }
                                 
                                 if !prescription.frequency.isEmpty {
                                     PrescriptionDetailRow(title: "Frequency", value: prescription.frequency, icon: "clock")
                                 }
                                 
                                 if !prescription.instructions.isEmpty {
                                     PrescriptionDetailRow(title: "Instructions", value: prescription.instructions, icon: "text.alignleft")
                                 }
                             }
                        }
                        .padding()
                        .background(Color(.systemBackground))
                        .cornerRadius(12)
                        .shadow(color: Color.black.opacity(0.05), radius: 2, x: 0, y: 1)
                    }
                    .padding()
                }
                
                Divider()
                
                // Chat History Section
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("Chat History")
                            .font(.headline)
                            .fontWeight(.semibold)
                        
                        Spacer()
                        
                        if let sessionTitle = prescriptionWithSession.sessionTitle {
                            Text(sessionTitle)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    .padding(.horizontal)
                    .padding(.top)
                    
                    if isLoadingMessages {
                        VStack {
                            ProgressView("Loading chat history...")
                                .padding()
                            Spacer()
                        }
                    } else if messages.isEmpty {
                        VStack(spacing: 16) {
                            Image(systemName: "message")
                                .font(.system(size: 40))
                                .foregroundColor(.gray)
                            
                            Text("No chat history available")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                    } else {
                        ScrollView {
                            LazyVStack(spacing: 12) {
                                ForEach(messages) { message in
                                    PrescriptionChatBubble(message: message)
                                        .padding(.horizontal)
                                }
                            }
                            .padding(.vertical)
                        }
                    }
                    
                    // Continue Chat Button
                    Button(action: onContinueChat) {
                        HStack {
                            Image(systemName: "message.fill")
                            Text("Continue Chat Session")
                        }
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.blue)
                        .cornerRadius(12)
                    }
                    .padding(.horizontal)
                    .padding(.bottom)
                }
                .frame(maxHeight: .infinity)
                .background(Color(.systemGray6))
            }
            .navigationTitle("Prescription Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Close") {
                        dismiss()
                    }
                }
            }
        }
        .task {
            await loadChatHistory()
        }
    }
    
    private func loadChatHistory() async {
        // If we have a session ID from the prescription, load its messages
        if let sessionId = prescriptionWithSession.chatSessionId {
            do {
                let backendMessages = try await NetworkService.shared.getSessionMessages(sessionId)
                await MainActor.run {
                    messages = backendMessages.map { $0.toChatMessage() }
                    isLoadingMessages = false
                }
                print("✅ [PrescriptionDetailView] Loaded \(messages.count) messages for session \(sessionId)")
            } catch {
                print("❌ [PrescriptionDetailView] Error loading messages: \(error)")
                await MainActor.run {
                    messages = []
                    isLoadingMessages = false
                }
            }
        } else {
            await MainActor.run {
                messages = []
                isLoadingMessages = false
            }
        }
    }
}

struct PrescriptionDetailRow: View {
    let title: String
    let value: String
    let icon: String
    
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .font(.body)
                .foregroundColor(.blue)
                .frame(width: 20)
            
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(.secondary)
                
                Text(value)
                    .font(.body)
                    .foregroundColor(.primary)
            }
            
            Spacer()
        }
    }
}

struct PrescriptionChatBubble: View {
    let message: ChatMessage
    
    var body: some View {
        HStack {
            if message.role == .user {
                Spacer()
                
                VStack(alignment: .trailing, spacing: 6) {
                    // Show file attachment if present
                    if message.hasAttachment, let fileName = message.fileName {
                        HStack(spacing: 6) {
                            Image(systemName: getFileIcon(for: message.fileType))
                                .foregroundColor(.white)
                            Text("📎 \(fileName)")
                                .font(.caption)
                                .foregroundColor(.white)
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(Color.blue.opacity(0.8))
                        .cornerRadius(8)
                    }
                    
                    // Show message content if not empty
                    if !message.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        Text(message.content)
                            .padding()
                            .background(Color.blue)
                            .foregroundColor(.white)
                            .cornerRadius(16)
                    }
                }
                .frame(maxWidth: .infinity * 0.8, alignment: .trailing)
            } else {
                VStack(alignment: .leading, spacing: 6) {
                    // Show file attachment if present  
                    if message.hasAttachment, let fileName = message.fileName {
                        HStack(spacing: 6) {
                            Image(systemName: getFileIcon(for: message.fileType))
                                .foregroundColor(.blue)
                            Text("📎 \(fileName)")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(Color(UIColor.systemGray6))
                        .cornerRadius(8)
                    }
                    
                    // Show message content if not empty
                    if !message.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        Text(message.content)
                            .padding()
                            .background(Color(.systemGray5))
                            .foregroundColor(.primary)
                            .cornerRadius(16)
                    }
                }
                .frame(maxWidth: .infinity * 0.8, alignment: .leading)
                
                Spacer()
            }
        }
    }
    
    private func getFileIcon(for fileType: String?) -> String {
        guard let fileType = fileType?.lowercased() else { return "paperclip" }
        
        switch fileType {
        case "pdf":
            return "doc.fill"
        case "jpg", "jpeg", "png":
            return "photo.fill"
        default:
            return "paperclip"
        }
    }
}

#Preview {
    PrescriptionsView()
} 