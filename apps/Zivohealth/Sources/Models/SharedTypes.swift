import Foundation
import SwiftUI

// MARK: - Doctor Types

struct Doctor: Identifiable, Codable, Hashable {
    let id: Int
    let fullName: String
    let specialization: String
    let yearsExperience: Int
    let rating: Double
    let totalConsultations: Int
    let bio: String?
    let isAvailable: Bool
    let profileImageURL: String?

    init(
        id: Int,
        fullName: String,
        specialization: String,
        yearsExperience: Int,
        rating: Double,
        totalConsultations: Int,
        bio: String?,
        isAvailable: Bool,
        profileImageURL: String? = nil
    ) {
        self.id = id
        self.fullName = fullName
        self.specialization = specialization
        self.yearsExperience = yearsExperience
        self.rating = rating
        self.totalConsultations = totalConsultations
        self.bio = bio
        self.isAvailable = isAvailable
        self.profileImageURL = profileImageURL
    }

    enum CodingKeys: String, CodingKey {
        case id
        case fullName = "full_name"
        case specialization
        case yearsExperience = "years_experience"
        case rating
        case totalConsultations = "total_consultations"
        case bio
        case isAvailable = "is_available"
        case profileImageURL = "profile_image_url"
    }
}

// MARK: - Consultation Request Types

struct ConsultationRequestResponse: Identifiable, Codable, Equatable {
    let id: Int
    let userId: Int
    let doctorId: Int
    let chatSessionId: Int?
    let clinicalReportId: Int?
    let context: String
    let userQuestion: String
    let status: String
    let urgencyLevel: String
    let createdAt: Date
    let acceptedAt: Date?
    let completedAt: Date?
    let doctorNotes: String?

    enum CodingKeys: String, CodingKey {
        case id
        case userId = "user_id"
        case doctorId = "doctor_id"
        case chatSessionId = "chat_session_id"
        case clinicalReportId = "clinical_report_id"
        case context
        case userQuestion = "user_question"
        case status
        case urgencyLevel = "urgency_level"
        case createdAt = "created_at"
        case acceptedAt = "accepted_at"
        case completedAt = "completed_at"
        case doctorNotes = "doctor_notes"
    }
}

struct ConsultationRequestWithDoctor: Identifiable, Codable {
    let id: Int
    let userId: Int
    let doctorId: Int
    let chatSessionId: Int?
    let clinicalReportId: Int?
    let context: String
    let userQuestion: String
    let status: String
    let urgencyLevel: String
    let createdAt: Date
    let acceptedAt: Date?
    let completedAt: Date?
    let doctorNotes: String?
    let doctor: Doctor

    enum CodingKeys: String, CodingKey {
        case id
        case userId = "user_id"
        case doctorId = "doctor_id"
        case chatSessionId = "chat_session_id"
        case clinicalReportId = "clinical_report_id"
        case context
        case userQuestion = "user_question"
        case status
        case urgencyLevel = "urgency_level"
        case createdAt = "created_at"
        case acceptedAt = "accepted_at"
        case completedAt = "completed_at"
        case doctorNotes = "doctor_notes"
        case doctor
    }
}

// MARK: - Clinical Report Types

struct ClinicalReport: Identifiable, Codable {
    let id: Int
    let userId: Int
    let chatSessionId: Int
    let messageId: Int?
    let userQuestion: String
    let aiResponse: String
    let comprehensiveContext: String
    let dataSourcesSummary: String?
    let vitalsData: String?
    let nutritionData: String?
    let prescriptionData: String?
    let labData: String?
    let pharmacyData: String?
    let agentRequirements: String?
    let createdAt: Date
    let updatedAt: Date?

    enum CodingKeys: String, CodingKey {
        case id
        case userId = "user_id"
        case chatSessionId = "chat_session_id"
        case messageId = "message_id"
        case userQuestion = "user_question"
        case aiResponse = "ai_response"
        case comprehensiveContext = "comprehensive_context"
        case dataSourcesSummary = "data_sources_summary"
        case vitalsData = "vitals_data"
        case nutritionData = "nutrition_data"
        case prescriptionData = "prescription_data"
        case labData = "lab_data"
        case pharmacyData = "pharmacy_data"
        case agentRequirements = "agent_requirements"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

struct ConsultationRequestWithClinicalReport: Identifiable, Codable {
    let id: Int
    let userId: Int
    let doctorId: Int
    let chatSessionId: Int?
    let clinicalReportId: Int?
    let context: String
    let userQuestion: String
    let status: String
    let urgencyLevel: String
    let createdAt: Date
    let acceptedAt: Date?
    let completedAt: Date?
    let doctorNotes: String?
    let doctor: Doctor
    let clinicalReport: ClinicalReport?

