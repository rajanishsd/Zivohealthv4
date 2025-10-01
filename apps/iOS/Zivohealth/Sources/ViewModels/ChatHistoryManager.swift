import Foundation
import SwiftUI

class ChatHistoryManager: ObservableObject {
    static let shared = ChatHistoryManager()
    
    @Published var chatSessions: [ChatSessionResponse] = []
    @Published var currentSessionId: Int?
    
    private let networkService = NetworkService.shared
    
    private init() {
        // Initialize with backend data
        Task {
            await loadChatSessionsFromBackend()
        }
    }
    
    // MARK: - Session Management
    
    @MainActor
    func createNewSession(title: String? = nil) async -> Int? {
        do {
            let sessionTitle = title ?? generateSessionTitle()
            let newSession = try await networkService.createChatSession(title: sessionTitle)
            
            // Add to beginning for recent-first order
            chatSessions.insert(newSession, at: 0)
            currentSessionId = newSession.id
            
            print("📝 [ChatHistoryManager] Created new session: \(newSession.title ?? "Untitled")")
            return newSession.id
        } catch {
            print("❌ [ChatHistoryManager] Error creating session: \(error)")
            return nil
        }
    }
    
    @MainActor
    func switchToSession(_ sessionId: Int) {
        guard chatSessions.contains(where: { $0.id == sessionId }) else {
            print("❌ [ChatHistoryManager] Session not found: \(sessionId)")
            return
        }
        
        currentSessionId = sessionId
        print("🔄 [ChatHistoryManager] Switched to session: \(sessionId)")
    }
    
    @MainActor
    func refreshSession(_ sessionId: Int) async {
        do {
            let updatedSession = try await networkService.getChatSession(sessionId)
            
            if let index = chatSessions.firstIndex(where: { $0.id == sessionId }) {
                chatSessions[index] = updatedSession
                
                // Move to top if it's the current session and has activity
                if sessionId == currentSessionId && index > 0 {
                    chatSessions.remove(at: index)
                    chatSessions.insert(updatedSession, at: 0)
                }
            }
            
            print("📊 [ChatHistoryManager] Updated session: \(updatedSession.title ?? "Untitled")")
        } catch {
            print("❌ [ChatHistoryManager] Error refreshing session: \(error)")
        }
    }
    
    @MainActor
    func deleteSession(_ sessionId: Int) async {
        do {
            // Call backend to delete the session
            try await networkService.deleteChatSession(sessionId: sessionId)
            
            // Remove from local array only after successful backend deletion
            chatSessions.removeAll { $0.id == sessionId }
            
            // If this was the current session, create a new one
            if currentSessionId == sessionId {
                currentSessionId = await createNewSession()
            }
            
            print("✅ [ChatHistoryManager] Successfully deleted session: \(sessionId)")
        } catch {
            print("❌ [ChatHistoryManager] Error deleting session \(sessionId): \(error)")
            // You might want to show an error to the user here
        }
    }
    
    func getCurrentSession() -> ChatSessionResponse? {
        guard let sessionId = currentSessionId else { return nil }
        return chatSessions.first { $0.id == sessionId }
    }
    
    @MainActor
    func ensureCurrentSession() async -> Int? {
        if let sessionId = currentSessionId,
           chatSessions.contains(where: { $0.id == sessionId }) {
            return sessionId
        } else {
            return await createNewSession()
        }
    }
    
    // MARK: - Backend Integration
    
    @MainActor
    func loadChatSessionsFromBackend() async {
        do {
            let sessions = try await networkService.getChatSessions()
            chatSessions = sessions.sorted { 
                ($0.lastMessageAt ?? $0.createdAt) > ($1.lastMessageAt ?? $1.createdAt) 
            }
            
            // Set current session to the most recent one with messages, or create new
            if let mostRecentSession = chatSessions.first(where: { ($0.messageCount ?? 0) > 0 }) {
                currentSessionId = mostRecentSession.id
            } else if currentSessionId == nil {
                currentSessionId = await createNewSession()
            }
            
            print("📱 [ChatHistoryManager] Loaded \(sessions.count) chat sessions from backend")
        } catch {
            print("❌ [ChatHistoryManager] Error loading sessions from backend: \(error)")
            // Create initial session if loading fails
            if currentSessionId == nil {
                currentSessionId = await createNewSession()
            }
        }
    }
    
    @MainActor
    func clearAllChatSessions() async {
        // Note: Backend doesn't have bulk delete, so we'll just clear local array
        chatSessions.removeAll()
        
        // Create a new initial session
        currentSessionId = await createNewSession()
        
        print("🗑️ [ChatHistoryManager] Cleared all chat sessions and created new session")
    }
    
    public func loadSessionMessages(_ sessionId: Int) async -> [ChatMessage] {
        print("📥 [ChatHistoryManager] Loading messages for session: \(sessionId)")
        
        do {
            let backendMessages = try await networkService.getSessionMessages(sessionId)
            
            let chatMessages = backendMessages.map { backendMessage in
                backendMessage.toChatMessage()
            }
            
            print("✅ [ChatHistoryManager] Loaded \(chatMessages.count) messages for session \(sessionId)")
            return chatMessages
        } catch {
            print("❌ [ChatHistoryManager] Error loading messages for session \(sessionId): \(error)")
            return []
        }
    }
    
    // MARK: - Helper Methods
    
    private func generateSessionTitle() -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return "Chat - \(formatter.string(from: Date()))"
    }
    
    // MARK: - Legacy Methods (Removed - No longer needed with backend storage)
    
    // All UserDefaults-based methods have been removed:
    // - getSessionMessages() - now handled by ChatViewModel directly from backend
    // - saveSessionMessages() - now handled by backend automatically
    // - getSessionPrescriptions() - prescriptions handled separately
    // - saveSessionPrescriptions() - prescriptions handled separately
    // - getSessionVerification() - verification handled separately
    // - saveSessionVerification() - verification handled separately
} 