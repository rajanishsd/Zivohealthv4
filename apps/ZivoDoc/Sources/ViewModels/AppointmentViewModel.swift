import Foundation
import SwiftUI
import Combine

@MainActor
class AppointmentViewModel: ObservableObject {
    static let shared = AppointmentViewModel()
    
    @Published var appointments: [AppointmentWithDetails] = []
    @Published var isLoading = false
    @Published var error: String?
    @Published var selectedAppointment: AppointmentWithDetails?
    
    private let networkService = NetworkService.shared
    @AppStorage("userMode") private var userMode: UserMode = .patient
    @Published private var observedUserMode: UserMode = .patient
    private var cancellables = Set<AnyCancellable>()
    
    private init() {
        // Initialize observed user mode
        observedUserMode = userMode
        
        // Start observing role changes using a timer-based approach
        startObservingRoleChanges()
    }
    
    private func startObservingRoleChanges() {
        // Observe user mode changes every second
        Timer.publish(every: 1.0, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                guard let self = self else { return }
                if self.observedUserMode != self.userMode {
                    self.observedUserMode = self.userMode
                    self.forceRefreshForRoleChange()
                }
            }
            .store(in: &cancellables)
    }
    
    func forceRefreshForRoleChange() {
        appointments = []
        loadAppointments()
    }
    
    func loadAppointments() {
        isLoading = true
        error = nil
        
        Task {
            do {
                let fetchedAppointments = try await networkService.getAppointments()
                await MainActor.run {
                    self.appointments = fetchedAppointments
                    self.isLoading = false
                }
            } catch {
                await MainActor.run {
                    self.error = error.localizedDescription
                    self.isLoading = false
                }
            }
        }
    }
    
    func createAppointment(_ appointmentCreate: AppointmentCreate) async throws -> Appointment {
        let appointment = try await networkService.createAppointment(appointmentCreate)
        // Reload appointments to get updated list
        loadAppointments()
        return appointment
    }
    
    func updateAppointment(id: Int, update: AppointmentUpdate) async throws {
        _ = try await networkService.updateAppointment(id: id, update: update)
        // Reload appointments to get updated list
        loadAppointments()
    }
    
    func deleteAppointment(id: Int) async throws {
        try await networkService.deleteAppointment(id: id)
        // Remove from local list and reload
        appointments.removeAll { $0.id == id }
        loadAppointments()
    }
    
    func getAppointmentById(id: Int) async throws -> AppointmentWithDetails {
        return try await networkService.getAppointment(id: id)
    }
    
    func refreshAppointments() {
        loadAppointments()
    }
    
    // Helper functions for appointment status
    func upcomingAppointments() -> [AppointmentWithDetails] {
        let currentDate = Date()
        return appointments.filter { 
            $0.appointmentDate > currentDate && ($0.status == "scheduled" || $0.status == "confirmed")
        }
    }
    
    func pastAppointments() -> [AppointmentWithDetails] {
        let currentDate = Date()
        return appointments.filter { 
            $0.appointmentDate < currentDate && ($0.status == "completed")
        }
    }
    
    func cancelledAppointments() -> [AppointmentWithDetails] {
        return appointments.filter { $0.status == "cancelled" }
    }
} 