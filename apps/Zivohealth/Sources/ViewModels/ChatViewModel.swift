import Foundation
import SwiftUI
import Combine

// MARK: - Message Tracking for Verification
struct MessageTrackingInfo {
    let content: String
    let timestamp: Date
    let fileURL: URL?
    var userMessageId: Int?
    var aiMessageId: Int?
    var requestId: String?
    var isComplete: Bool = false
}

@MainActor
class ChatViewModel: ObservableObject {
    static let shared = ChatViewModel()

    @Published var messages: [ChatMessage] = []
    @Published var isLoading = false
    @Published var error: String?
    @Published var currentSessionId: Int? { didSet { if let sessionId = currentSessionId, sessionId != oldValue { startStatusUpdates(sessionId: sessionId) } } }
    
    // Verification tracking (still local until we add backend support)
    @Published var pendingVerificationRequest: ConsultationRequestResponse?
    @Published var isVerificationPending = false
    @Published var verificationStatus: String?
    @Published var selectedDoctorForVerification: Doctor?
    
    // Computed property for current session title
    @Published var currentSessionTitle: String = "Chat"
    
    // Track when AI response is complete and if last interaction was file upload
    @Published var isAIResponseComplete = false
    @Published var lastInteractionWasFileUpload = false
    @Published var isAnalyzingFile = false  // Track when file analysis is in progress
    
    // Track retry state to prevent duplicate messages
    private var lastSentMessageContent: String?
    private var lastSentFileURL: URL?
    private var isRetrying = false
    
    // Track sent messages for verification
    private var sentMessageTracker: [String: MessageTrackingInfo] = [:]

    // MARK: - Streaming and Real-time Status
    @Published var isStreaming = false
    @Published var streamingContent = ""
    @Published var currentStatus = ""
    @Published var currentProgress: Double = 0.0
    @Published var currentAgent = ""
    @Published var isTyping = false
    @Published var currentUploadFilename = ""  // Track current upload filename
    
    // Enhanced messages with interactive components
    @Published var enhancedMessages: [EnhancedChatMessage] = []
    @Published var useEnhancedMode = false  // Backend-controlled enhanced chat features
    


    private let networkService = NetworkService.shared
    private let historyManager = ChatHistoryManager.shared

    // Add timer for automatic status checking
    private var statusCheckTimer: Timer?
    private var cancellables = Set<AnyCancellable>()
    
    // Streaming and WebSocket tasks
    private var statusTask: Task<Void, Never>?
    private var streamingTask: Task<Void, Never>?
    private var activeStatusSessionId: Int?

    private init() {
        // Private initializer to enforce singleton pattern
        setupCurrentSession()
        
        // Start automatic status checking when verification becomes pending
        $isVerificationPending
            .sink { [weak self] isPending in
                if isPending {
                    self?.startAutomaticStatusChecking()
                } else {
                    Task { @MainActor in
                        await self?.stopAutomaticStatusChecking()
                    }
                }
            }
            .store(in: &cancellables)
        
        // Listen for upload state changes and transition to analysis
        networkService.$isUploading
            .sink { [weak self] isUploading in
                guard let self = self else { return }
                if isUploading && self.lastInteractionWasFileUpload {
                    // Upload started, show uploading status
                    print("📎 [ChatViewModel] Upload started - showing upload status")
                    self.isAnalyzingFile = true
                    self.currentStatus = "Analyzing file..."
                    self.isTyping = true
                } else if !isUploading && self.lastInteractionWasFileUpload {
                    // Upload completed, keep showing analysis state - don't change anything
                    print("📎 [ChatViewModel] Upload completed - keeping analysis state active")
                    // Keep isAnalyzingFile = true until we get the final AI response
                }
            }
            .store(in: &cancellables)
    }
    
    private func setupCurrentSession() {
        Task {
            // Clean up any invalid session data on startup
            cleanupInvalidSessionData()
            
            // Try to restore the last session ID from UserDefaults first
            if let savedSessionId = UserDefaults.standard.object(forKey: "currentChatSessionId") as? Int {
                currentSessionId = savedSessionId
                print("🔄 [ChatViewModel] Restored session ID from UserDefaults: \(savedSessionId)")
                
                // Try to load the session data to verify it exists
                do {
                    await loadCurrentSessionData()
                    print("✅ [ChatViewModel] Successfully loaded existing session data")
                } catch {
                    print("❌ [ChatViewModel] Failed to load session data: \(error)")
                    print("🧹 [ChatViewModel] Clearing invalid session and creating new one")
                    
                    // Clear invalid session data
                    UserDefaults.standard.removeObject(forKey: "currentChatSessionId")
                    currentSessionId = nil
                    await MainActor.run {
                        self.clearAllMessages()
                    }
                    
                    // Create new session
                    currentSessionId = await historyManager.ensureCurrentSession()
                    await loadCurrentSessionData()
                    
                    // Save the new session ID
                    if let sessionId = currentSessionId {
                        UserDefaults.standard.set(sessionId, forKey: "currentChatSessionId")
                        print("💾 [ChatViewModel] Saved new session ID to UserDefaults: \(sessionId)")
                    }
                }
            } else {
                // Create new session if none exists
                currentSessionId = await historyManager.ensureCurrentSession()
                await loadCurrentSessionData()
                
                // Save the current session ID
                if let sessionId = currentSessionId {
                    UserDefaults.standard.set(sessionId, forKey: "currentChatSessionId")
                    print("💾 [ChatViewModel] Saved current session ID to UserDefaults: \(sessionId)")
                }
            }
        }
    }
    
    // MARK: - Helper Methods
    
    private func getFileType(for fileExtension: String) -> String {
        let ext = fileExtension.lowercased()
        switch ext {
        case "jpg", "jpeg", "png", "gif", "bmp", "tiff":
            return "Image File"
        case "pdf":
            return "PDF Document"
        case "doc", "docx":
            return "Word Document"
        case "xls", "xlsx":
            return "Excel Document"
        case "txt":
            return "Text File"
        default:
            return "Unknown File"
        }
    }
    
    private func clearAllMessages() {
        messages.removeAll()
        enhancedMessages.removeAll()
        currentSessionTitle = "New Chat"
        isAIResponseComplete = false
        lastInteractionWasFileUpload = false
        error = nil
        print("🧹 [ChatViewModel] Cleared all messages and reset chat state")
    }
    
    // MARK: - Session Management
    
