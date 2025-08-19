import Foundation

public enum MessageRole: String, Codable, Sendable {
    case user
    case assistant
    case status
}

public struct ChatMessage: Identifiable, Codable, Sendable {
    public let id: UUID
    public let content: String
    public let timestamp: Date
    public let role: MessageRole
    // File attachment support
    public let filePath: String?
    public let fileType: String?
    public let fileName: String?
    // Visualization support
    public let visualizations: [Visualization]?

    public init(role: MessageRole, content: String, timestamp: Date = Date(), filePath: String? = nil, fileType: String? = nil, fileName: String? = nil, visualizations: [Visualization]? = nil) {
        id = UUID()
        self.role = role
        self.content = content
        self.timestamp = timestamp
        self.filePath = filePath
        self.fileType = fileType
        self.fileName = fileName
        self.visualizations = visualizations
    }
    
    // Computed property to check if message has file attachment
    public var hasAttachment: Bool {
        return filePath != nil || fileName != nil
    }
    
    // Computed property to check if message has visualizations
    public var hasVisualizations: Bool {
        return visualizations?.isEmpty == false
    }
}

// MARK: - Visualization Support

public struct Visualization: Codable, Sendable {
    public let id: String
    public let type: String  // "chart", "plot", "image"
    public let title: String
    public let description: String?
    public let relativeUrl: String
    public let metadata: [String: AnyCodable]?
    
    enum CodingKeys: String, CodingKey {
        case id, type, title, description, metadata
        case relativeUrl = "relative_url"
    }
    
    public init(id: String, type: String, title: String, description: String? = nil, relativeUrl: String, metadata: [String: AnyCodable]? = nil) {
        self.id = id
        self.type = type
        self.title = title
        self.description = description
        self.relativeUrl = relativeUrl
        self.metadata = metadata
    }
}

// Helper for Any type in dictionaries
public struct AnyCodable: Codable {
    public let value: Any
    
    public init<T>(_ value: T?) {
        self.value = value ?? ()
    }
    
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        
        if let intValue = try? container.decode(Int.self) {
            value = intValue
        } else if let doubleValue = try? container.decode(Double.self) {
            value = doubleValue
        } else if let stringValue = try? container.decode(String.self) {
            value = stringValue
        } else if let boolValue = try? container.decode(Bool.self) {
            value = boolValue
        } else {
            value = ()
        }
    }
    
    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        
        if let intValue = value as? Int {
            try container.encode(intValue)
        } else if let doubleValue = value as? Double {
            try container.encode(doubleValue)
        } else if let stringValue = value as? String {
            try container.encode(stringValue)
        } else if let boolValue = value as? Bool {
            try container.encode(boolValue)
        }
    }
}

// MARK: - Interactive Components for Enhanced Chat

public struct QuickReply: Codable, Sendable {
    public let text: String
    public let value: String
    
    public init(text: String, value: String) {
        self.text = text
        self.value = value
    }
}

public struct InteractiveComponent: Codable, Sendable {
    public let type: String
    public let data: [String: Any]
    
    public init(type: String, data: [String: Any]) {
        self.type = type
        self.data = data
    }
    
    enum CodingKeys: String, CodingKey {
        case type, data
    }
    
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        type = try container.decode(String.self, forKey: .type)
        
        // Handle the data dictionary with Any values
        let dataContainer = try container.nestedContainer(keyedBy: DynamicCodingKeys.self, forKey: .data)
        var decodedData: [String: Any] = [:]
        
        for key in dataContainer.allKeys {
            if let stringValue = try? dataContainer.decode(String.self, forKey: key) {
                decodedData[key.stringValue] = stringValue
            } else if let intValue = try? dataContainer.decode(Int.self, forKey: key) {
                decodedData[key.stringValue] = intValue
            } else if let boolValue = try? dataContainer.decode(Bool.self, forKey: key) {
                decodedData[key.stringValue] = boolValue
            } else if let stringArrayValue = try? dataContainer.decode([String].self, forKey: key) {
                decodedData[key.stringValue] = stringArrayValue
            } else if let intArrayValue = try? dataContainer.decode([Int].self, forKey: key) {
                decodedData[key.stringValue] = intArrayValue
            } else if let doubleValue = try? dataContainer.decode(Double.self, forKey: key) {
                decodedData[key.stringValue] = doubleValue
            } else if let doubleArrayValue = try? dataContainer.decode([Double].self, forKey: key) {
                decodedData[key.stringValue] = doubleArrayValue
            }
        }
        
        data = decodedData
    }
    
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(type, forKey: .type)
        // Note: Encoding [String: Any] requires custom handling
        // For now, we'll use a simplified approach
    }
}

public struct EnhancedChatMessage: Identifiable, Codable, Sendable {
    public let id: UUID
    public let content: String
    public let timestamp: Date
    public let role: MessageRole
    public let filePath: String?
    public let fileType: String?
    public let fileName: String?
    public let quickReplies: [QuickReply]?
    public let interactiveComponents: [InteractiveComponent]?
    public let visualizations: [Visualization]?
    
    public init(
        role: MessageRole,
        content: String,
        timestamp: Date = Date(),
        filePath: String? = nil,
        fileType: String? = nil,
        fileName: String? = nil,
        quickReplies: [QuickReply]? = nil,
        interactiveComponents: [InteractiveComponent]? = nil,
        visualizations: [Visualization]? = nil
    ) {
        id = UUID()
        self.role = role
        self.content = content
        self.timestamp = timestamp
        self.filePath = filePath
        self.fileType = fileType
        self.fileName = fileName
        self.quickReplies = quickReplies
        self.interactiveComponents = interactiveComponents
        self.visualizations = visualizations
    }
    
