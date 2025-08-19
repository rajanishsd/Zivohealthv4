import Foundation
import SwiftUI
import Combine

// MARK: - Upload Progress Delegate
class UploadProgressDelegate: NSObject, URLSessionTaskDelegate {
    let progressHandler: (Double) -> Void
    
    init(progressHandler: @escaping (Double) -> Void) {
        self.progressHandler = progressHandler
    }
    
    func urlSession(_ session: URLSession, task: URLSessionTask, didSendBodyData bytesSent: Int64, totalBytesSent: Int64, totalBytesExpectedToSend: Int64) {
        let progress = Double(totalBytesSent) / Double(totalBytesExpectedToSend)
        DispatchQueue.main.async {
            self.progressHandler(progress)
        }
    }
}

public class NetworkService: ObservableObject {
    public static let shared = NetworkService()

    @AppStorage("apiEndpoint") private var apiEndpoint = "http://192.168.0.105:8000"
    @AppStorage("patientAuthToken") private var patientAuthToken = ""
    @AppStorage("doctorAuthToken") private var doctorAuthToken = ""
    @AppStorage("doctorRefreshToken") private var doctorRefreshToken = ""
    @AppStorage("userMode") private var userMode: UserMode = .doctor

    private let apiVersion = "/api/v1"
    private let maxRetries = 3
    private let retryDelay: TimeInterval = 1.0
    
    // Custom URLSession with extended timeout for file uploads
    private lazy var urlSession: URLSession = {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 300.0    // 5 minutes for regular requests (increased from 30 seconds)
        config.timeoutIntervalForResource = 300.0   // 5 minutes for resources (file uploads)
        config.waitsForConnectivity = true          // Wait for connectivity instead of failing immediately
        config.allowsCellularAccess = true
        config.networkServiceType = .default
        
        // Add retry policy for background connections
        config.shouldUseExtendedBackgroundIdleMode = true
        
        return URLSession(configuration: config)
    }()
    
    // Progress tracking
    @Published public var uploadProgress: Double = 0.0
    @Published public var isUploading: Bool = false
    
    // Network state tracking
    @Published public var isNetworkAvailable: Bool = true
    @Published public var isReconnecting: Bool = false
    private var reconnectionTimer: Timer?
    
    // Authentication state
    private var isRefreshingToken: Bool = false
    private let maxAuthRetries = 3
    private var authRetryCount = 0

