import SwiftUI
import UIKit

struct AppointmentDetailView: View {
    @ObservedObject var appointmentViewModel: AppointmentViewModel
    @State private var currentAppointment: AppointmentWithDetails
    @Environment(\.dismiss) private var dismiss
    @State private var showingEditView = false
    @State private var showingCancelAlert = false
    @State private var isLoading = false
    
    init(appointment: AppointmentWithDetails, appointmentViewModel: AppointmentViewModel) {
        self._currentAppointment = State(initialValue: appointment)
        self.appointmentViewModel = appointmentViewModel
    }
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Appointment Header
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(currentAppointment.title)
                                    .font(.title2)
                                    .fontWeight(.bold)
                                
                                Text("Dr. \(currentAppointment.doctorName)")
                                    .font(.headline)
                                    .foregroundColor(.blue)
                            }
                            
                            Spacer()
                            
                            StatusBadge(status: currentAppointment.status)
                        }
                        
                        Divider()
                        
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Image(systemName: "calendar")
                                    .foregroundColor(.secondary)
                                Text(currentAppointment.appointmentDate.formatted(date: .abbreviated, time: .shortened))
                                    .font(.subheadline)
                            }
                            
                            HStack {
                                Image(systemName: "clock")
                                    .foregroundColor(.secondary)
                                Text("\(currentAppointment.durationMinutes) minutes")
                                    .font(.subheadline)
                            }
                            
                            HStack {
                                Image(systemName: "stethoscope")
                                    .foregroundColor(.secondary)
                                Text(currentAppointment.appointmentType.capitalized)
                                    .font(.subheadline)
                            }
                        }
                    }
                    .padding()
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(12)
                    
                    // Description
                    if let description = currentAppointment.description, !description.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Description")
                                .font(.headline)
                            
                            Text(description)
                                .font(.body)
                                .foregroundColor(.secondary)
                        }
                        .padding()
                        .background(Color.gray.opacity(0.1))
                        .cornerRadius(12)
                    }
                    
                    // Patient Notes
                    if let patientNotes = currentAppointment.patientNotes, !patientNotes.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Your Notes")
                                .font(.headline)
                            
                            Text(patientNotes)
                                .font(.body)
                                .foregroundColor(.secondary)
                        }
                        .padding()
                        .background(Color.gray.opacity(0.1))
                        .cornerRadius(12)
                    }
                    
                    // Doctor Notes
                    if let doctorNotes = currentAppointment.doctorNotes, !doctorNotes.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Doctor's Notes")
                                .font(.headline)
                            
                            Text(doctorNotes)
                                .font(.system(size: UIFont.preferredFont(forTextStyle: .body).pointSize * 0.6))
                                .foregroundColor(.secondary)
                        }
                        .padding()
                        .background(Color.blue.opacity(0.1))
                        .cornerRadius(12)
                    }
                    
                    // Action Buttons
                    if currentAppointment.status != "completed" && currentAppointment.status != "cancelled" {
                        VStack(spacing: 12) {
                            Button(action: {
                                showingEditView = true
                            }) {
                                HStack {
                                    Image(systemName: "pencil")
                                    Text("Edit Appointment")
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.blue)
                                .foregroundColor(.white)
                                .cornerRadius(12)
                            }
                            .disabled(isLoading)
                            
                            Button(action: {
                                showingCancelAlert = true
                            }) {
                                HStack {
                                    Image(systemName: "xmark.circle")
                                    Text("Cancel Appointment")
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.red)
                                .foregroundColor(.white)
                                .cornerRadius(12)
                            }
                            .disabled(isLoading)
                        }
                    }
                }
                .padding()
            }
            .navigationTitle("Appointment Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
            .sheet(isPresented: $showingEditView) {
                CreateAppointmentView(
                    appointmentViewModel: appointmentViewModel,
                    editingAppointment: currentAppointment
                )
            }
            .onChange(of: showingEditView) { isPresented in
                if !isPresented {
                    Task {
                        do {
                            let updated = try await appointmentViewModel.getAppointmentById(id: currentAppointment.id)
                            await MainActor.run {
                                currentAppointment = updated
                            }
                            appointmentViewModel.refreshAppointments()
                        } catch {
                            // Ignore errors; list refresh still occurs
                            appointmentViewModel.refreshAppointments()
                        }
                    }
                }
            }
            .alert("Cancel Appointment", isPresented: $showingCancelAlert) {
                Button("Cancel", role: .destructive) {
                    cancelAppointment()
                }
                Button("Keep Appointment", role: .cancel) { }
            } message: {
                Text("Are you sure you want to cancel this appointment? This action cannot be undone.")
            }
        }
    }
    
    private func cancelAppointment() {
        isLoading = true
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
                try await appointmentViewModel.updateAppointment(id: currentAppointment.id, update: update)
                await MainActor.run {
                    isLoading = false
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                    appointmentViewModel.error = error.localizedDescription
                }
            }
        }
    }
} 