    // Convert from regular ChatMessage
    public init(from chatMessage: ChatMessage) {
        id = chatMessage.id
        content = chatMessage.content
        timestamp = chatMessage.timestamp
        role = chatMessage.role
        filePath = chatMessage.filePath
        fileType = chatMessage.fileType
        fileName = chatMessage.fileName
        quickReplies = nil
        interactiveComponents = nil
        visualizations = chatMessage.visualizations
    }
    
    public var hasAttachment: Bool {
        return filePath != nil || fileName != nil
    }
    
    public var hasInteractiveElements: Bool {
        return quickReplies?.isEmpty == false || interactiveComponents?.isEmpty == false
    }
    
    public var hasVisualizations: Bool {
        return visualizations?.isEmpty == false
    }
}

// MARK: - Streaming Support

public struct StreamingChunk: Codable, Sendable {
    public let type: String
    public let content: String?
    public let status: String?
    public let progress: Double?
    public let metadata: [String: Any]?
    
    enum CodingKeys: String, CodingKey {
        case type, content, status, progress, metadata
    }
    
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        type = try container.decode(String.self, forKey: .type)
        content = try container.decodeIfPresent(String.self, forKey: .content)
        status = try container.decodeIfPresent(String.self, forKey: .status)
        progress = try container.decodeIfPresent(Double.self, forKey: .progress)
        
        // Handle metadata dictionary (simplified)
        metadata = try container.decodeIfPresent([String: String].self, forKey: .metadata) as? [String: Any]
    }
    
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(type, forKey: .type)
        try container.encodeIfPresent(content, forKey: .content)
        try container.encodeIfPresent(status, forKey: .status)
        try container.encodeIfPresent(progress, forKey: .progress)
    }
}

public struct StreamingChatResponse: Codable, Sendable {
    public let requestId: String
    public let sessionId: Int
    public let userMessage: BackendChatMessage
    public let streamUrl: String
    
    enum CodingKeys: String, CodingKey {
        case requestId = "request_id"
        case sessionId = "session_id"
        case userMessage = "user_message"
        case streamUrl = "stream_url"
    }
}

public struct ChatStatusMessage: Codable, Sendable {
    public let sessionId: Int
    public let status: String
    public let message: String?
    public let progress: Double?
    public let agentName: String?
    
    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case status
        case message
        case progress
        case agentName = "agent_name"
    }
}

public struct ChatMessageUpdate: Codable, Sendable {
    public let sessionId: Int
    public let messageType: String
    public let newMessage: ChatMessage?
    public let messageCount: Int?
    public let lastMessageId: Int?
    
    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case messageType = "message_type"
        case newMessage = "new_message"
        case messageCount = "message_count"
        case lastMessageId = "last_message_id"
    }
}

// Helper for dynamic coding keys
private struct DynamicCodingKeys: CodingKey {
    var stringValue: String
    init?(stringValue: String) {
        self.stringValue = stringValue
    }
    
    var intValue: Int?
    init?(intValue: Int) {
        return nil
    }
}

// MARK: - Backend Chat Models

public struct ChatSessionResponse: Identifiable, Codable, Sendable {
    public let id: Int
    let title: String?
    let createdAt: Date
    let updatedAt: Date?
    let lastMessageAt: Date?
    let messageCount: Int?
    let hasVerification: Bool?
    let hasPrescriptions: Bool?
    let isActive: Bool?
    let enhancedModeEnabled: Bool?  // Backend-controlled enhanced features
    
    enum CodingKeys: String, CodingKey {
        case id
        case title
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case lastMessageAt = "last_message_at"
        case messageCount = "message_count"
        case hasVerification = "has_verification"
        case hasPrescriptions = "has_prescriptions"
        case isActive = "is_active"
        case enhancedModeEnabled = "enhanced_mode_enabled"
    }
}

public struct BackendChatMessage: Identifiable, Codable, Sendable {
    public let id: Int
    let sessionId: Int
    let userId: Int
    let content: String
    let role: String
    let createdAt: Date
    let tokensUsed: Int?
    let responseTimeMs: Int?
    // File attachment support
    let filePath: String?
    let fileType: String?
    // Visualization support
    let visualizations: [Visualization]?
    
    enum CodingKeys: String, CodingKey {
        case id
        case sessionId = "session_id"
        case userId = "user_id"
        case content
        case role
        case createdAt = "created_at"
        case tokensUsed = "tokens_used"
        case responseTimeMs = "response_time_ms"
        case filePath = "file_path"
        case fileType = "file_type"
        case visualizations
    }
    
    // Convert to local ChatMessage format
    public func toChatMessage() -> ChatMessage {
        let messageRole = MessageRole(rawValue: role) ?? .user
        
        // Extract filename from file path if available
        var fileName: String? = nil
        if let filePath = filePath {
            fileName = URL(fileURLWithPath: filePath).lastPathComponent
        }
        
        
        return ChatMessage(
            role: messageRole,
            content: content,
            timestamp: createdAt,
            filePath: filePath,
            fileType: fileType,
            fileName: fileName,
            visualizations: visualizations
        )
    }
}

public struct ChatMessageResponse: Codable, Sendable {
    let userMessage: BackendChatMessage
    let aiMessage: BackendChatMessage?
    let session: ChatSessionResponse
    
    enum CodingKeys: String, CodingKey {
        case userMessage = "user_message"
        case aiMessage = "ai_message"
        case session
    }
}

public struct ChatSessionCreate: Codable {
    let title: String?
    
    init(title: String? = nil) {
        self.title = title
    }
}

public struct ChatMessageCreate: Codable {
    let content: String
}