    // Custom JSON encoder for proper date handling
    private lazy var encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }()

    // Custom JSON decoder for proper date handling
    private lazy var decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let dateString = try container.decode(String.self)
            
            // Try multiple formatters in order of preference
            // ISO8601 with fractional seconds and timezone
            let iso8601WithFractionalSeconds = ISO8601DateFormatter()
            iso8601WithFractionalSeconds.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = iso8601WithFractionalSeconds.date(from: dateString) {
                return date
            }
            
            // ISO8601 with timezone
            let iso8601WithTimezone = ISO8601DateFormatter()
            iso8601WithTimezone.formatOptions = [.withInternetDateTime]
            if let date = iso8601WithTimezone.date(from: dateString) {
                return date
            }
            
            // Format without timezone: "2025-06-17T16:00:00"
            let formatterWithoutTimezone = DateFormatter()
            formatterWithoutTimezone.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
            formatterWithoutTimezone.timeZone = TimeZone.current
            if let date = formatterWithoutTimezone.date(from: dateString) {
                return date
            }
            
            // Format with milliseconds but no timezone: "2025-06-17T16:00:00.000"
            let formatterWithMilliseconds = DateFormatter()
            formatterWithMilliseconds.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSS"
            formatterWithMilliseconds.timeZone = TimeZone.current
            if let date = formatterWithMilliseconds.date(from: dateString) {
                return date
            }
            
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Cannot decode date string \(dateString)")
        }
        
        return decoder
    }()

    public enum NetworkError: Error, LocalizedError {
        case invalidURL
        case invalidRequest
        case invalidResponse
        case decodingError
        case serverError(String)
        case authenticationFailed
        case networkError(Error)

        public var errorDescription: String? {
            switch self {
            case .invalidURL:
                return "Invalid URL"
            case .invalidRequest:
                return "Invalid request"
            case .invalidResponse:
                return "Invalid response"
            case .decodingError:
                return "Data decoding error"
            case let .serverError(message):
                return "Server error: \(message)"
            case .authenticationFailed:
                return "Authentication failed"
            case let .networkError(error):
                return "Network error: \(error.localizedDescription)"
            }
        }
    }

    // Role-based demo credentials
    private var currentCredentials: (email: String, password: String, name: String) {
        switch userMode {
        case .patient:
            return ("patient@zivohealth.com", "patient123", "Demo Patient")
        case .doctor:
            return ("doctor@zivohealth.com", "doctor123", "Demo Doctor")
        }
    }

    // Always reflect latest endpoint
    private var baseURL: String { "\(apiEndpoint)\(apiVersion)" }

    private init() {
        // Initialization complete - baseURL will be computed lazily when first accessed
    }
    
    // MARK: - Public URL Construction
    
    /// Constructs a full URL from a relative path
    /// - Parameter path: The relative path (e.g., "/files/plots/chart.png")
    /// - Returns: Full URL string
    public func fullURL(for path: String) -> String {
        return baseURL + path
    }

    // Centralized API endpoint accessors
    public var apiEndpointConfig: String {
        get { apiEndpoint }
        set { apiEndpoint = newValue }
    }

    private func headers(requiresAuth: Bool = true) -> [String: String] {
        var headers = [
            "Content-Type": "application/json",
            "Accept": "application/json",
        ]

        if requiresAuth {
            headers["Authorization"] = "Bearer \(authToken)"
        }

        return headers
    }

    // Get the appropriate token for current role
    private var authToken: String {
        get {
            switch userMode {
            case .patient:
                return patientAuthToken
            case .doctor:
                return doctorAuthToken
            }
        }
        set {
            switch userMode {
            case .patient:
                patientAuthToken = newValue
            case .doctor:
                doctorAuthToken = newValue
            }
        }
    }

    // MARK: - Token Management

    private struct TokenInfo: Codable {
        let accessToken: String
        let tokenType: String
        let expiresAt: Date
        
        init(from tokenResponse: TokenResponse) {
            self.accessToken = tokenResponse.accessToken
            self.tokenType = tokenResponse.tokenType
            // Set expiration to 55 minutes from now (5 minutes before the actual 60 minute expiration)
            self.expiresAt = Date().addingTimeInterval(55 * 60)
        }
    }

    private func isTokenExpired() -> Bool {
        guard let tokenData = UserDefaults.standard.data(forKey: "\(userMode)_token_info"),
              let tokenInfo = try? decoder.decode(TokenInfo.self, from: tokenData) else {
            return true
        }
        return Date() >= tokenInfo.expiresAt
    }

    private func tryRefreshAccessTokenIfNeeded() async -> Bool {
        guard isTokenExpired() else { return true }
        // Only doctor flow uses refresh token for now
        guard userMode == .doctor, !doctorRefreshToken.isEmpty else { return false }
        do {
            let body: [String: Any] = ["refresh_token": doctorRefreshToken]
            let data = try await post("/auth/refresh", body: body, requiresAuth: false)
            let tokenResponse = try decoder.decode(TokenResponse.self, from: data)
            authToken = tokenResponse.accessToken
            saveTokenInfo(tokenResponse)
            return true
        } catch {
            print("❌ [NetworkService] Token refresh failed: \(error)")
            return false
        }
    }

    private func saveTokenInfo(_ tokenResponse: TokenResponse) {
        let tokenInfo = TokenInfo(from: tokenResponse)
        if let encoded = try? encoder.encode(tokenInfo) {
            UserDefaults.standard.set(encoded, forKey: "\(userMode)_token_info")
        }
    }

    private func clearTokenInfo() {
        UserDefaults.standard.removeObject(forKey: "\(userMode)_token_info")
    }

    public func clearAuthToken() {
        print("🗑️ [NetworkService] Clearing stored auth token for \(userMode)")
        authToken = ""
        clearTokenInfo()
    }

    public func clearAllTokens() {
        print("🗑️ [NetworkService] Clearing all stored auth tokens")
        patientAuthToken = ""
        doctorAuthToken = ""
    }

    public func getCurrentToken() -> String {
        return authToken
    }

    // MARK: - LiveKit Video

    struct VideoConfigResponse: Codable { let url: String }
    struct VideoTokenResponse: Codable { let token: String }

    public func getLiveKitURL() async throws -> String {
        let data = try await get("/video/config", requiresAuth: true)
        let cfg = try decoder.decode(VideoConfigResponse.self, from: data)
        return cfg.url
    }

    public func createLiveKitToken(
        room: String,
        identity: String,
        name: String? = nil,
        metadata: [String: Any]? = nil,
        ttlSeconds: Int = 3600
    ) async throws -> String {
        var body: [String: Any] = [
            "room": room,
            "identity": identity,
            "ttl_seconds": ttlSeconds
        ]
        if let name = name { body["name"] = name }
        if let metadata = metadata { body["metadata"] = metadata }

        let data = try await post("/video/token", body: body, requiresAuth: true)
        let resp = try decoder.decode(VideoTokenResponse.self, from: data)
        return resp.token
    }

    public func forceReauthentication() async throws {
        print("🔄 [NetworkService] Forcing re-authentication for \(userMode)")
        clearAuthToken()
        try await ensureAuthentication()
        print("✅ [NetworkService] Re-authentication completed successfully")
    }

    public func handleRoleChange() {
        print("🔄 [NetworkService] User role changed to \(userMode)")
        print("🔐 [NetworkService] Current \(userMode) token: \(authToken.isEmpty ? "None" : "Exists (\(authToken.count) chars)")")

        // Don't clear the token anymore - each role keeps its own token
        if authToken.isEmpty {
            print("💡 [NetworkService] No token for \(userMode), will authenticate with \(currentCredentials.email) on next API call")
        } else {
            print("✅ [NetworkService] Using existing token for \(userMode)")
        }
    }

    public func clearAllStoredData() {
        print("🗑️ [NetworkService] Clearing ALL stored authentication data")
        patientAuthToken = ""
        doctorAuthToken = ""
        print("✅ [NetworkService] All tokens cleared - next API call will trigger fresh authentication")
    }
    
    public func debugAuthenticationState() {
        print("🔍 [NetworkService] Authentication Debug Info:")
        print("   Current Mode: \(userMode)")
        print("   Patient Token: \(patientAuthToken.isEmpty ? "Empty" : "Exists (\(patientAuthToken.count) chars)")")
        print("   Doctor Token: \(doctorAuthToken.isEmpty ? "Empty" : "Exists (\(doctorAuthToken.count) chars)")")
        print("   Current Credentials: \(currentCredentials.email)")
        print("   API Endpoint: \(apiEndpoint)")
    }

    // MARK: - App Lifecycle Management
    
    public func handleAppDidBecomeActive() {
        print("🟢 [NetworkService] App became active - checking connection and authentication")
        isNetworkAvailable = true
        isReconnecting = false
        stopReconnectionTimer()
        
        // Reset auth retry count
        authRetryCount = 0
        
        // Check if authentication is still valid
        Task {
            do {
                try await ensureAuthentication()
                print("✅ [NetworkService] Authentication validated on app activation")
            } catch {
                print("⚠️ [NetworkService] Authentication validation failed: \(error)")
                // Force token refresh on next request
                clearAuthToken()
            }
        }
    }
    
    public func handleAppDidEnterBackground() {
        print("🔴 [NetworkService] App entered background - preparing for potential network interruption")
        // Don't clear tokens or stop connections immediately
        // iOS will handle background app refresh and network state
        
        // Start monitoring for when we need to reconnect
        startReconnectionTimer()
    }
    
    public func handleEndpointChange() {
        print("🔄 [NetworkService] API endpoint changed to: \(apiEndpoint)")
        // Clear any cached network state
        isNetworkAvailable = true
        isReconnecting = false
        stopReconnectionTimer()
        
        // Clear authentication tokens since endpoint changed
        clearAllTokens()
        
        // Reset auth retry count
        authRetryCount = 0
        
        // Update baseURL will be computed lazily on next request
        print("✅ [NetworkService] Endpoint change handled successfully")
    }
    
    private func startReconnectionTimer() {
        stopReconnectionTimer()
        
        reconnectionTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.checkNetworkConnectivity()
            }
        }
    }
    
    private func stopReconnectionTimer() {
        reconnectionTimer?.invalidate()
        reconnectionTimer = nil
    }
    
    @MainActor
    private func checkNetworkConnectivity() {
        // Simple connectivity check by making a lightweight request
        Task {
            do {
                let url = URL(string: "\(apiEndpoint)/health")!
                var request = URLRequest(url: url)
                request.timeoutInterval = 5.0
                request.httpMethod = "GET"
                
                let (_, response) = try await URLSession.shared.data(for: request)
                if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode < 400 {
                    if !isNetworkAvailable {
                        print("🟢 [NetworkService] Network connectivity restored")
                        isNetworkAvailable = true
                        isReconnecting = false
                        stopReconnectionTimer()
                    }
                }
            } catch {
                if isNetworkAvailable {
                    print("🔴 [NetworkService] Network connectivity lost: \(error)")
                    isNetworkAvailable = false
                    isReconnecting = true
                }
            }
        }
    }

    // MARK: - Chat Management with Backend Storage
    
    public func createChatSession(title: String? = nil) async throws -> ChatSessionResponse {
        print("🌐 [NetworkService] createChatSession called")
        
        let body: [String: Any] = [
            "title": title ?? "New Chat"
        ]
        
        do {
            let data = try await post("/chat-sessions/", body: body, requiresAuth: true)
            let session = try decoder.decode(ChatSessionResponse.self, from: data)
            print("✅ [NetworkService] Created chat session: \(session.id)")
            return session
        } catch {
            print("❌ [NetworkService] Error creating chat session: \(error)")
            throw error
        }
    }
    
    public func getChatSessions() async throws -> [ChatSessionResponse] {
        print("🌐 [NetworkService] getChatSessions called")
        
        do {
            let data = try await get("/chat-sessions/", requiresAuth: true)
            let sessions = try decoder.decode([ChatSessionResponse].self, from: data)
            print("✅ [NetworkService] Retrieved \(sessions.count) chat sessions")
            return sessions
        } catch {
            print("❌ [NetworkService] Error getting chat sessions: \(error)")
            throw error
        }
    }
    
    public func getChatSession(_ sessionId: Int) async throws -> ChatSessionResponse {
        print("🌐 [NetworkService] getChatSession called for ID: \(sessionId)")
        
        do {
            let data = try await get("/chat-sessions/\(sessionId)", requiresAuth: true)
            let session = try decoder.decode(ChatSessionResponse.self, from: data)
            print("✅ [NetworkService] Retrieved chat session: \(session.id)")
            return session
        } catch {
            print("❌ [NetworkService] Error getting chat session: \(error)")
            throw error
        }
    }
    
    public func sendChatMessage(sessionId: Int, message: String) async throws -> ChatMessageResponse {
        print("🌐 [NetworkService] sendChatMessage called for session: \(sessionId)")
        print("📤 [NetworkService] Message: '\(message)'")
        
        let body: [String: Any] = [
            "content": message
        ]
        
        do {
            let data = try await post("/chat-sessions/\(sessionId)/messages", body: body, requiresAuth: true)
            let response = try decoder.decode(ChatMessageResponse.self, from: data)
            print("✅ [NetworkService] Sent chat message, got AI response")
            return response
        } catch {
            print("❌ [NetworkService] Error sending chat message: \(error)")
            throw error
        }
    }
    
    public func sendChatMessageWithFile(sessionId: Int, message: String, fileURL: URL) async throws -> ChatMessageResponse {
        print("🌐 [NetworkService] sendChatMessageWithFile called for session: \(sessionId)")
        print("📤 [NetworkService] Message: '\(message)'")
        print("📎 [NetworkService] File: \(fileURL.lastPathComponent)")
        
        // Create multipart form data
        let boundary = UUID().uuidString
        var request = try await createAuthenticatedRequest(for: "/chat-sessions/\(sessionId)/messages/upload")
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        
        var body = Data()
        
        // Add content field
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"content\"\r\n\r\n".data(using: .utf8)!)
        body.append("\(message)\r\n".data(using: .utf8)!)
        
        // Add file field
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileURL.lastPathComponent)\"\r\n".data(using: .utf8)!)
        
        let mimeType = getMimeType(for: fileURL.pathExtension)
        body.append("Content-Type: \(mimeType)\r\n\r\n".data(using: .utf8)!)
        
        // Add file data
        do {
            let fileData = try Data(contentsOf: fileURL)
            body.append(fileData)
            print("📊 [NetworkService] File size: \(fileData.count) bytes")
        } catch {
            print("❌ [NetworkService] Failed to read file: \(error)")
            throw error
        }
        
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        
        return try await withCheckedThrowingContinuation { continuation in
            // Set upload progress to start
            Task { @MainActor in
                self.isUploading = true
                self.uploadProgress = 0.0
            }
            
            // Create progress delegate
            let progressDelegate = UploadProgressDelegate { progress in
                Task { @MainActor in
                    self.uploadProgress = progress
                }
            }
            
            // Create URLSession with delegate for this upload
            let config = URLSessionConfiguration.default
            config.timeoutIntervalForRequest = 30.0
            config.timeoutIntervalForResource = 300.0
            config.waitsForConnectivity = true
            config.allowsCellularAccess = true
            
            let uploadSession = URLSession(configuration: config, delegate: progressDelegate, delegateQueue: nil)
            
            // Create upload task
            let uploadTask = uploadSession.uploadTask(with: request, from: body) { data, response, error in
                defer {
                    uploadSession.invalidateAndCancel()
                    Task { @MainActor in
                        self.isUploading = false
                    }
                }
                
                if let error = error {
                    print("❌ [NetworkService] Upload task error: \(error)")
                    Task { @MainActor in
                        self.uploadProgress = 0.0
                    }
                    continuation.resume(throwing: NetworkError.networkError(error))
                    return
                }
                
                guard let data = data else {
                    print("❌ [NetworkService] No data received from upload")
                    Task { @MainActor in
                        self.uploadProgress = 0.0
                    }
                    continuation.resume(throwing: NetworkError.invalidResponse)
                    return
                }
                
                guard let httpResponse = response as? HTTPURLResponse else {
                    print("❌ [NetworkService] Invalid response type")
                    Task { @MainActor in
                        self.uploadProgress = 0.0
                    }
                    continuation.resume(throwing: NetworkError.invalidResponse)
                    return
                }
                
                guard 200...299 ~= httpResponse.statusCode else {
                    let errorString = String(data: data, encoding: .utf8) ?? "Unknown error"
                    print("❌ [NetworkService] File upload error: \(httpResponse.statusCode) - \(errorString)")
                    Task { @MainActor in
                        self.uploadProgress = 0.0
                    }
                    continuation.resume(throwing: NetworkError.serverError("HTTP \(httpResponse.statusCode): \(errorString)"))
                    return
                }
                
                do {
                    let chatResponse = try self.decoder.decode(ChatMessageResponse.self, from: data)
                    print("✅ [NetworkService] File uploaded successfully, got AI response")
                    
                    Task { @MainActor in
                        self.uploadProgress = 1.0
                        // Keep progress at 100% for a moment before hiding
                        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                            self.uploadProgress = 0.0
                        }
                    }
                    
                    continuation.resume(returning: chatResponse)
                } catch {
                    print("❌ [NetworkService] Error decoding response: \(error)")
                    Task { @MainActor in
                        self.uploadProgress = 0.0
                    }
                    continuation.resume(throwing: NetworkError.decodingError)
                }
            }
            
            uploadTask.resume()
        }
    }

    // Streaming variant with file upload
    public func sendStreamingChatMessageWithFile(sessionId: Int, message: String, fileURL: URL) async throws -> StreamingChatResponse {
        print("🌐 [NetworkService] sendStreamingChatMessageWithFile called for session: \(sessionId)")
        print("📤 [NetworkService] Streaming message: '\(message)'")
        print("📎 [NetworkService] File: \(fileURL.lastPathComponent)")

        let boundary = UUID().uuidString
        var request = try await createAuthenticatedRequest(for: "/chat-sessions/\(sessionId)/messages/upload/stream")
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()
        // message field
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"content\"\r\n\r\n".data(using: .utf8)!)
        body.append("\(message)\r\n".data(using: .utf8)!)

        // file field
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileURL.lastPathComponent)\"\r\n".data(using: .utf8)!)
        let mimeType = getMimeType(for: fileURL.pathExtension)
        body.append("Content-Type: \(mimeType)\r\n\r\n".data(using: .utf8)!)
        let fileData = try Data(contentsOf: fileURL)
        body.append(fileData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)

        // Upload and decode streaming response
        let (data, response) = try await urlSession.upload(for: request, from: body)
        guard let httpResponse = response as? HTTPURLResponse, 200..<400 ~= httpResponse.statusCode else {
            throw NetworkError.invalidResponse
        }
        let streamResponse = try decoder.decode(StreamingChatResponse.self, from: data)
        return streamResponse
    }

    private func getMimeType(for fileExtension: String) -> String {
        switch fileExtension.lowercased() {
        case "pdf":
            return "application/pdf"
        case "jpg", "jpeg":
            return "image/jpeg"
        case "png":
            return "image/png"
        default:
            return "application/octet-stream"
        }
    }
    
    private func createAuthenticatedRequest(for path: String) async throws -> URLRequest {
        let fullURL = "\(baseURL)\(path)"
        guard let url = URL(string: fullURL) else {
            throw NetworkError.invalidURL
        }
        
        var request = URLRequest(url: url)
        
        // Ensure we're authenticated and get the token
        try await ensureAuthentication()
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        
        return request
    }
    
    public func getSessionMessages(_ sessionId: Int) async throws -> [BackendChatMessage] {
        print("🌐 [NetworkService] getSessionMessages called for session: \(sessionId)")
        
        do {
            let data = try await get("/chat-sessions/\(sessionId)/messages", requiresAuth: true)
            let messages = try decoder.decode([BackendChatMessage].self, from: data)
            print("✅ [NetworkService] Retrieved \(messages.count) messages for session \(sessionId)")
            return messages
        } catch {
            print("❌ [NetworkService] Error getting session messages: \(error)")
            throw error
        }
    }

    // Save a direct message (like doctor responses) without triggering AI generation
    public func saveDirectMessage(sessionId: Int, role: String, content: String) async throws {
        print("🌐 [NetworkService] saveDirectMessage called for session: \(sessionId)")
        print("📤 [NetworkService] Message role: \(role)")
        print("📤 [NetworkService] Message content: '\(content.prefix(100))...'")
        
        let body: [String: Any] = [
            "role": role,
            "content": content
        ]
        
        do {
            let data = try await post("/chat-sessions/\(sessionId)/direct-message", body: body, requiresAuth: true)
            print("✅ [NetworkService] Saved direct message successfully")
        } catch {
            print("❌ [NetworkService] Error saving direct message: \(error)")
            throw error
        }
    }

    // MARK: - Streaming Chat Methods
    
    public func sendStreamingChatMessage(sessionId: Int, message: String) async throws -> StreamingChatResponse {
        print("🌐 [NetworkService] sendStreamingChatMessage called for session: \(sessionId)")
        print("📤 [NetworkService] Streaming message: '\(message)'")
        
        let body: [String: Any] = [
            "content": message
        ]
        
        do {
            let data = try await post("/chat-sessions/\(sessionId)/messages/stream", body: body, requiresAuth: true)
            let response = try decoder.decode(StreamingChatResponse.self, from: data)
            print("✅ [NetworkService] Started streaming chat response")
            return response
        } catch {
            print("❌ [NetworkService] Error starting streaming chat: \(error)")
            throw error
        }
    }
    
    public func connectToStreamingResponse(sessionId: Int, requestId: String) -> AsyncStream<StreamingChunk> {
        print("🌐 [NetworkService] connectToStreamingResponse for session: \(sessionId), request: \(requestId)")
        
        return AsyncStream { continuation in
            Task {
                do {
                    let streamURL = "\(baseURL)/chat-sessions/\(sessionId)/stream/\(requestId)"
                    guard let url = URL(string: streamURL) else {
                        continuation.finish()
                        return
                    }
                    
                    var request = URLRequest(url: url)
                    request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
                    request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
                    request.setValue("no-cache", forHTTPHeaderField: "Cache-Control")
                    
                    let (data, response) = try await URLSession.shared.bytes(for: request)
                    
                    guard let httpResponse = response as? HTTPURLResponse,
                          httpResponse.statusCode == 200 else {
                        print("❌ [NetworkService] Streaming response failed")
                        continuation.finish()
                        return
                    }
                    
                    print("📡 [NetworkService] Connected to streaming response")
                    
                    for try await line in data.lines {
                        if line.hasPrefix("data: ") {
                            let jsonString = String(line.dropFirst(6))
                            if let data = jsonString.data(using: .utf8) {
                                do {
                                    let chunk = try decoder.decode(StreamingChunk.self, from: data)
                                    continuation.yield(chunk)
                                    
                                    if chunk.type == "complete" || chunk.type == "error" {
                                        print("✅ [NetworkService] Streaming completed")
                                        continuation.finish()
                                        return
                                    }
                                } catch {
                                    print("⚠️ [NetworkService] Error decoding streaming chunk: \(error)")
                                }
                            }
                        }
                    }
                    
                    continuation.finish()
                } catch {
                    print("❌ [NetworkService] Streaming error: \(error)")
                    continuation.finish()
                }
            }
        }
    }
    
    // MARK: - WebSocket Support for Real-time Status
    
    public func connectToStatusUpdates(sessionId: Int) -> AsyncStream<ChatStatusMessage> {
        print("🌐 [NetworkService] connectToStatusUpdates for session: \(sessionId)")
        
        return AsyncStream { continuation in
            Task {
                do {
                    let wsURL = baseURL.replacingOccurrences(of: "http://", with: "ws://")
                                     .replacingOccurrences(of: "https://", with: "wss://")
                    let fullURL = "\(wsURL)/chat-sessions/\(sessionId)/status"
                    
                    guard let url = URL(string: fullURL) else {
                        print("❌ [NetworkService] Invalid WebSocket URL")
                        continuation.finish()
                        return
                    }
                    
                    var request = URLRequest(url: url)
                    // Note: WebSocket auth would need special handling in production
                    
                    let webSocketTask = URLSession.shared.webSocketTask(with: request)
                    webSocketTask.resume()
                    
                    print("🔌 [NetworkService] WebSocket connected for status updates")
                    
                    while true {
                        do {
                            let message = try await webSocketTask.receive()
                            switch message {
                            case .string(let text):
                                if let data = text.data(using: .utf8) {
                                    do {
                                        let statusMessage = try decoder.decode(ChatStatusMessage.self, from: data)
                                        continuation.yield(statusMessage)
                                    } catch {
                                        print("⚠️ [NetworkService] Error decoding status message: \(error)")
                                    }
                                }
                            case .data:
                                break
                            @unknown default:
                                break
                            }
                        } catch {
                            print("❌ [NetworkService] WebSocket error: \(error)")
                            break
                        }
                    }
                    
                    webSocketTask.cancel()
                    continuation.finish()
                } catch {
                    print("❌ [NetworkService] WebSocket connection error: \(error)")
                    continuation.finish()
                }
            }
        }
    }
    


    // Legacy method - now deprecated, kept for compatibility
    public func sendChatMessage(_ message: String, history: [[String: String]] = []) async throws -> (response: String, title: String?) {
        print("⚠️ [NetworkService] Using legacy chat endpoint - consider migrating to session-based chat")
        
        let body: [String: Any] = [
            "message": message,
            "history": history
        ]

        do {
            // Use the simple /api/chat endpoint directly (bypassing baseURL with /api/v1)
            let fullURL = "\(apiEndpoint)/api/chat"
            print("🎯 [NetworkService] Direct URL: \(fullURL)")

            guard let url = URL(string: fullURL) else {
                print("❌ [NetworkService] Invalid URL: \(fullURL)")
                throw NetworkError.invalidURL
            }

            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            print("🔧 [NetworkService] HTTP Method: POST")

            // Set headers (no auth required for this endpoint)
            let requestHeaders = [
                "Content-Type": "application/json",
                "Accept": "application/json",
            ]
            for (key, value) in requestHeaders {
                request.setValue(value, forHTTPHeaderField: key)
            }
            print("📋 [NetworkService] Request headers: \(requestHeaders)")

            // Set request body
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
            print("📦 [NetworkService] Request body set: \(body)")

            print("📡 [NetworkService] Sending request...")
            let (data, response) = try await URLSession.shared.data(for: request)
            print("📨 [NetworkService] Response received")

            guard let httpResponse = response as? HTTPURLResponse else {
                print("❌ [NetworkService] Invalid response type")
                throw NetworkError.invalidResponse
            }
            print("📊 [NetworkService] HTTP Status Code: \(httpResponse.statusCode)")

            guard 200...299 ~= httpResponse.statusCode else {
                let errorString = String(data: data, encoding: .utf8) ?? "Unknown error"
                print("❌ [NetworkService] HTTP Error: \(httpResponse.statusCode) - \(errorString)")
                throw NetworkError.serverError("HTTP \(httpResponse.statusCode): \(errorString)")
            }

            print("📊 [NetworkService] Response data size: \(data.count) bytes")
            let jsonResponse = try JSONSerialization.jsonObject(with: data) as? [String: Any]
            print("📋 [NetworkService] Response JSON: \(jsonResponse ?? [:])")

            guard let response = jsonResponse?["response"] as? String else {
                print("❌ [NetworkService] Missing 'response' field in JSON")
                throw NetworkError.invalidResponse
            }

            let title = jsonResponse?["title"] as? String
            print("✅ [NetworkService] Chat response received successfully")
            print("📝 [NetworkService] Response: '\(response.prefix(100))...'")
            if let title = title {
                print("🏷️ [NetworkService] Title: '\(title)'")
            }

            return (response: response, title: title)
        } catch {
            print("❌ [NetworkService] Error in sendChatMessage: \(error)")
            throw error
        }
    }

    // MARK: - Patients

    public func getPatients() async throws -> Data {
        return try await get("/patients")
    }

    public func createPatient(_ patient: [String: Any]) async throws -> Data {
        return try await post("/patients", body: patient)
    }

    public func updatePatient(id: String, patient: [String: Any]) async throws -> Data {
        return try await put("/patients/\(id)", body: patient)
    }

    public func deletePatient(id: String) async throws {
        _ = try await delete("/patients/\(id)")
    }

    // MARK: - Health Metrics

    public func getHealthMetrics(patientId: String) async throws -> Data {
        return try await get("/patients/\(patientId)/metrics")
    }

    public func addHealthMetric(patientId: String, metric: [String: Any]) async throws -> Data {
        return try await post("/patients/\(patientId)/metrics", body: metric)
    }

    // MARK: - Lab Reports

    public func getLabReports(patientId: String) async throws -> Data {
        return try await get("/patients/\(patientId)/reports")
    }

    public func addLabReport(patientId: String, report: [String: Any]) async throws -> Data {
        return try await post("/patients/\(patientId)/reports", body: report)
    }

    // MARK: - Chat Session Management
    
    public func updateChatSession(sessionId: Int, title: String) async throws -> BackendChatSession {
        print("📝 [NetworkService] Updating chat session \(sessionId) with title: \(title)")
        
        let body: [String: Any] = [
            "title": title
        ]
        
        do {
            let data = try await put("/chat-sessions/\(sessionId)", body: body, requiresAuth: true)
            let chatSession = try decoder.decode(BackendChatSession.self, from: data)
            print("✅ [NetworkService] Updated chat session: \(chatSession.id) - \(chatSession.title)")
            return chatSession
        } catch {
            print("❌ [NetworkService] Error updating chat session: \(error)")
            throw error
        }
    }
    
    public func deleteChatSession(sessionId: Int) async throws {
        print("🗑️ [NetworkService] Deleting chat session \(sessionId)")
        
        do {
            _ = try await delete("/chat-sessions/\(sessionId)", requiresAuth: true)
            print("✅ [NetworkService] Deleted chat session: \(sessionId)")
        } catch {
            print("❌ [NetworkService] Error deleting chat session: \(error)")
            throw error
        }
    }

    // MARK: - Consultation Verification
    
    func checkConsultationVerificationStatus(requestId: Int) async throws -> ConsultationRequestResponse {
        let url = "\(baseURL)/doctors/consultation-requests/\(requestId)/status"
        
        var request = URLRequest(url: URL(string: url)!)
        request.httpMethod = "GET"
        
        for (key, value) in headers() {
            request.setValue(value, forHTTPHeaderField: key)
        }
        
        print("🔍 [NetworkService] Checking verification status for consultation request \(requestId)")
        
        let (data, response) = try await urlSession.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw NetworkError.invalidResponse
        }
        
        guard 200...299 ~= httpResponse.statusCode else {
            let errorString = String(data: data, encoding: .utf8) ?? "Unknown error"
            print("❌ [NetworkService] Verification status check failed with status code: \(httpResponse.statusCode) - \(errorString)")
            throw NetworkError.serverError("HTTP \(httpResponse.statusCode): \(errorString)")
        }
        
        let consultationRequest = try decoder.decode(ConsultationRequestResponse.self, from: data)
        print("✅ [NetworkService] Retrieved verification status: \(consultationRequest.status)")
        
        return consultationRequest
    }
}

