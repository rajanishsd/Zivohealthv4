import Foundation
import SwiftUI

class PatientViewModel: ObservableObject {
    @Published var patients: [Patient] = []
    @Published var isLoading = false
    @Published var error: String?

    private let networkService = NetworkService.shared

    init() {
        loadPatients()
    }

    func loadPatients() {
        isLoading = true
        error = nil

        Task {
            do {
                let data = try await networkService.getPatients()
                let decoder = JSONDecoder()
                decoder.dateDecodingStrategy = .iso8601
                let response = try decoder.decode([Patient].self, from: data)

                await MainActor.run {
                    patients = response
                    isLoading = false
                }
            } catch NetworkService.NetworkError.authenticationFailed {
                await MainActor.run {
                    error = "Please log in to continue"
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    self.error = error.localizedDescription
                    isLoading = false
                }
            }
        }
    }

    func addPatient(name: String, dateOfBirth: Date, gender: String, contactNumber: String, email: String, address: String) {
        let patient: [String: Any] = [
            "name": name,
            "date_of_birth": ISO8601DateFormatter().string(from: dateOfBirth),
            "gender": gender,
            "contact_number": contactNumber,
            "email": email,
            "address": address,
        ]

        Task {
            do {
                _ = try await networkService.createPatient(patient)
                await MainActor.run {
                    loadPatients()
                }
            } catch {
                await MainActor.run {
                    self.error = error.localizedDescription
                }
            }
        }
    }

    func deletePatient(_ patient: Patient) {
        Task {
            do {
                try await networkService.deletePatient(id: patient.id)
                await MainActor.run {
                    loadPatients()
                }
            } catch {
                await MainActor.run {
                    self.error = error.localizedDescription
                }
            }
        }
    }

    func addHealthMetric(type: String, value: Double, unit: String, for patient: Patient) {
        let metric: [String: Any] = [
            "type": type,
            "value": value,
            "unit": unit,
            "date": ISO8601DateFormatter().string(from: Date()),
        ]

        Task {
            do {
                _ = try await networkService.addHealthMetric(patientId: patient.id, metric: metric)
                await MainActor.run {
                    loadPatients()
                }
            } catch {
                await MainActor.run {
                    self.error = error.localizedDescription
                }
            }
        }
    }

    func addLabReport(date: Date, testName: String, testResults: String, normalRange: String, unit: String, labName: String, doctorName: String, for patient: Patient) {
        let report: [String: Any] = [
            "date": ISO8601DateFormatter().string(from: date),
            "test_name": testName,
            "test_results": testResults,
            "normal_range": normalRange,
            "unit": unit,
            "lab_name": labName,
            "doctor_name": doctorName,
        ]

        Task {
            do {
                _ = try await networkService.addLabReport(patientId: patient.id, report: report)
                await MainActor.run {
                    loadPatients()
                }
            } catch {
                await MainActor.run {
                    self.error = error.localizedDescription
                }
            }
        }
    }
}
