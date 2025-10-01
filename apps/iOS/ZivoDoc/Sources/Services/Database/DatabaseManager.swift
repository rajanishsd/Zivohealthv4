import Foundation

class DatabaseManager {
    static let shared = DatabaseManager()
    private var patients: [Patient] = []

    private init() {
        // Initialize with some sample data if needed
    }

    // MARK: - Patient Operations

    func savePatient(_ patient: Patient) throws {
        if let existingIndex = patients.firstIndex(where: { $0.id == patient.id }) {
            patients[existingIndex] = patient
        } else {
            patients.append(patient)
        }
    }

    func deletePatient(_ patient: Patient) throws {
        patients.removeAll { $0.id == patient.id }
    }

    func getPatient(id: String) throws -> Patient? {
        return patients.first { $0.id == id }
    }

    func getAllPatients() -> [Patient] {
        return patients
    }

    // MARK: - Lab Report Operations

    func saveLabReport(_ report: LabReport, for patient: Patient) throws {
        if let index = patients.firstIndex(where: { $0.id == patient.id }) {
            var updatedPatient = patients[index]
            updatedPatient.labReports.append(report)
            patients[index] = updatedPatient
        }
    }

    // MARK: - Health Metric Operations

    func saveHealthMetric(_ metric: HealthMetric, for patient: Patient) throws {
        if let index = patients.firstIndex(where: { $0.id == patient.id }) {
            var updatedPatient = patients[index]
            updatedPatient.healthMetrics.append(metric)
            patients[index] = updatedPatient
        }
    }

    func getHealthMetrics(for patient: Patient, ofType type: String) -> [HealthMetric] {
        return patient.healthMetrics.filter { $0.type == type }
    }
}