// MARK: - Authentication Extension

public extension NetworkService {
    private func ensureAuthentication() async throws {
        // Check if we have a valid token that hasn't expired
        if !authToken.isEmpty && !isTokenExpired() {
            print("🔐 [NetworkService] Using existing valid auth token for \(userMode)")
            print("🎫 [NetworkService] Token length: \(authToken.count) characters")
            return
        }

        if !authToken.isEmpty {
            print("⚠️ [NetworkService] Auth token expired for \(userMode), attempting refresh...")
            if await tryRefreshAccessTokenIfNeeded() {
                print("✅ [NetworkService] Token refreshed for \(userMode)")
                return
            }
            clearAuthToken()
        }

        print("🔐 [NetworkService] No valid auth token found for \(userMode), attempting authentication...")
        print("👤 [NetworkService] Will try to authenticate as: \(currentCredentials.email)")

        // For ZivoDoc (doctor app), require manual login on cold start. Do not auto-register/login.
        if userMode == .doctor {
            print("🛑 [NetworkService] Manual login required for doctor mode - skipping auto login.")
            throw NetworkError.authenticationFailed
        }

        // Try to login with role-specific credentials
        do {
            let token = try await login(email: currentCredentials.email, password: currentCredentials.password)
            print("✅ [NetworkService] Successfully authenticated \(userMode) with token length: \(token.count)")
            return
        } catch let error as NetworkError {
            print("⚠️ [NetworkService] Login failed with error: \(error)")

            switch error {
            case let .serverError(message) where message.contains("Incorrect email or password"):
                // User doesn't exist, try to register
                print("🔄 [NetworkService] \(userMode.rawValue.capitalized) user doesn't exist, attempting registration...")
                try await register(email: currentCredentials.email, password: currentCredentials.password, fullName: currentCredentials.name)
                print("✅ [NetworkService] \(userMode.rawValue.capitalized) user registered successfully")

                // Now login with the newly registered user
                let token = try await login(email: currentCredentials.email, password: currentCredentials.password)
                print("✅ [NetworkService] Successfully logged in new \(userMode) user with token length: \(token.count)")
                return
            default:
                print("❌ [NetworkService] Authentication failed with error: \(error)")
                throw error
            }
        } catch {
            print("❌ [NetworkService] Unexpected authentication error: \(error)")
            throw NetworkError.authenticationFailed
        }
    }

