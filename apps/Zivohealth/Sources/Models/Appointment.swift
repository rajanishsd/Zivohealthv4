import Foundation

struct Appointment: Identifiable, Codable {
    let id: Int
    let patientId: Int
    let doctorId: Int
    let consultationRequestId: Int?
    let title: String
    let description: String?
    let appointmentDate: Date
    let durationMinutes: Int
    let status: String
    let appointmentType: String
    let patientNotes: String?
    let doctorNotes: String?
    let createdAt: Date
    let updatedAt: Date
    
    enum CodingKeys: String, CodingKey {
        case id
        case patientId = "patient_id"
        case doctorId = "doctor_id"
        case consultationRequestId = "consultation_request_id"
        case title, description
        case appointmentDate = "appointment_date"
        case durationMinutes = "duration_minutes"
        case status
        case appointmentType = "appointment_type"
        case patientNotes = "patient_notes"
        case doctorNotes = "doctor_notes"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

struct AppointmentWithDetails: Identifiable, Codable {
    let id: Int
    let patientId: Int
    let doctorId: Int
    let consultationRequestId: Int?
    let title: String
    let description: String?
    let appointmentDate: Date
    let durationMinutes: Int
    let status: String
    let appointmentType: String
    let patientNotes: String?
    let doctorNotes: String?
    let createdAt: Date
    let updatedAt: Date
    let patientName: String
    let patientEmail: String
    let doctorName: String
    let doctorEmail: String
    
    enum CodingKeys: String, CodingKey {
        case id
        case patientId = "patient_id"
        case doctorId = "doctor_id"
        case consultationRequestId = "consultation_request_id"
        case title, description
        case appointmentDate = "appointment_date"
        case durationMinutes = "duration_minutes"
        case status
        case appointmentType = "appointment_type"
        case patientNotes = "patient_notes"
        case doctorNotes = "doctor_notes"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case patientName = "patient_name"
        case patientEmail = "patient_email"
        case doctorName = "doctor_name"
        case doctorEmail = "doctor_email"
    }
}

struct AppointmentCreate: Codable {
    let doctorId: Int
    let consultationRequestId: Int?
    let title: String
    let description: String?
    let appointmentDate: Date
    let durationMinutes: Int
    let status: String
    let appointmentType: String
    let patientNotes: String?
    
    enum CodingKeys: String, CodingKey {
        case doctorId = "doctor_id"
        case consultationRequestId = "consultation_request_id"
        case title, description
        case appointmentDate = "appointment_date"
        case durationMinutes = "duration_minutes"
        case status
        case appointmentType = "appointment_type"
        case patientNotes = "patient_notes"
    }
}

struct AppointmentUpdate: Codable {
    let title: String?
    let description: String?
    let appointmentDate: Date?
    let durationMinutes: Int?
    let status: String?
    let appointmentType: String?
    let patientNotes: String?
    let doctorNotes: String?
    
    enum CodingKeys: String, CodingKey {
        case title, description
        case appointmentDate = "appointment_date"
        case durationMinutes = "duration_minutes"
        case status
        case appointmentType = "appointment_type"
        case patientNotes = "patient_notes"
        case doctorNotes = "doctor_notes"
    }
} 