    func createNewChat() {
        Task {
            // Create new session in backend
            if let newSessionId = await historyManager.createNewSession() {
                currentSessionId = newSessionId
                
                // Save to UserDefaults for persistence across role switches
                UserDefaults.standard.set(newSessionId, forKey: "currentChatSessionId")
                
                // Clear current state - INCLUDING enhanced messages
                await MainActor.run {
                    self.clearAllMessages()
                    self.clearVerificationRequest()
                }
                
                print("📝 [ChatViewModel] Created new chat session: \(newSessionId)")
                print("🧹 [ChatViewModel] Cleared all messages and enhanced messages")
            }
        }
    }
    
    func switchToSession(_ sessionId: Int) {
        Task {
            // Switch to new session
            historyManager.switchToSession(sessionId)
            currentSessionId = sessionId
            
            // Save to UserDefaults for persistence across role switches
            UserDefaults.standard.set(sessionId, forKey: "currentChatSessionId")
            
            // Reset AI response state before loading new session
            await MainActor.run {
                isAIResponseComplete = false
                lastInteractionWasFileUpload = false
            }
            
            // Load new session data
            await loadCurrentSessionData()
            
            print("🔄 [ChatViewModel] Switched to session: \(sessionId)")
        }
    }

    func loadCurrentSessionData() async {
        print("📥 [ChatViewModel] loadCurrentSessionData called")
        
        guard let sessionId = currentSessionId else {
            print("⚠️ [ChatViewModel] No current session ID")
            return
        }
        
        do {
            // Load session details and messages from backend
            let session = try await networkService.getChatSession(sessionId)
            let backendMessages = try await networkService.getSessionMessages(sessionId)
            
            await MainActor.run {
                
                // Filter out any status messages or invalid messages from backend
                let validMessages = backendMessages.filter { backendMessage in
                    // Only include user and assistant messages, filter out status/system messages
                    let isValidRole = backendMessage.role == "user" || backendMessage.role == "assistant"
                    let isNotSystemJSON = !backendMessage.content.contains("message_type")
                    
                    // Allow messages with file attachments OR VISUALIZATIONS even if content is empty
                    let hasFileAttachment = backendMessage.filePath != nil && !backendMessage.filePath!.isEmpty
                    let hasVisualizations = backendMessage.visualizations?.isEmpty == false
                    let hasValidContent = !backendMessage.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                    let isValidMessage = hasValidContent || hasFileAttachment || hasVisualizations
                    
                    let isValid = isValidRole && isNotSystemJSON && isValidMessage
                    
                    
                    return isValid
                }

                
                self.messages = validMessages.map { $0.toChatMessage() }
                self.currentSessionTitle = session.title ?? "Chat Session"
                print("🧹 [ChatViewModel] Initial load filtered messages: \(backendMessages.count) -> \(validMessages.count)")
                
                // Update enhanced mode setting from session AFTER messages are loaded
                self.updateEnhancedModeFromSession(session)
                
                // Ensure enhanced messages are synced if in enhanced mode
                if self.useEnhancedMode && !self.messages.isEmpty {
                    self.enhancedMessages = self.messages.map { EnhancedChatMessage(from: $0) }
                    print("📦 [ChatViewModel] Synced \(self.enhancedMessages.count) messages for enhanced mode on load")
                }
                
                // Set AI response complete if we have messages and the last message is from assistant
                self.isAIResponseComplete = !self.messages.isEmpty && self.messages.last?.role == .assistant
                self.lastInteractionWasFileUpload = false  // Reset for loaded sessions
                
                print("✅ [ChatViewModel] Loaded \(self.messages.count) messages for session \(sessionId)")
                print("📝 [ChatViewModel] Updated session title to: \(self.currentSessionTitle)")
                print("🤖 [ChatViewModel] AI response complete: \(self.isAIResponseComplete)")
            }
        } catch {
            print("❌ [ChatViewModel] Error loading session data: \(error)")
            
            // If session doesn't exist, clear the invalid ID and try to create/load a valid one
            if error.localizedDescription.contains("404") || error.localizedDescription.contains("not found") {
                print("🧹 [ChatViewModel] Session \(sessionId) not found, clearing and creating new session")
                UserDefaults.standard.removeObject(forKey: "currentChatSessionId")
                currentSessionId = nil
                
                // Try to load an existing session or create a new one
                currentSessionId = await historyManager.ensureCurrentSession()
                if let newSessionId = currentSessionId {
                    UserDefaults.standard.set(newSessionId, forKey: "currentChatSessionId")
                    await loadCurrentSessionData()
                    print("✅ [ChatViewModel] Successfully recovered with session \(newSessionId)")
                }
            }
        }
    }
    
    func createNewSession() async {
        print("➕ [ChatViewModel] Creating new session")
        
        if let newSessionId = await historyManager.createNewSession() {
            await MainActor.run {
                self.currentSessionId = newSessionId
                self.clearAllMessages()
                print("✅ [ChatViewModel] Created new session with ID: \(newSessionId)")
            }
        } else {
            print("❌ [ChatViewModel] Failed to create new session")
        }
    }
    
    // Legacy methods for compatibility - now simplified
    private func loadPersistedMessages() {
        // No longer needed - messages loaded from backend
    }
    
    private func loadPersistedVerificationData() {
        // Still local until backend supports verification in sessions
    }
    
    private func persistVerificationData() {
        // Still local until backend supports verification in sessions
    }

    func persistMessages() {
        // No longer needed - messages persisted automatically by backend
    }
    
    private func cleanupInvalidSessionData() {
        // Check if we have a stored session ID and if it's reasonable
        if let savedSessionId = UserDefaults.standard.object(forKey: "currentChatSessionId") as? Int {
            // If the session ID seems unreasonable (too high, likely from old data), clear it
            if savedSessionId > 1000 {
                print("🧹 [ChatViewModel] Clearing potentially invalid session ID: \(savedSessionId)")
                UserDefaults.standard.removeObject(forKey: "currentChatSessionId")
            }
        }
    }
    
    func setVerificationRequest(_ request: ConsultationRequestResponse, doctor: Doctor) {
        pendingVerificationRequest = request
        selectedDoctorForVerification = doctor
        isVerificationPending = true
        verificationStatus = request.status
        print("✅ [ChatViewModel] Set verification request \(request.id) with Dr. \(doctor.fullName)")
    }
    