    func login(email: String, password: String) async throws -> String {
        print("🔐 [NetworkService] Attempting login for \(userMode): \(email)")

        let loginData = "username=\(email)&password=\(password)"
        let body = loginData.data(using: .utf8)!

        do {
            let data = try await post("/auth/login", body: body, contentType: "application/x-www-form-urlencoded", requiresAuth: false)
            print("✅ [NetworkService] Login successful for \(userMode)")

            let tokenResponse = try decoder.decode(TokenResponse.self, from: data)
            let token = tokenResponse.accessToken

            print("🎫 [NetworkService] Received auth token for \(userMode) (length: \(token.count))")
            print("🔑 [NetworkService] Token preview: \(token.prefix(20))...")

            // Store the token and its expiration info
            authToken = token
            saveTokenInfo(tokenResponse)
            if userMode == .doctor, let refresh = tokenResponse.refreshToken {
                doctorRefreshToken = refresh
            }
            print("💾 [NetworkService] Stored token and expiration info for \(userMode)")

            return token
        } catch {
            print("❌ [NetworkService] Login failed for \(userMode): \(error)")
            throw NetworkError.authenticationFailed
        }
    }

    private func register(email: String, password: String, fullName: String) async throws -> String {
        print("📝 [NetworkService] Attempting registration for user: \(email)")

        let body: [String: Any] = [
            "email": email,
            "password": password,
            "full_name": fullName,
            "is_active": true,
        ]

        do {
            let data = try await post("/auth/register", body: body, requiresAuth: false)
            print("✅ [NetworkService] Registration successful")

            let userResponse = try decoder.decode(UserResponse.self, from: data)
            print("👤 [NetworkService] Created user with ID: \(userResponse.id)")

            // Now login to get the token
            return try await login(email: email, password: password)
        } catch {
            print("❌ [NetworkService] Registration failed: \(error)")
            throw error
        }
    }
}

