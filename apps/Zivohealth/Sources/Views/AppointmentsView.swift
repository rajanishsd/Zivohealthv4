import SwiftUI

struct AppointmentsView: View {
    @ObservedObject private var appointmentViewModel = AppointmentViewModel.shared
    @State private var showingCreateAppointment = false
    @State private var selectedAppointment: AppointmentWithDetails?
    @State private var showingAppointmentDetail = false
    
    var body: some View {
        VStack {
            if appointmentViewModel.isLoading {
                ProgressView("Loading appointments...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if appointmentViewModel.appointments.isEmpty {
                // Empty state
                VStack(spacing: 24) {
                    Spacer()
                    
                    Image(systemName: "calendar.badge.plus")
                        .font(.system(size: 64))
                        .foregroundColor(.blue.opacity(0.6))
                    
                    VStack(spacing: 8) {
                        Text("No Appointments")
                            .font(.title2)
                            .fontWeight(.semibold)
                        
                        Text("Your appointments will appear here")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    
                    Spacer()
                }
                .padding()
            } else {
                List {
                    // Upcoming Appointments
                    let upcomingAppointments = appointmentViewModel.upcomingAppointments()
                    if !upcomingAppointments.isEmpty {
                        Section("Upcoming Appointments") {
                            ForEach(upcomingAppointments) { appointment in
                                AppointmentRow(appointment: appointment)
                                    .onTapGesture {
                                        selectedAppointment = appointment
                                        showingAppointmentDetail = true
                                    }
                                    .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                                        Button("Cancel", role: .destructive) {
                                            cancelAppointment(appointment)
                                        }
                                        
                                        Button("Edit") {
                                            selectedAppointment = appointment
                                            showingCreateAppointment = true
                                        }
                                        .tint(.blue)
                                    }
                            }
                        }
                    }
                    
                    // Past Appointments
                    let pastAppointments = appointmentViewModel.pastAppointments()
                    if !pastAppointments.isEmpty {
                        Section("Past Appointments") {
                            ForEach(pastAppointments) { appointment in
                                AppointmentRow(appointment: appointment)
                                    .onTapGesture {
                                        selectedAppointment = appointment
                                        showingAppointmentDetail = true
                                    }
                            }
                        }
                    }
                    
                    // Cancelled Appointments
                    let cancelledAppointments = appointmentViewModel.cancelledAppointments()
                    if !cancelledAppointments.isEmpty {
                        Section("Cancelled Appointments") {
                            ForEach(cancelledAppointments) { appointment in
                                AppointmentRow(appointment: appointment)
                                    .onTapGesture {
                                        selectedAppointment = appointment
                                        showingAppointmentDetail = true
                                    }
                            }
                        }
                    }
                }
                .refreshable {
                    appointmentViewModel.refreshAppointments()
                }
            }
        }
        .navigationTitle("Appointments")
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            // Empty toolbar to override inherited toolbar items
        }
        .sheet(isPresented: $showingCreateAppointment) {
            CreateAppointmentView(
                appointmentViewModel: appointmentViewModel,
                editingAppointment: selectedAppointment
            )
        }
        .sheet(isPresented: $showingAppointmentDetail) {
            if let appointment = selectedAppointment {
                AppointmentDetailView(appointment: appointment, appointmentViewModel: appointmentViewModel)
            }
        }
        .onAppear {
            appointmentViewModel.loadAppointments()
        }
        .alert("Error", isPresented: .constant(appointmentViewModel.error != nil)) {
            Button("OK") {
                appointmentViewModel.error = nil
            }
        } message: {
            Text(appointmentViewModel.error ?? "")
        }
    }
    
    private func cancelAppointment(_ appointment: AppointmentWithDetails) {
        Task {
            do {
                let update = AppointmentUpdate(
                    title: nil,
                    description: nil,
                    appointmentDate: nil,
                    durationMinutes: nil,
                    status: "cancelled",
                    appointmentType: nil,
                    patientNotes: nil,
                    doctorNotes: nil
                )
                try await appointmentViewModel.updateAppointment(id: appointment.id, update: update)
            } catch {
                appointmentViewModel.error = error.localizedDescription
            }
        }
    }
}

struct AppointmentRow: View {
    let appointment: AppointmentWithDetails
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(appointment.title)
                        .font(.headline)
                        .foregroundColor(.primary)
                    
                    Text("Doctor: \(appointment.doctorName)")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                StatusBadge(status: appointment.status)
            }
            
            HStack {
                Label(
                    appointment.appointmentDate.formatted(date: .abbreviated, time: .shortened),
                    systemImage: "calendar"
                )
                .font(.caption)
                .foregroundColor(.secondary)
                
                Spacer()
                
                Label(
                    "\(appointment.durationMinutes) min",
                    systemImage: "clock"
                )
                .font(.caption)
                .foregroundColor(.secondary)
            }
            
            if appointment.appointmentType != "unknown" {
                HStack {
                    Label(
                        appointment.appointmentType.capitalized.replacingOccurrences(of: "_", with: " "),
                        systemImage: "stethoscope"
                    )
                    .font(.caption)
                    .foregroundColor(.blue)
                    
                    Spacer()
                }
            }
            
            if let description = appointment.description, !description.isEmpty {
                HStack {
                    Label(description, systemImage: "note.text")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(2)
                    
                    Spacer()
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .gray.opacity(0.2), radius: 2, x: 0, y: 1)
    }
} 