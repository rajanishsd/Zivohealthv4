import Foundation

struct Patient: Identifiable, Codable, Hashable, Equatable {
    let id: String = UUID().uuidString
    var name: String = ""
    var dateOfBirth: Date = .init()
    var gender: String = ""
    var contactNumber: String = ""
    var email: String = ""
    var address: String = ""
    var medicalHistory: String?
    var currentMedications: [String] = []
    var allergies: [String] = []
    var labReports: [LabReport] = []
    var healthMetrics: [HealthMetric] = []

    init(name: String, dateOfBirth: Date, gender: String, contactNumber: String = "", email: String = "", address: String = "") {
        self.name = name
        self.dateOfBirth = dateOfBirth
        self.gender = gender
        self.contactNumber = contactNumber
        self.email = email
        self.address = address
    }

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case dateOfBirth = "date_of_birth"
        case gender
        case contactNumber = "contact_number"
        case email
        case address
        case medicalHistory = "medical_history"
        case currentMedications = "current_medications"
        case allergies
        case labReports = "lab_reports"
        case healthMetrics = "health_metrics"
    }

    // Hashable conformance
    func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }

    // Equatable conformance
    static func == (lhs: Patient, rhs: Patient) -> Bool {
        return lhs.id == rhs.id
    }
}