// MARK: - Doctor Consultation Extension

extension NetworkService {
    struct DoctorRegistrationInput {
        let email: String
        let password: String
        let fullName: String
        let dateOfBirth: Date?
        let contactNumber: String?
        let licenseNumber: String
        let specialization: String
        let yearsExperience: Int
        let bio: String?
        let isAvailable: Bool
    }

    func registerDoctor(_ input: DoctorRegistrationInput) async throws {
        print("📝 [NetworkService] Registering doctor: \(input.email)")
        let isoDate: String? = input.dateOfBirth.map { date in
            let f = DateFormatter()
            f.dateFormat = "yyyy-MM-dd"
            f.timeZone = .current
            return f.string(from: date)
        }
        var body: [String: Any] = [
            "email": input.email,
            "password": input.password,
            "full_name": input.fullName,
            "license_number": input.licenseNumber,
            "specialization": input.specialization,
            "years_experience": input.yearsExperience,
            "is_available": input.isAvailable
        ]
        if let dob = isoDate { body["date_of_birth"] = dob }
        if let contact = input.contactNumber { body["contact_number"] = contact }
        if let bio = input.bio { body["bio"] = bio }

        _ = try await post("/doctors/register", body: body, requiresAuth: false)
        // Intentionally DO NOT auto-login after registration. User must login explicitly.
    }
    func getAvailableDoctors() async throws -> [Doctor] {
        print("🏥 [NetworkService] Getting all available doctors")

        do {
            let data = try await get("/doctors/available", requiresAuth: true)
            print("✅ [NetworkService] Available doctors fetched successfully")

            let doctors = try decoder.decode([Doctor].self, from: data)
            print("👨‍⚕️ [NetworkService] Found \(doctors.count) available doctors")

            return doctors
        } catch {
            print("❌ [NetworkService] Error getting available doctors: \(error)")
            throw error
        }
    }
    