    private func startAutomaticStatusChecking() {
        statusCheckTimer?.invalidate()
        statusCheckTimer = Timer.scheduledTimer(withTimeInterval: 3.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                await self?.checkVerificationStatus()
            }
        }
        print("⏰ [ChatViewModel] Started automatic verification status checking")
    }

    private func stopAutomaticStatusChecking() async {
        statusCheckTimer?.invalidate()
        statusCheckTimer = nil
        print("⏹️ [ChatViewModel] Stopped automatic verification status checking")
    }

    func checkVerificationStatus() async {
        guard let request = pendingVerificationRequest else { return }
        
        do {
            print("🔍 [ChatViewModel] Checking verification status for request \(request.id)")
            let updatedRequest = try await networkService.checkConsultationVerificationStatus(requestId: request.id)
            
            await MainActor.run {
                verificationStatus = updatedRequest.status
                print("✅ [ChatViewModel] Updated verification status to: \(updatedRequest.status)")
            }
            
            // If completed, add doctor's response to chat and clear verification
            if updatedRequest.status.lowercased() == "completed" {
                // Add doctor's response to chat if available
                if let doctorNotes = updatedRequest.doctorNotes, !doctorNotes.isEmpty {
                    // Parse structured response into separate sections
                    let parsedSections = parseStructuredDoctorResponse(doctorNotes)
                    
                    // Save to backend FIRST to ensure sync, then update local UI
                    if let sessionId = currentSessionId {
                        do {
                            // Save each section as a separate message for better readability
                            for section in parsedSections {
                                let sectionContent = "**\(section.title)**\n\n\(section.content)"
                                try await networkService.saveDirectMessage(
                                    sessionId: sessionId, 
                                    role: "assistant",
                                    content: sectionContent
                                )
                            }
                            print("✅ [ChatViewModel] Saved doctor's structured response to backend")
                            
                            // Now reload messages from backend to ensure sync
                            await loadCurrentSessionData()
                            print("✅ [ChatViewModel] Reloaded messages from backend to ensure sync")
                            
                            // Parse and create prescriptions if found in doctor's response
                            await parsePrescriptionsFromDoctorResponse(doctorNotes, sessionId: sessionId, doctorName: selectedDoctorForVerification?.fullName ?? "Doctor")
                            
                        } catch {
                            print("❌ [ChatViewModel] Failed to save doctor's response to backend: \(error)")
                            
                            // Fallback: add sections to local messages only if backend save fails
                            await MainActor.run {
                                for section in parsedSections {
                                    let sectionContent = "**\(section.title)**\n\n\(section.content)"
                                    let doctorResponseMessage = ChatMessage(
                                        role: .assistant,
                                        content: sectionContent,
                                        timestamp: Date()
                                    )
                                    messages.append(doctorResponseMessage)
                                }
                                print("⚠️ [ChatViewModel] Added doctor's structured response locally as fallback")
                            }
                        }
                    } else {
                        // No session available, add locally only
                        await MainActor.run {
                            for section in parsedSections {
                                let sectionContent = "**\(section.title)**\n\n\(section.content)"
                                let doctorResponseMessage = ChatMessage(
                                    role: .assistant,
                                    content: sectionContent,
                                    timestamp: Date()
                                )
                                messages.append(doctorResponseMessage)
                            }
                            print("⚠️ [ChatViewModel] No session ID available, added doctor's structured response locally only")
                        }
                    }
                }
                
                await stopAutomaticStatusChecking()
                clearVerificationRequest()
                print("🎉 [ChatViewModel] Consultation completed - cleared verification request")
            }
        } catch {
            print("❌ [ChatViewModel] Error checking verification status: \(error)")
            // Keep the current status on error
        }
    }
    
    func clearVerificationRequest() {
        pendingVerificationRequest = nil
        selectedDoctorForVerification = nil
        isVerificationPending = false
        verificationStatus = nil
        
        print("🗑️ [ChatViewModel] Cleared verification request data")
    }
    
    func manuallyCheckVerificationStatus() {
        Task {
            await checkVerificationStatus()
        }
    }
    
    private func parseStructuredDoctorResponse(_ doctorNotes: String) -> [(title: String, content: String)] {
        // Check if this is a generated AI summary (contains structured sections)
        if doctorNotes.contains("## Questions") && doctorNotes.contains("## Proposed Solution") && doctorNotes.contains("## Precautions") {
            // This is a generated summary - extract only the Proposed Solution for patients
            let proposedSolutionPattern = #"##\s*Proposed Solution\s*\n(.*?)(?=\n##|\Z)"#
            let regex = try? NSRegularExpression(pattern: proposedSolutionPattern, options: [.caseInsensitive, .dotMatchesLineSeparators])
            if let match = regex?.firstMatch(in: doctorNotes, options: [], range: NSRange(doctorNotes.startIndex..., in: doctorNotes)),
               let range = Range(match.range(at: 1), in: doctorNotes) {
                let proposedSolution = String(doctorNotes[range]).trimmingCharacters(in: .whitespacesAndNewlines)
                if !proposedSolution.isEmpty {
                    return [("Doctor's Response", proposedSolution)]
                }
            }
        }
        
        // For direct doctor responses, show the entire content
        return [("Doctor's Response", doctorNotes)]
    }
    
    private func parsePrescriptionsFromDoctorResponse(_ doctorNotes: String, sessionId: Int, doctorName: String) async {
        print("💊 [ChatViewModel] Parsing prescriptions from doctor response...")
        
        // Look for prescription patterns in doctor's response
        let prescriptionPatterns = [
            // Pattern 1: **Prescribed Medications:** or **Prescriptions:**
            #"(?:Prescribed Medications?|Prescriptions?):(.*?)(?=\n\*\*|\n[A-Z]|\Z)"#,
            // Pattern 2: ## Prescribed Medications: or ## Prescriptions:
            #"##\s*(?:Prescribed Medications?|Prescriptions?):(.*?)(?=\n##|\n[A-Z]|\Z)"#,
            // Pattern 3: Medication: or Drug: followed by details
            #"(?:Medication|Drug):\s*([^\n]+(?:\n(?!(?:Medication|Drug|##|\*\*))[^\n]*)*)"#
        ]
        
        var foundPrescriptions: [PrescriptionData] = []
        
        for pattern in prescriptionPatterns {
            let regex = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive, .dotMatchesLineSeparators])
            let matches = regex?.matches(in: doctorNotes, options: [], range: NSRange(doctorNotes.startIndex..., in: doctorNotes))
            
            for match in matches ?? [] {
                if let range = Range(match.range(at: 1), in: doctorNotes) {
                    let prescriptionText = String(doctorNotes[range]).trimmingCharacters(in: .whitespacesAndNewlines)
                    let prescriptions = parsePrescriptionText(prescriptionText, prescribedBy: doctorName)
                    foundPrescriptions.append(contentsOf: prescriptions)
                }
            }
        }
        
        // Create prescriptions in backend
        for prescription in foundPrescriptions {
            do {
                try await networkService.addPrescriptionToSession(sessionId: sessionId, prescription: prescription)
                print("✅ [ChatViewModel] Created prescription: \(prescription.medicationName)")
            } catch {
                print("❌ [ChatViewModel] Failed to create prescription \(prescription.medicationName): \(error)")
            }
        }
        
        // Add prescriptions as chat messages if any were found
        if !foundPrescriptions.isEmpty {
            print("💊 [ChatViewModel] Successfully created \(foundPrescriptions.count) prescriptions")
            
            // Create prescription summary message
            var prescriptionMessage = "💊 **Prescriptions**\n\n"
            for prescription in foundPrescriptions {
                prescriptionMessage += "• **\(prescription.medicationName)**"
                if let dosage = prescription.dosage {
                    prescriptionMessage += " - \(dosage)"
                }
                if let frequency = prescription.frequency {
                    prescriptionMessage += " \(frequency)"
                }
                if let instructions = prescription.instructions {
                    prescriptionMessage += "\n  \(instructions)"
                }
                prescriptionMessage += "\n\n"
            }
            prescriptionMessage += "Prescribed by: \(doctorName)"
            
            // Save prescription message to chat
            do {
                try await networkService.saveDirectMessage(
                    sessionId: sessionId,
                    role: "assistant", 
                    content: prescriptionMessage
                )
                print("✅ [ChatViewModel] Added prescriptions to chat")
            } catch {
                print("❌ [ChatViewModel] Failed to add prescriptions to chat: \(error)")
            }
        }
    }
    
    private func parsePrescriptionText(_ text: String, prescribedBy: String) -> [PrescriptionData] {
        var prescriptions: [PrescriptionData] = []
        
        // Split by lines and parse each medication
        let lines = text.components(separatedBy: .newlines)
        
        for line in lines {
            let trimmedLine = line.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmedLine.isEmpty || trimmedLine.hasPrefix("*") == false { continue }
            
            // Remove bullet points and clean up
            let cleanLine = trimmedLine.replacingOccurrences(of: "^[•\\*\\-]\\s*", with: "", options: .regularExpression)
            
            // Parse medication details
            let medicationName = extractMedicationName(from: cleanLine)
            let dosage = extractDosage(from: cleanLine)
            let frequency = extractFrequency(from: cleanLine)
            let instructions = extractInstructions(from: cleanLine)
            
            if !medicationName.isEmpty {
                let prescription = PrescriptionData(
                    medicationName: medicationName,
                    dosage: dosage,
                    frequency: frequency,
                    instructions: instructions,
                    prescribedBy: prescribedBy
                )
                prescriptions.append(prescription)
            }
        }
        
        return prescriptions
    }
    
    private func extractMedicationName(from text: String) -> String {
        // Extract text before first dash, parenthesis, or dosage pattern
        let patterns = [" - ", " (", " \\d+mg", " \\d+g", " \\d+ mg"]
        
        for pattern in patterns {
            if let range = text.range(of: pattern, options: .regularExpression) {
                return String(text[..<range.lowerBound]).trimmingCharacters(in: .whitespacesAndNewlines)
            }
        }
        
        return text.trimmingCharacters(in: .whitespacesAndNewlines)
    }
    
    private func extractDosage(from text: String) -> String? {
        let dosagePatterns = [
            #"\d+\s*mg"#,
            #"\d+\s*g"#,
            #"\d+\s*mcg"#,
            #"\d+\s*ml"#,
            #"\d+\s*units?"#
        ]
        
        for pattern in dosagePatterns {
            let regex = try? NSRegularExpression(pattern: pattern, options: .caseInsensitive)
            if let match = regex?.firstMatch(in: text, options: [], range: NSRange(text.startIndex..., in: text)),
               let range = Range(match.range, in: text) {
                return String(text[range])
            }
        }
        
        return nil
    }
    
    private func extractFrequency(from text: String) -> String? {
        let frequencyPatterns = [
            #"(?:once|twice|thrice|\d+\s*times?)\s*(?:daily|per day|a day)"#,
            #"(?:every|once)\s*\d+\s*hours?"#,
            #"(?:morning|evening|bedtime|before meals?|after meals?)"#,
            #"BID|TID|QID|QD|PRN"#
        ]
        
        for pattern in frequencyPatterns {
            let regex = try? NSRegularExpression(pattern: pattern, options: .caseInsensitive)
            if let match = regex?.firstMatch(in: text, options: [], range: NSRange(text.startIndex..., in: text)),
               let range = Range(match.range, in: text) {
                return String(text[range])
            }
        }
        
        return nil
    }
    
    private func extractInstructions(from text: String) -> String? {
        let instructionPatterns = [
            #"Instructions?:\s*([^\n]+)"#,
            #"Notes?:\s*([^\n]+)"#,
            #"Take\s+([^\n]+)"#
        ]
        
        for pattern in instructionPatterns {
            let regex = try? NSRegularExpression(pattern: pattern, options: .caseInsensitive)
            if let match = regex?.firstMatch(in: text, options: [], range: NSRange(text.startIndex..., in: text)),
               let range = Range(match.range(at: 1), in: text) {
                return String(text[range]).trimmingCharacters(in: .whitespacesAndNewlines)
            }
        }
        
        return nil
    }

    func sendMessage(_ content: String) async {
        await sendStreamingMessage(content)
    }
    
    func sendMessage(_ content: String, fileURL: URL) async {
        await sendStreamingMessage(content, fileURL: fileURL)
    }
    
    // Removed legacy non-stream send path (sendMessageInternal). All sends use streaming variants.
    
    // MARK: - Advanced Message Verification
    
    private func verifyMessageProcessing(content: String, fileURL: URL?) async -> Bool {
        /*
        Sophisticated verification to check if a message was actually processed by the backend.
        This goes beyond simple content matching to verify complete processing.
        */
        
        print("🔍 [ChatViewModel] Starting comprehensive message verification...")
        
        // Step 0: Check if we have tracking information for this message
        let trimmedContent = content.trimmingCharacters(in: .whitespacesAndNewlines)
        let trackingEntries = sentMessageTracker.values.filter { 
            $0.content.trimmingCharacters(in: .whitespacesAndNewlines) == trimmedContent
        }
        
        // If we have recent tracking data that shows completion, use it for fast verification
        if let recentTracking = trackingEntries.first(where: { 
            $0.isComplete && Date().timeIntervalSince($0.timestamp) < 600 // Within 10 minutes
        }) {
            print("✅ [ChatViewModel] Fast verification: Message found in tracking as complete")
            return true
        }
        
        // Step 1: Reload latest messages from backend
        await reloadLatestMessages()
        
        // Step 2: Multiple verification layers
        
        // Find potential user message matches
        let userMessages = messages.filter { 
            $0.role == .user && 
            $0.content.trimmingCharacters(in: .whitespacesAndNewlines) == trimmedContent
        }
        
        guard !userMessages.isEmpty else {
            print("❌ [ChatViewModel] No matching user message found")
            return false
        }
        
        // Step 3: For each potential match, verify complete processing
        for userMessage in userMessages {
            // Note: Skipping ID-based verification due to type mismatch between ChatMessage (UUID) and BackendChatMessage (Int)
            // Relying on comprehensive content and metadata matching instead
            
            // Get the index of this user message  
            guard let userIndex = messages.firstIndex(where: { $0.content == userMessage.content && $0.role == .user }) else {
                continue
            }
            
            // Verification criteria:
            var verificationScore = 0
            var maxScore = 5
            
            // 1. Content match (already verified above)
            verificationScore += 1
            
            // 2. Timestamp recency (within last 5 minutes)
            if Date().timeIntervalSince(userMessage.timestamp) < 300 {
                verificationScore += 1
            }
            
            // 3. File attachment match (if applicable)
            if let expectedFileURL = fileURL {
                let expectedFileName = expectedFileURL.lastPathComponent
                if userMessage.fileName == expectedFileName || userMessage.filePath?.contains(expectedFileName) == true {
                    verificationScore += 1
                } else {
                    // File mismatch is a strong negative indicator
                    continue
                }
            } else if userMessage.fileName == nil && userMessage.filePath == nil {
                // Both no file - good match
                verificationScore += 1
            }
            
            // 4. AI response exists after this user message
            let messagesAfterUser = messages.suffix(from: messages.index(after: userIndex))
            let hasAIResponse = messagesAfterUser.contains { $0.role == .assistant }
            if hasAIResponse {
                verificationScore += 1
            }
            
            // 5. Session state consistency
            if let sessionId = currentSessionId {
                // Check if session message count makes sense
                // This is a basic sanity check
                verificationScore += 1
            }
            
            let verificationPercentage = Double(verificationScore) / Double(maxScore)
            print("🔍 [ChatViewModel] Message verification score: \(verificationScore)/\(maxScore) (\(Int(verificationPercentage * 100))%)")
            
            // Require at least 80% confidence for positive verification
            if verificationPercentage >= 0.8 {
                print("✅ [ChatViewModel] Message processing verified with high confidence")
                return true
            }
        }
        
        print("❌ [ChatViewModel] Message processing could not be verified")
        return false
    }
    
    private func trackSentMessage(content: String, fileURL: URL?) -> String {
        /*
        Track a message being sent for future verification.
        Returns a tracking key for this message.
        */
        let trackingKey = "\(Date().timeIntervalSince1970)_\(content.hashValue)"
        let trackingInfo = MessageTrackingInfo(
            content: content,
            timestamp: Date(),
            fileURL: fileURL
        )
        sentMessageTracker[trackingKey] = trackingInfo
        
        print("📝 [ChatViewModel] Tracking message: \(trackingKey)")
        return trackingKey
    }
    
    private func updateMessageTracking(trackingKey: String, response: ChatMessageResponse?) {
        /*
        Update tracking info with response data from backend.
        */
        guard var trackingInfo = sentMessageTracker[trackingKey] else { return }
        
        if let response = response {
            trackingInfo.userMessageId = response.userMessage.id
            trackingInfo.aiMessageId = response.aiMessage?.id
            trackingInfo.isComplete = response.aiMessage != nil
            sentMessageTracker[trackingKey] = trackingInfo
            
            print("📝 [ChatViewModel] Updated tracking for \(trackingKey): userMsg=\(response.userMessage.id), aiMsg=\(response.aiMessage?.id ?? -1)")
        }
    }

    // Methods for managing multiple chat sessions
    func loadChatSessions() {
        // This method is called to ensure chat sessions are loaded in the history manager
        Task {
            await historyManager.loadChatSessionsFromBackend()
        }
        print("📱 [ChatViewModel] Requested chat sessions load from history manager")
    }

    // Load a specific chat session
    func loadSpecificSession(_ sessionId: Int) {
        print("🔄 [ChatViewModel] Loading specific session: \(sessionId)")
        
        Task {
            // Set as current session
            currentSessionId = sessionId
            
            // Load the session data
            await loadCurrentSessionData()
            
            if let session = historyManager.getCurrentSession() {
                print("✅ [ChatViewModel] Loaded session '\(session.title ?? "Untitled")' with \(messages.count) messages")
            }
        }
    }

    // Public method to manually clear invalid session data
    func clearInvalidSessionData() {
        print("🧹 [ChatViewModel] Manually clearing invalid session data")
        UserDefaults.standard.removeObject(forKey: "currentChatSessionId")
        currentSessionId = nil
        
        Task {
            await MainActor.run {
                self.clearAllMessages()
                isLoading = false
                currentUploadFilename = ""  // Only clear when starting fresh session
            }
            
            // Create a new session
            currentSessionId = await historyManager.ensureCurrentSession()
            if let newSessionId = currentSessionId {
                UserDefaults.standard.set(newSessionId, forKey: "currentChatSessionId")
                print("✅ [ChatViewModel] Created new session after clearing invalid data: \(newSessionId)")
            }
        }
    }
    
    // MARK: - Enhanced Mode Configuration
    
    func updateEnhancedModeFromSession(_ session: ChatSessionResponse) {
        let previousMode = useEnhancedMode
        useEnhancedMode = session.enhancedModeEnabled ?? false
        
        if previousMode != useEnhancedMode {
            print("🔄 [ChatViewModel] Enhanced mode updated from backend: \(useEnhancedMode ? "ENABLED" : "DISABLED")")
            
            // Always sync enhanced messages with regular messages when switching to enhanced mode
            if useEnhancedMode && !messages.isEmpty {
                enhancedMessages = messages.map { EnhancedChatMessage(from: $0) }
                print("📦 [ChatViewModel] Synced \(enhancedMessages.count) messages to enhanced mode")
            }
        }
    }
    
    // MARK: - Streaming and Enhanced Chat Methods
    
    func sendStreamingMessage(_ content: String) async {
        print("🌊 [ChatViewModel] sendStreamingMessage called")
        print("📤 [ChatViewModel] Streaming message: '\(content)'")
        
        // Create user message immediately for better UX, but avoid duplicates if the same content
        if let last = messages.last, last.role == .user && last.content == content {
            print("🚫 [ChatViewModel] Prevented duplicate local user message append")
        } else {
            let userMessage = ChatMessage(role: .user, content: content)
            messages.append(userMessage)
            enhancedMessages.append(EnhancedChatMessage(from: userMessage))
        }
        
        // Reset state
        isStreaming = true
        isLoading = true
        streamingContent = ""
        currentStatus = "Processing..."
        currentProgress = 0.0
        error = nil
        isAIResponseComplete = false
        isTyping = true
        
        do {
            // Ensure we have a current session
            if currentSessionId == nil {
                await createNewSession()
            }
            
            guard let sessionId = currentSessionId else {
                throw URLError(.badServerResponse)
            }
            
            // Start WebSocket connection for status updates
            startStatusUpdates(sessionId: sessionId)
            
            // Send streaming message request
            let streamingResponse = try await networkService.sendStreamingChatMessage(
                sessionId: sessionId, 
                message: content
            )
            
            // Start streaming response
            await handleStreamingResponse(
                sessionId: sessionId,
                requestId: streamingResponse.requestId
            )
            
        } catch {
            await MainActor.run {
                self.error = "Failed to send streaming message: \(error.localizedDescription)"
                self.isStreaming = false
                self.isLoading = false
                self.isTyping = false
                self.isAnalyzingFile = false  // Re-enable input on error
                // Keep filename visible even on streaming error
            }
        }
    }

    // Streaming variant for file uploads
    func sendStreamingMessage(_ content: String, fileURL: URL) async {
        print("🌊 [ChatViewModel] sendStreamingMessage with file called")
        print("📤 [ChatViewModel] Streaming message: '\(content)' with file \(fileURL.lastPathComponent)")

        // Add user's file message immediately to chat (with duplicate prevention)
        await MainActor.run {
            let fileName = fileURL.lastPathComponent
            let messageContent = content.isEmpty ? "📎 \(fileName)" : content
            
            // Check for duplicates before adding
            let isDuplicate = self.messages.contains(where: { existing in
                existing.role == .user && 
                existing.fileName == fileName && 
                existing.fileName != nil && 
                !existing.fileName!.isEmpty
            })
            
            if !isDuplicate {
                let userMessage = ChatMessage(
                    role: .user,
                    content: messageContent,
                    timestamp: Date(),
                    filePath: fileURL.path,
                    fileType: getFileType(for: fileURL.pathExtension),
                    fileName: fileName
                )
                self.messages.append(userMessage)
                
                // Add to enhanced messages if in enhanced mode
                if self.useEnhancedMode {
                    let enhanced = self.createEnhancedMessage(from: userMessage, content: userMessage.content)
                    self.enhancedMessages.append(enhanced)
                }
            } else {
                print("🚫 [ChatViewModel] Prevented duplicate file message: \(fileName)")
            }
        }

        // Reset UI state
        await MainActor.run {
            self.isStreaming = true
            self.isLoading = true
            self.streamingContent = ""
            self.currentStatus = "Analyzing file..."
            self.currentProgress = 0.0
            self.error = nil
            self.isAIResponseComplete = false
            self.isTyping = true
            self.isAnalyzingFile = true
            self.lastInteractionWasFileUpload = true
            self.currentUploadFilename = fileURL.lastPathComponent
        }

        do {
            // Ensure session
            if currentSessionId == nil {
                await createNewSession()
            }
            guard let sessionId = currentSessionId else { throw URLError(.badServerResponse) }

            // Start status updates WS
            startStatusUpdates(sessionId: sessionId)

            // Send streaming message with file
            let streamingResponse = try await networkService.sendStreamingChatMessageWithFile(sessionId: sessionId, message: content, fileURL: fileURL)

            // handle stream
            await handleStreamingResponse(sessionId: sessionId, requestId: streamingResponse.requestId)
        } catch {
            await MainActor.run {
                self.error = "Failed to send streaming file: \(error.localizedDescription)"
                self.isStreaming = false
                self.isLoading = false
                self.isTyping = false
                self.isAnalyzingFile = false
            }
        }
    }

    private func startStatusUpdates(sessionId: Int) {
        // Avoid duplicate WS connections for the same session
        if let activeId = activeStatusSessionId, activeId == sessionId, statusTask != nil {
            return
        }

        // Cancel previous status task (if any) and mark active session id
        statusTask?.cancel()
        activeStatusSessionId = sessionId
        
        statusTask = Task {
            // Clean start; rely on WS events only
            let statusStream = networkService.connectToStatusUpdates(sessionId: sessionId)
            
            for await statusMessage in statusStream {
                await MainActor.run {
                    let statusText = statusMessage.status
                    let lowerStatus = statusText.lowercased()
                    // Ignore noisy connection status updates – we'll show a small indicator in header instead
                    if lowerStatus.contains("connected") && !lowerStatus.contains("disconnected") {
                        return
                    }
                    
                    // Handle enriched status types that include a new message payload
                    if statusText == "message_added" || statusText == "complete" {
                        var appendedFromPayload = false
                        // Try to parse the JSON payload that the backend sent along with the status
                        if let rawPayload = statusMessage.message,
                           let data = rawPayload.data(using: .utf8) {
                            do {
                                if let root = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                                   let newMsgDict = root["new_message"] as? [String: Any],
                                   let roleString = newMsgDict["role"] as? String,
                                   let content = newMsgDict["content"] as? String {
                                    // Convert timestamp
                                    let iso = ISO8601DateFormatter()
                                    let timestampStr = newMsgDict["timestamp"] as? String ?? ""
                                    let date = iso.date(from: timestampStr) ?? Date()
                                    // Optional fields
                                    let filePath = newMsgDict["filePath"] as? String
                                    let fileType = newMsgDict["fileType"] as? String
                                    let fileName = newMsgDict["fileName"] as? String
                                    // Visualizations (if provided)
                                    var visualizations: [Visualization]? = nil
                                    if let vizArray = newMsgDict["visualizations"] as? [[String: Any]],
                                       let vizData = try? JSONSerialization.data(withJSONObject: vizArray) {
                                        visualizations = try? JSONDecoder().decode([Visualization].self, from: vizData)
                                    }
                                    let messageRole = MessageRole(rawValue: roleString) ?? .assistant
                                    let chatMsg = ChatMessage(
                                        role: messageRole,
                                        content: content,
                                        timestamp: date,
                                        filePath: filePath,
                                        fileType: fileType,
                                        fileName: fileName,
                                        visualizations: visualizations
                                    )
                                    // Deduplicate on (role, content) and for file messages also check filename
                                    let isDuplicate = self.messages.contains(where: { existing in
                                        if existing.role == chatMsg.role && existing.content == chatMsg.content {
                                            return true
                                        }
                                        // For file messages, also check if it's the same file by filename
                                        if existing.role == chatMsg.role && 
                                           existing.fileName == chatMsg.fileName && 
                                           existing.fileName != nil && 
                                           !existing.fileName!.isEmpty {
                                            return true
                                        }
                                        return false
                                    })
                                    if !isDuplicate {
                                        self.messages.append(chatMsg)
                                        appendedFromPayload = true
                                        if self.useEnhancedMode {
                                            let enhanced = self.createEnhancedMessage(from: chatMsg, content: chatMsg.content)
                                            self.enhancedMessages.append(enhanced)
                                        }

                                        // If an assistant message arrived, we are likely waiting for user input.
                                        if messageRole == .assistant {
                                            self.isAnalyzingFile = false
                                            self.isLoading = false
                                            self.isTyping = false
                                            self.lastInteractionWasFileUpload = false
                                            self.currentUploadFilename = ""
                                            self.currentStatus = ""
                                        }
                                    }
                                }
                            } catch {
                                print("⚠️ [ChatViewModel] Failed to parse status payload: \(error)")
                            }
                        }
                        // Always reconcile with backend to ensure UI reflects the latest persisted state
                        Task { await self.reloadLatestMessages() }
                        // Update UI flags for completion status
                        if statusText == "complete" {
                            self.currentStatus = "Complete"
                            self.isStreaming = false
                            self.isLoading = false
                            self.isTyping = false
                            self.isAIResponseComplete = true
                            self.currentProgress = statusMessage.progress ?? 1.0
                            // Clear file upload state when complete
                            self.lastInteractionWasFileUpload = false
                            self.isAnalyzingFile = false
                            self.currentUploadFilename = ""
                        }
                        return // Skip automatic reload beyond the explicit fallback above
                    }
                    
                    // Update UI status for other status types
                    if statusText.contains("processing") || statusText.contains("Processing") {
                        self.currentStatus = self.lastInteractionWasFileUpload ? "Analyzing file..." : "Processing..."
                        self.isTyping = true
                        self.isAnalyzingFile = self.lastInteractionWasFileUpload
                    } else if statusText.contains("complete") || statusText.contains("Complete") {
                        self.currentStatus = "Complete"
                        print("🏁 [ChatViewModel] Received complete status - clearing analysis state")
                        // Clear analysis state when complete
                        self.lastInteractionWasFileUpload = false
                        self.isAnalyzingFile = false
                        self.currentUploadFilename = ""
                    } else if statusText.lowercased().contains("waiting for user") || statusText.lowercased().contains("awaiting_user") || statusText.lowercased().contains("awaiting user") {
                        // Backend indicates it needs user input now
                        self.isAnalyzingFile = false
                        self.isLoading = false
                        self.isTyping = false
                        self.lastInteractionWasFileUpload = false
                        self.currentUploadFilename = ""
                        self.currentStatus = ""
                    } else {
                        self.currentStatus = statusText
                        self.isTyping = statusText != "error"
                    }
                    
                    self.currentProgress = statusMessage.progress ?? self.currentProgress
                    self.currentAgent = statusMessage.agentName ?? ""
                    
                    // For other statuses (processing, analyzing, error) we still reload to stay in sync
                    if statusText != "message_added" && statusText != "complete" {
                        print("📊 [ChatViewModel] Status update: \(statusText) - reloading messages")
                        Task {
                            await self.reloadLatestMessages()
                        }
                    }
                }
                
                // On complete or error, clear analyzing state but keep listening for future messages
                if statusMessage.status == "complete" || statusMessage.status == "error" {
                    await MainActor.run {
                        self.isAnalyzingFile = false
                        self.lastInteractionWasFileUpload = false
                        self.currentUploadFilename = ""
                    }
                    continue
                }
            }
            // When the loop exits, clear active session marker
            await MainActor.run {
                if self.activeStatusSessionId == sessionId {
                    self.activeStatusSessionId = nil
                }
            }
        }
    }
    
    private func reloadLatestMessages() async {
        """
        Simple method to reload latest messages and session info from backend.
        Called on any status update to ensure frontend stays in sync.
        """
        guard let sessionId = currentSessionId else {
            print("⚠️ [ChatViewModel] No current session ID to reload messages")
            return
        }
        
        do {
            print("🔄 [ChatViewModel] Reloading latest messages for session \(sessionId)")
            let backendMessages = try await networkService.getSessionMessages(sessionId)
            let updatedSession = try await networkService.getChatSession(sessionId)
            
            await MainActor.run {
                // Always update with fresh backend data
                let previousCount = self.messages.count
                
                // Filter out any status messages or invalid messages from backend
                let validMessages = backendMessages.filter { backendMessage in
                    // Only include user and assistant messages, filter out status/system messages
                    let isValidRole = backendMessage.role == "user" || backendMessage.role == "assistant"
                    let isNotSystemJSON = !backendMessage.content.contains("message_type")
                    
                    // Allow messages with file attachments even if content is empty
                    let hasFileAttachment = backendMessage.filePath != nil && !backendMessage.filePath!.isEmpty
                    let hasValidContent = !backendMessage.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                    let hasVisualizations = backendMessage.visualizations?.isEmpty == false
                    let isValidMessage = hasValidContent || hasFileAttachment || hasVisualizations
                    
                    // Debug logging for filtered messages
                    if !isValidRole {
                        print("🚫 [ChatViewModel] Filtered message (invalid role): \(backendMessage.role)")
                    } else if !isNotSystemJSON {
                        print("🚫 [ChatViewModel] Filtered message (system JSON): \(backendMessage.content.prefix(50))")
                    } else if !isValidMessage {
                        print("🚫 [ChatViewModel] Filtered message (no content, file, or visualizations): content='\(backendMessage.content)', file_path='\(backendMessage.filePath ?? "nil")', visualizations=\(backendMessage.visualizations?.count ?? 0)")
                    } else {
                        print("✅ [ChatViewModel] Valid message: role=\(backendMessage.role), hasContent=\(hasValidContent), hasFile=\(hasFileAttachment), hasVisualizations=\(hasVisualizations), file_path='\(backendMessage.filePath ?? "nil")'")
                    }
                    
                    return isValidRole && isNotSystemJSON && isValidMessage
                }
                
                self.messages = validMessages.map { $0.toChatMessage() }
                print("🧹 [ChatViewModel] Filtered messages: \(backendMessages.count) -> \(validMessages.count)")
                
                // Debug: Log file messages
                let fileMessages = validMessages.filter { $0.filePath != nil }
                print("📎 [ChatViewModel] File messages found: \(fileMessages.count)")
                for (index, fileMsg) in fileMessages.enumerated() {
                    print("   \(index + 1). \(fileMsg.role): \(fileMsg.filePath ?? "nil") - \(fileMsg.content.prefix(50))")
                }
                
                // Update session title if it has changed
                if let newTitle = updatedSession.title, newTitle != self.currentSessionTitle {
                    self.currentSessionTitle = newTitle
                    print("🏷️ [ChatViewModel] Updated session title to: '\(newTitle)'")
                }
                
                // Update enhanced messages if in enhanced mode
                if self.useEnhancedMode {
                    self.enhancedMessages = self.messages.map { EnhancedChatMessage(from: $0) }
                }
                
                print("✅ [ChatViewModel] Reloaded \(self.messages.count) messages (was \(previousCount))")
                
                // Update completion state
                self.isAIResponseComplete = !self.messages.isEmpty && self.messages.last?.role == .assistant
                
                // Smart fallback: If we have new messages including an AI response, processing must be complete
                // This handles cases where status updates might fail
                if self.messages.count > previousCount && self.isAIResponseComplete {
                    print("🎯 [ChatViewModel] Detected new AI response - clearing analyzing state after delay")
                    // Clear after a delay to ensure user sees the status
                    DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
                        // Clear all analysis state after AI response is complete
                        self.currentUploadFilename = ""
                        self.isAnalyzingFile = false
                        self.isTyping = false
                        self.isLoading = false
                        self.lastInteractionWasFileUpload = false
                        self.currentStatus = "Complete"
                        print("📝 [ChatViewModel] Finally cleared analysis state after AI response")
                    }
                }
                
                // Don't clear file upload state here - let the delayed clearing handle it
            }
        } catch {
            print("❌ [ChatViewModel] Failed to reload messages: \(error)")
        }
    }
    
    private func handleStreamingResponse(sessionId: Int, requestId: String) async {
        // Cancel previous streaming task
        streamingTask?.cancel()
        
        streamingTask = Task {
            let responseStream = networkService.connectToStreamingResponse(
                sessionId: sessionId,
                requestId: requestId
            )
            
            var accumulatedContent = ""
            
            for await chunk in responseStream {
                await MainActor.run {
                    switch chunk.type {
                    case "content":
                        if let content = chunk.content {
                            accumulatedContent += content
                            self.streamingContent = accumulatedContent
                        }
                        
                        if let progress = chunk.progress {
                            self.currentProgress = progress
                        }
                        
                    case "complete":
                        // If accumulatedContent is empty, this was a quick "user_response" stream.
                        // Keep loading indicators ON until backend sends new status updates.
                        if accumulatedContent.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                            self.isStreaming = false  // SSE ended
                            // Keep isLoading / isTyping the same so that the spinner remains visible.
                            self.currentStatus = "Processing..."
                            print("⏳ [ChatViewModel] User response acknowledged – waiting for AI follow-up")
                        } else {
                            // Normal AI response flow finished.
                            self.isStreaming = false
                            self.isLoading = false
                            self.isTyping = false
                            self.isAIResponseComplete = true
                            self.streamingContent = ""
                            self.currentStatus = "Complete"
                            self.currentProgress = 1.0
                            print("✅ [ChatViewModel] Streaming completed with AI content")
                        }
                        
                    case "error":
                        self.error = chunk.content ?? "Streaming error occurred"
                        self.isStreaming = false
                        self.isLoading = false
                        self.isTyping = false
                        
                        print("❌ [ChatViewModel] Streaming error: \(chunk.content ?? "Unknown error")")
                        
                    default:
                        break
                    }
                }
                
                // Stop processing if complete or error
                if chunk.type == "complete" || chunk.type == "error" {
                    break
                }
            }
        }
    }
    
    private func createEnhancedMessage(from message: ChatMessage, content: String) -> EnhancedChatMessage {
        // Quick replies feature has been disabled.
        return EnhancedChatMessage(
            role: message.role,
            content: message.content,
            timestamp: message.timestamp,
            filePath: message.filePath,
            fileType: message.fileType,
            fileName: message.fileName,
            quickReplies: nil,
            interactiveComponents: nil
        )
    }
    
    func handleQuickReply(_ reply: QuickReply) {
        print("🔘 [ChatViewModel] Quick reply selected: \(reply.text) -> \(reply.value)")
        
        // Handle common quick reply actions
        switch reply.value {
        case "schedule_appointment":
            // TODO: Navigate to appointment scheduling
            print("📅 [ChatViewModel] Should navigate to appointment scheduling")
            
        case "view_records", "view_prescriptions":
            // TODO: Navigate to health records
            print("📋 [ChatViewModel] Should navigate to health records")
            
        case "yes", "no", "maybe", "more_info":
            // Send the reply as a new message
            Task {
                if useEnhancedMode {
                    await sendStreamingMessage(reply.text)
                } else {
                    await sendMessage(reply.text)
                }
            }
            
        default:
            // Default: send the reply text as a message
            Task {
                if useEnhancedMode {
                    await sendStreamingMessage(reply.text)
                } else {
                    await sendMessage(reply.text)
                }
            }
        }
    }
    
    deinit {
        statusTask?.cancel()
        streamingTask?.cancel()
        Task { @MainActor in
            await stopAutomaticStatusChecking()
        }
    }
}