    enum CodingKeys: String, CodingKey {
        case id
        case userId = "user_id"
        case doctorId = "doctor_id"
        case chatSessionId = "chat_session_id"
        case clinicalReportId = "clinical_report_id"
        case context
        case userQuestion = "user_question"
        case status
        case urgencyLevel = "urgency_level"
        case createdAt = "created_at"
        case acceptedAt = "accepted_at"
        case completedAt = "completed_at"
        case doctorNotes = "doctor_notes"
        case doctor
        case clinicalReport = "clinical_report"
    }
}

// MARK: - User Mode

enum UserMode: String, CaseIterable {
    case patient
    case doctor
}

// MARK: - Chat Session Types

struct ChatSession: Identifiable, Codable {
    let id: UUID
    let title: String
    let createdAt: Date
    let lastMessageAt: Date
    let messageCount: Int
    let hasVerification: Bool
    let hasPrescriptions: Bool
    
    init(
        id: UUID = UUID(),
        title: String,
        createdAt: Date = Date(),
        lastMessageAt: Date = Date(),
        messageCount: Int = 0,
        hasVerification: Bool = false,
        hasPrescriptions: Bool = false
    ) {
        self.id = id
        self.title = title
        self.createdAt = createdAt
        self.lastMessageAt = lastMessageAt
        self.messageCount = messageCount
        self.hasVerification = hasVerification
        self.hasPrescriptions = hasPrescriptions
    }
}

struct ChatSessionWithMessages: Identifiable, Codable {
    let session: ChatSession
    let messages: [ChatMessage]
    let verificationRequest: ConsultationRequestResponse?
    let prescriptions: [Prescription]
    
    var id: UUID { session.id }
    
    init(
        session: ChatSession,
        messages: [ChatMessage] = [],
        verificationRequest: ConsultationRequestResponse? = nil,
        prescriptions: [Prescription] = []
    ) {
        self.session = session
        self.messages = messages
        self.verificationRequest = verificationRequest
        self.prescriptions = prescriptions
    }
}

struct Prescription: Identifiable, Codable {
    let id: UUID
    var medicationName: String
    var dosage: String
    var frequency: String
    var instructions: String
    let prescribedBy: String
    let prescribedAt: Date
    
    init(
        id: UUID = UUID(),
        medicationName: String = "",
        dosage: String = "",
        frequency: String = "",
        instructions: String = "",
        prescribedBy: String = "",
        prescribedAt: Date = Date()
    ) {
        self.id = id
        self.medicationName = medicationName
        self.dosage = dosage
        self.frequency = frequency
        self.instructions = instructions
        self.prescribedBy = prescribedBy
        self.prescribedAt = prescribedAt
    }
}

struct PrescriptionWithSession: Identifiable, Codable {
    let id: String
    let medicationName: String
    let dosage: String
    let frequency: String
    let instructions: String
    let prescribedBy: String
    let prescribedAt: Date
    let consultationId: Int
    let chatSessionId: Int?
    let doctorName: String
    let sessionTitle: String?
    
    // Convert to regular Prescription
    var prescription: Prescription {
        Prescription(
            id: UUID(uuidString: id) ?? UUID(),
            medicationName: medicationName,
            dosage: dosage,
            frequency: frequency,
            instructions: instructions,
            prescribedBy: prescribedBy,
            prescribedAt: prescribedAt
        )
    }
    
    enum CodingKeys: String, CodingKey {
        case id
        case medicationName = "medication_name"
        case dosage
        case frequency
        case instructions
        case prescribedBy = "prescribed_by"
        case prescribedAt = "prescribed_at"
        case consultationId = "consultation_id"
        case chatSessionId = "chat_session_id"
        case doctorName = "doctor_name"
        case sessionTitle = "session_title"
    }
}

// Backend Chat Session (matches backend API schema)
public struct BackendChatSession: Identifiable, Codable {
    public let id: Int
    public let title: String
    public let userId: Int
    public let createdAt: String
    public let updatedAt: String
    public let lastMessageAt: String
    public let messageCount: Int
    public let hasVerification: Bool
    public let hasPrescriptions: Bool
    public let isActive: Bool
    
    public enum CodingKeys: String, CodingKey {
        case id, title
        case userId = "user_id"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case lastMessageAt = "last_message_at"
        case messageCount = "message_count"
        case hasVerification = "has_verification"
        case hasPrescriptions = "has_prescriptions"
        case isActive = "is_active"
    }
}

// MARK: - Health Insights

struct HealthInsight {
    let icon: String
    let color: Color
    let title: String
    let message: String
}