    func findDoctorsByContext(_ context: String) async throws -> [Doctor] {
        print("🔍 [NetworkService] Finding doctors by context")
        print("📝 [NetworkService] Context: \(context.prefix(100))...")

        let body: [String: Any] = [
            "context": context,
        ]

        do {
            let data = try await post("/doctors/find-by-context", body: body, requiresAuth: true)
            print("✅ [NetworkService] Doctors found successfully")

            let doctors = try decoder.decode([Doctor].self, from: data)
            print("👨‍⚕️ [NetworkService] Found \(doctors.count) matching doctors")

            return doctors
        } catch {
            print("❌ [NetworkService] Error finding doctors: \(error)")
            throw error
        }
    }

    func createConsultationRequest(
        doctorId: Int,
        context: String,
        userQuestion: String,
        chatSessionId: Int? = nil
    ) async throws -> ConsultationRequestResponse {
        print("📝 [NetworkService] Creating consultation request")
        print("👨‍⚕️ [NetworkService] Doctor ID: \(doctorId)")
        print("❓ [NetworkService] Question: \(userQuestion.prefix(100))...")
        if let sessionId = chatSessionId {
            print("💬 [NetworkService] Chat Session ID: \(sessionId)")
        }

        var body: [String: Any] = [
            "doctor_id": doctorId,
            "context": context,
            "user_question": userQuestion,
            "urgency_level": "normal",
        ]
        
        if let sessionId = chatSessionId {
            body["chat_session_id"] = sessionId
        }

        do {
            let data = try await post("/doctors/consultation-requests", body: body, requiresAuth: true)
            print("✅ [NetworkService] Consultation request created successfully")

            let consultationRequest = try decoder.decode(ConsultationRequestResponse.self, from: data)
            print("📋 [NetworkService] Request ID: \(consultationRequest.id)")

            return consultationRequest
        } catch {
            print("💥 [NetworkService] Error creating consultation request: \(error)")
            throw error
        }
    }

    func getUserConsultationRequests() async throws -> [ConsultationRequestWithDoctor] {
        print("📋 [NetworkService] Getting user consultation requests")

        do {
            let data = try await get("/doctors/consultation-requests", requiresAuth: true)
            print("✅ [NetworkService] Consultation requests fetched successfully")

            let requests = try decoder.decode([ConsultationRequestWithDoctor].self, from: data)
            print("📊 [NetworkService] Found \(requests.count) consultation requests")

            return requests
        } catch {
            print("💥 [NetworkService] Error fetching consultation requests: \(error)")
            throw error
        }
    }

    func getDoctorConsultationRequests() async throws -> [ConsultationRequestResponse] {
        print("🏥 [NetworkService] Getting consultation requests for doctor")

        do {
            // Use the doctor-specific endpoint that returns ConsultationRequestResponse objects
            let data = try await get("/doctors/my-consultation-requests", requiresAuth: true)
            print("✅ [NetworkService] Doctor consultation requests fetched successfully")

            let requests = try decoder.decode([ConsultationRequestResponse].self, from: data)
            print("📋 [NetworkService] Found \(requests.count) consultation requests")

            return requests
        } catch {
            print("❌ [NetworkService] Error fetching doctor consultation requests: \(error)")
            throw error
        }
    }

    func getMyConsultationRequests() async throws -> [ConsultationRequestWithDoctor] {
        print("🏥 [NetworkService] Getting consultation requests with doctor details")

        // Ensure we have valid authentication
        try await ensureAuthentication()

        do {
            // Use the endpoint that returns ConsultationRequestWithDoctor objects
            let data = try await get("/doctors/consultation-requests", requiresAuth: true)
            print("✅ [NetworkService] Consultation requests fetched successfully")

            let requests = try decoder.decode([ConsultationRequestWithDoctor].self, from: data)
            print("📋 [NetworkService] Found \(requests.count) consultation requests with doctor details")

            return requests
        } catch {
            print("❌ [NetworkService] Error fetching consultation requests: \(error)")
            throw error
        }
    }

    func updateConsultationRequestStatus(
        requestId: Int,
        status: String,
        notes: String? = nil
    ) async throws -> ConsultationRequestResponse {
        print("🔄 [NetworkService] Updating consultation request \(requestId) status to \(status)")

        // Ensure we have valid authentication
        try await ensureAuthentication()

        let body: [String: Any] = [
            "status": status,
            "doctor_notes": notes ?? "",
        ]

        do {
            let data = try await request(
                path: "/doctors/consultation-requests/\(requestId)/status",
                method: "PATCH",
                body: body,
                requiresAuth: true
            )
            print("✅ [NetworkService] Consultation request status updated successfully")

            let updatedRequest = try decoder.decode(ConsultationRequestResponse.self, from: data)
            print("📋 [NetworkService] Updated request ID: \(updatedRequest.id)")

            return updatedRequest
        } catch {
            print("💥 [NetworkService] Error updating consultation request status: \(error)")
            throw error
        }
    }

    func generateConsultationSummary(
        requestId: Int
    ) async throws -> ConsultationRequestResponse {
        print("🤖 [NetworkService] Generating AI summary for consultation request \(requestId)")

        // Ensure we have valid authentication
        try await ensureAuthentication()

        let body: [String: Any] = [
            "request_id": requestId
        ]

        do {
            let data = try await post("/doctors/generate-summary", body: body, requiresAuth: true)
            print("✅ [NetworkService] AI summary generated successfully")

            let updatedRequest = try decoder.decode(ConsultationRequestResponse.self, from: data)
            print("📋 [NetworkService] Updated request with summary: \(updatedRequest.id)")

            return updatedRequest
        } catch {
            print("💥 [NetworkService] Error generating consultation summary: \(error)")
            throw error
        }
    }
    
    func getConsultationRequestById(
        _ requestId: Int
    ) async throws -> ConsultationRequestResponse {
        print("🔍 [NetworkService] Getting consultation request by ID: \(requestId)")
        
        // Ensure we have valid authentication
        try await ensureAuthentication()
        
        do {
            let data = try await get("/doctors/consultation-requests/\(requestId)/status", requiresAuth: true)
            print("✅ [NetworkService] Consultation request retrieved successfully")
            
            let request = try decoder.decode(ConsultationRequestResponse.self, from: data)
            print("📋 [NetworkService] Request ID: \(request.id), Status: \(request.status)")
            
            return request
        } catch {
            print("💥 [NetworkService] Error getting consultation request: \(error)")
            throw error
        }
    }
}

// MARK: - Prescription Data Structure
struct PrescriptionData {
    let medicationName: String
    let dosage: String?
    let frequency: String?
    let instructions: String?
    let prescribedBy: String
}

// MARK: - Prescription Extension
extension NetworkService {
    
    // Save prescriptions for a specific consultation request
    func savePrescriptionsForConsultation(
        requestId: Int,
        prescriptions: [Prescription]
    ) async throws {
        print("💊 [NetworkService] Saving \(prescriptions.count) prescriptions for consultation \(requestId)")
        
        let body = [
            "prescriptions": prescriptions.map { prescription in
                [
                    "medication_name": prescription.medicationName,
                    "dosage": prescription.dosage,
                    "frequency": prescription.frequency,
                    "instructions": prescription.instructions,
                    "prescribed_by": prescription.prescribedBy,
                    "prescribed_at": ISO8601DateFormatter().string(from: prescription.prescribedAt)
                ]
            }
        ]
        
        do {
            _ = try await post("/doctors/consultation-requests/\(requestId)/prescriptions", body: body, requiresAuth: true)
            print("✅ [NetworkService] Prescriptions saved successfully")
        } catch {
            print("❌ [NetworkService] Error saving prescriptions: \(error)")
            throw error
        }
    }
    
    // Get all prescriptions for the current patient
    func getPatientPrescriptions() async throws -> [PrescriptionWithSession] {
        print("💊 [NetworkService] Getting patient prescriptions")
        
        do {
            let data = try await get("/chat-sessions/prescriptions/patient", requiresAuth: true)
            print("✅ [NetworkService] Patient prescriptions fetched successfully")
            
            let prescriptions = try decoder.decode([PrescriptionWithSession].self, from: data)
            print("📊 [NetworkService] Found \(prescriptions.count) prescriptions")
            
            return prescriptions
        } catch {
            print("❌ [NetworkService] Error fetching patient prescriptions: \(error)")
            throw error
        }
    }
    
        // Add a prescription to a session
    func addPrescriptionToSession(sessionId: Int, prescription: PrescriptionData) async throws {
        print("💊 [NetworkService] Adding prescription to session \(sessionId)")
        
        let body: [String: Any] = [
            "medication_name": prescription.medicationName,
            "dosage": prescription.dosage ?? "",
            "frequency": prescription.frequency ?? "", 
            "instructions": prescription.instructions ?? "",
            "prescribed_by": prescription.prescribedBy
        ]
        
        do {
            _ = try await post("/chat-sessions/\(sessionId)/prescriptions", body: body, requiresAuth: true)
            print("✅ [NetworkService] Prescription added to session successfully")
        } catch {
            print("❌ [NetworkService] Error adding prescription to session: \(error)")
            throw error
        }
    }

    // Get prescriptions for a specific consultation/session
    func getPrescriptionsForSession(sessionId: Int) async throws -> [Prescription] {
        print("💊 [NetworkService] Getting prescriptions for session \(sessionId)")

        do {
            let data = try await get("/chat-sessions/\(sessionId)/prescriptions", requiresAuth: true)
            print("✅ [NetworkService] Session prescriptions fetched successfully")

            let prescriptions = try decoder.decode([Prescription].self, from: data)
            print("📊 [NetworkService] Found \(prescriptions.count) prescriptions for session")

            return prescriptions
        } catch {
            print("❌ [NetworkService] Error fetching session prescriptions: \(error)")
            throw error
        }
    }
}

// MARK: - Appointment Extension
extension NetworkService {
    
    // Create a new appointment
    func createAppointment(_ appointmentCreate: AppointmentCreate) async throws -> Appointment {
        print("📅 [NetworkService] Creating new appointment: \(appointmentCreate.title)")
        
        let body: [String: Any] = [
            "doctor_id": appointmentCreate.doctorId,
            "consultation_request_id": appointmentCreate.consultationRequestId as Any,
            "title": appointmentCreate.title,
            "description": appointmentCreate.description as Any,
            "appointment_date": ISO8601DateFormatter().string(from: appointmentCreate.appointmentDate),
            "duration_minutes": appointmentCreate.durationMinutes,
            "status": appointmentCreate.status,
            "appointment_type": appointmentCreate.appointmentType,
            "patient_notes": appointmentCreate.patientNotes as Any
        ]
        
        do {
            let data = try await post("/appointments/", body: body, requiresAuth: true)
            let appointment = try decoder.decode(Appointment.self, from: data)
            print("✅ [NetworkService] Appointment created successfully: \(appointment.id)")
            return appointment
        } catch {
            print("❌ [NetworkService] Error creating appointment: \(error)")
            throw error
        }
    }
    
    // Get all appointments for current user
    func getAppointments() async throws -> [AppointmentWithDetails] {
        print("📅 [NetworkService] Getting appointments")
        print("🔐 [NetworkService] Current user mode: \(userMode)")
        print("🎫 [NetworkService] Current auth token: \(authToken.isEmpty ? "EMPTY" : "EXISTS (\(authToken.count) chars)")")
        print("🌐 [NetworkService] API endpoint: \(apiEndpoint)")
        
        do {
            let data = try await get("/appointments/", requiresAuth: true)
            let appointments = try decoder.decode([AppointmentWithDetails].self, from: data)
            print("✅ [NetworkService] Found \(appointments.count) appointments for \(userMode)")
            
            // Log each appointment for debugging
            for (index, appointment) in appointments.enumerated() {
                print("📋 [NetworkService] Appointment \(index + 1): \(appointment.title) - Patient: \(appointment.patientName), Doctor: \(appointment.doctorName)")
            }
            
            return appointments
        } catch {
            print("❌ [NetworkService] Error fetching appointments: \(error)")
            throw error
        }
    }
    
    // Get specific appointment by ID
    func getAppointment(id: Int) async throws -> AppointmentWithDetails {
        print("📅 [NetworkService] Getting appointment \(id)")
        
        do {
            let data = try await get("/appointments/\(id)", requiresAuth: true)
            let appointment = try decoder.decode(AppointmentWithDetails.self, from: data)
            print("✅ [NetworkService] Appointment retrieved: \(appointment.title)")
            return appointment
        } catch {
            print("❌ [NetworkService] Error fetching appointment: \(error)")
            throw error
        }
    }
    
    // Update an appointment
    func updateAppointment(id: Int, update: AppointmentUpdate) async throws -> Appointment {
        print("📅 [NetworkService] Updating appointment \(id)")
        
        var body: [String: Any] = [:]
        if let title = update.title { body["title"] = title }
        if let description = update.description { body["description"] = description }
        if let appointmentDate = update.appointmentDate {
            body["appointment_date"] = ISO8601DateFormatter().string(from: appointmentDate)
        }
        if let durationMinutes = update.durationMinutes { body["duration_minutes"] = durationMinutes }
        if let status = update.status { body["status"] = status }
        if let appointmentType = update.appointmentType { body["appointment_type"] = appointmentType }
        if let patientNotes = update.patientNotes { body["patient_notes"] = patientNotes }
        if let doctorNotes = update.doctorNotes { body["doctor_notes"] = doctorNotes }
        
        do {
            let data = try await put("/appointments/\(id)", body: body, requiresAuth: true)
            let appointment = try decoder.decode(Appointment.self, from: data)
            print("✅ [NetworkService] Appointment updated successfully")
            return appointment
        } catch {
            print("❌ [NetworkService] Error updating appointment: \(error)")
            throw error
        }
    }
    
    // Delete an appointment
    func deleteAppointment(id: Int) async throws {
        print("📅 [NetworkService] Deleting appointment \(id)")
        
        do {
            _ = try await delete("/appointments/\(id)", requiresAuth: true)
            print("✅ [NetworkService] Appointment deleted successfully")
        } catch {
            print("❌ [NetworkService] Error deleting appointment: \(error)")
            throw error
        }
    }
}

// MARK: - Clinical Report Extension
extension NetworkService {
    
    // Get clinical report for a consultation request (for doctors)
    func getClinicalReport(for consultationRequestId: Int) async throws -> ClinicalReport {
        print("📋 [NetworkService] Getting clinical report for consultation \(consultationRequestId)")
        
        try await ensureAuthentication()
        
        do {
            let data = try await get("/doctors/consultation-requests/\(consultationRequestId)/clinical-report", requiresAuth: true)
            let clinicalReport = try decoder.decode(ClinicalReport.self, from: data)
            print("✅ [NetworkService] Clinical report retrieved successfully")
            return clinicalReport
        } catch {
            print("❌ [NetworkService] Error fetching clinical report: \(error)")
            throw error
        }
    }
    
    // Get consultation request with clinical report (for doctors)
    func getConsultationWithClinicalReport(consultationRequestId: Int) async throws -> ConsultationRequestWithClinicalReport {
        print("📋 [NetworkService] Getting consultation with clinical report for request \(consultationRequestId)")
        
        try await ensureAuthentication()
        
        do {
            let data = try await get("/doctors/consultation-requests/\(consultationRequestId)/with-clinical-report", requiresAuth: true)
            let consultation = try decoder.decode(ConsultationRequestWithClinicalReport.self, from: data)
            print("✅ [NetworkService] Consultation with clinical report retrieved successfully")
            return consultation
        } catch {
            print("❌ [NetworkService] Error fetching consultation with clinical report: \(error)")
            throw error
        }
    }
}

// MARK: - HTTP Methods Extension

extension NetworkService {
    private func get(_ path: String, requiresAuth: Bool = true) async throws -> Data {
        return try await request(path: path, method: "GET", body: nil, requiresAuth: requiresAuth)
    }

    private func post(_ path: String, body: [String: Any], requiresAuth: Bool = true) async throws -> Data {
        return try await request(path: path, method: "POST", body: body, requiresAuth: requiresAuth)
    }

    func post(_ path: String, body: Data, contentType: String, requiresAuth: Bool = true) async throws -> Data {
        return try await request(path: path, method: "POST", bodyData: body, contentType: contentType, requiresAuth: requiresAuth)
    }

    private func put(_ path: String, body: [String: Any], requiresAuth: Bool = true) async throws -> Data {
        return try await request(path: path, method: "PUT", body: body, requiresAuth: requiresAuth)
    }

    private func delete(_ path: String, requiresAuth: Bool = true) async throws -> Data {
        return try await request(path: path, method: "DELETE", body: nil, requiresAuth: requiresAuth)
    }

    func request(
        path: String,
        method: String,
        body: [String: Any]? = nil,
        bodyData: Data? = nil,
        contentType: String = "application/json",
        requiresAuth: Bool = true,
        isRetry: Bool = false
    ) async throws -> Data {
        // Ensure authentication before making the request
        if requiresAuth {
            try await ensureAuthentication()
        }
        
        let fullURL = baseURL + path
        print("🚀 [NetworkService] Making \(method) request to: \(fullURL)")
        print("🔧 [NetworkService] HTTP Method: \(method)")

        guard let url = URL(string: fullURL) else {
            print("❌ [NetworkService] Invalid URL: \(fullURL)")
            throw NetworkError.invalidURL
        }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = method

        // Set headers
        var headers: [String: String] = [
            "Accept": "application/json",
            "Content-Type": contentType,
        ]

        if requiresAuth && !authToken.isEmpty {
            headers["Authorization"] = "Bearer \(authToken)"
        }

        for (key, value) in headers {
            urlRequest.setValue(value, forHTTPHeaderField: key)
        }

        print("📋 [NetworkService] Request headers: \(headers)")

        // Set body
        if let bodyData = bodyData {
            urlRequest.httpBody = bodyData
            print("📦 [NetworkService] Request body set with \(bodyData.count) bytes")
        } else if let body = body {
            do {
                let jsonData = try JSONSerialization.data(withJSONObject: body)
                urlRequest.httpBody = jsonData
                print("📦 [NetworkService] Request body set: \(body)")
            } catch {
                print("❌ [NetworkService] Failed to serialize JSON body: \(error)")
                throw NetworkError.invalidRequest
            }
        }

        print("📡 [NetworkService] Sending request...")

        do {
            let (data, response) = try await urlSession.data(for: urlRequest)
            print("📨 [NetworkService] Response received")

            guard let httpResponse = response as? HTTPURLResponse else {
                print("❌ [NetworkService] Invalid HTTP response type")
                throw NetworkError.invalidResponse
            }

            print("📊 [NetworkService] HTTP Status Code: \(httpResponse.statusCode)")
            print("📏 [NetworkService] Response data size: \(data.count) bytes")

            if let responseString = String(data: data, encoding: .utf8) {
                print("📄 [NetworkService] Response body: \(responseString)")
            }

            // Handle 401 errors with automatic token refresh and retry
            if httpResponse.statusCode == 401 && requiresAuth && !isRetry && authRetryCount < maxAuthRetries {
                print("🔄 [NetworkService] Got 401 Unauthorized (attempt \(authRetryCount + 1)/\(maxAuthRetries))")
                authRetryCount += 1
                
                // Clear the token and force re-authentication
                clearAuthToken()
                
                // Wait a moment before retrying to avoid rapid successive attempts
                try await Task.sleep(nanoseconds: 1_000_000_000) // 1 second
                
                // Retry the request with fresh authentication
                return try await request(
                    path: path,
                    method: method,
                    body: body,
                    bodyData: bodyData,
                    contentType: contentType,
                    requiresAuth: requiresAuth,
                    isRetry: true
                )
            }
            
            // Handle network errors with retry logic
            if (httpResponse.statusCode >= 500 || 
                httpResponse.statusCode == 408 ||  // Request timeout
                httpResponse.statusCode == 429) && // Too many requests
                !isRetry && authRetryCount < maxAuthRetries {
                
                print("🔄 [NetworkService] Server error \(httpResponse.statusCode), retrying...")
                authRetryCount += 1
                
                // Exponential backoff: wait longer for each retry
                let delay = Double(authRetryCount) * 2.0
                try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                
                return try await request(
                    path: path,
                    method: method,
                    body: body,
                    bodyData: bodyData,
                    contentType: contentType,
                    requiresAuth: requiresAuth,
                    isRetry: true
                )
            }

            guard httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 else {
                print("❌ [NetworkService] Error status code: \(httpResponse.statusCode)")
                if let error = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let message = error["detail"] as? String
                {
                    print("📄 [NetworkService] Error message from server: \(message)")
                    throw NetworkError.serverError("HTTP \(httpResponse.statusCode): \(message)")
                }
                print("❓ [NetworkService] Unknown error occurred")
                throw NetworkError.serverError("Unknown error occurred")
            }

            print("✅ [NetworkService] Request successful")
            
            // Reset auth retry count on successful request
            if !isRetry {
                authRetryCount = 0
            }
            
            return data
        } catch {
            print("💥 [NetworkService] Network request failed: \(error)")
            
            // Reset auth retry count on successful request or final failure
            if !isRetry {
                authRetryCount = 0
            }
            
            // Provide more specific error handling
            if let urlError = error as? URLError {
                switch urlError.code {
                case .notConnectedToInternet, .networkConnectionLost:
                    isNetworkAvailable = false
                    isReconnecting = true
                    startReconnectionTimer()
                    throw NetworkError.networkError(NSError(
                        domain: "NetworkError",
                        code: -1,
                        userInfo: [NSLocalizedDescriptionKey: "No internet connection. Please check your network settings."]
                    ))
                case .timedOut:
                    throw NetworkError.networkError(NSError(
                        domain: "NetworkError", 
                        code: -2,
                        userInfo: [NSLocalizedDescriptionKey: "Request timed out. Please try again."]
                    ))
                case .cannotFindHost, .cannotConnectToHost:
                    throw NetworkError.networkError(NSError(
                        domain: "NetworkError",
                        code: -3, 
                        userInfo: [NSLocalizedDescriptionKey: "Cannot connect to server. Please try again later."]
                    ))
                default:
                    throw NetworkError.networkError(error)
                }
            }
            
            throw NetworkError.networkError(error)
        }
    }
}

// MARK: - Response Types

struct TokenResponse: Codable {
    let accessToken: String
    let tokenType: String
    let userType: String
    let expiresIn: Int
    let refreshToken: String?

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case tokenType = "token_type"
        case userType = "user_type"
        case expiresIn = "expires_in"
        case refreshToken = "refresh_token"
    }
}

struct UserResponse: Codable {
    let id: Int
    let email: String
    let fullName: String
    let isActive: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case email
        case fullName = "full_name"
        case isActive = "is_active"
    }
}
