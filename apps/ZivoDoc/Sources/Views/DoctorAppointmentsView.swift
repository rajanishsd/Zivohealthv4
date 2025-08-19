import SwiftUI

struct DoctorAppointmentsView: View {
    @ObservedObject private var appointmentViewModel = AppointmentViewModel.shared
    @State private var selectedAppointment: AppointmentWithDetails?
    @State private var showingAppointmentDetail = false
    @AppStorage("userMode") private var userMode: UserMode = .doctor
    
    var body: some View {
        NavigationView {
            VStack {
                if appointmentViewModel.isLoading {
                    ProgressView("Loading appointments...")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if appointmentViewModel.appointments.isEmpty {
                    // Empty state
                    VStack(spacing: 24) {
                        Spacer()
                        
                        Image(systemName: "calendar.badge.clock")
                            .font(.system(size: 64))
                            .foregroundColor(.blue.opacity(0.6))
                        
                        VStack(spacing: 8) {
                            Text("No Appointments")
                                .font(.title2)
                                .fontWeight(.semibold)
                            
                            Text("No patients have scheduled appointments with you yet")
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
                                    DoctorAppointmentRow(appointment: appointment)
                                        .onTapGesture {
                                            selectedAppointment = appointment
                                            showingAppointmentDetail = true
                                        }
                                }
                            }
                        }
                        
                        // Past Appointments
                        let pastAppointments = appointmentViewModel.pastAppointments()
                        if !pastAppointments.isEmpty {
                            Section("Past Appointments") {
                                ForEach(pastAppointments) { appointment in
                                    DoctorAppointmentRow(appointment: appointment)
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
                                    DoctorAppointmentRow(appointment: appointment)
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
            .navigationTitle("My Appointments")
            .navigationBarTitleDisplayMode(.large)
            .sheet(isPresented: $showingAppointmentDetail) {
                if let appointment = selectedAppointment {
                    DoctorAppointmentDetailView(appointment: appointment, appointmentViewModel: appointmentViewModel)
                }
            }
            .onAppear {
                if userMode != .doctor {
                    userMode = .doctor
                    NetworkService.shared.handleRoleChange()
                }
                appointmentViewModel.loadAppointments()
            }
            .onChange(of: userMode) { newUserMode in
                if newUserMode == .doctor {
                    appointmentViewModel.forceRefreshForRoleChange()
                }
            }
            .alert("Error", isPresented: .constant(appointmentViewModel.error != nil)) {
                Button("OK") {
                    appointmentViewModel.error = nil
                }
            } message: {
                Text(appointmentViewModel.error ?? "")
            }
        }
    }
    
    private func todaysAppointments() -> [AppointmentWithDetails] {
        return appointmentViewModel.appointments.filter { 
            Calendar.current.isDateInToday($0.appointmentDate) && 
            ($0.status == "scheduled" || $0.status == "confirmed")
        }
    }
    
    private func confirmAppointment(_ appointment: AppointmentWithDetails) {
        Task {
            do {
                let update = AppointmentUpdate(
                    title: nil,
                    description: nil,
                    appointmentDate: nil,
                    durationMinutes: nil,
                    status: "confirmed",
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
    
    private func completeAppointment(_ appointment: AppointmentWithDetails) {
        Task {
            do {
                let update = AppointmentUpdate(
                    title: nil,
                    description: nil,
                    appointmentDate: nil,
                    durationMinutes: nil,
                    status: "completed",
                    appointmentType: nil,
                    patientNotes: nil,
                    doctorNotes: "Appointment completed"
                )
                try await appointmentViewModel.updateAppointment(id: appointment.id, update: update)
            } catch {
                appointmentViewModel.error = error.localizedDescription
            }
        }
    }
}

struct DoctorAppointmentRow: View {
    let appointment: AppointmentWithDetails
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(appointment.title)
                        .font(.headline)
                        .foregroundColor(.primary)
                    
                    Text("Patient: \(appointment.patientName)")
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
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .gray.opacity(0.2), radius: 2, x: 0, y: 1)
    }
}

struct DoctorAppointmentDetailView: View {
    let appointment: AppointmentWithDetails
    @ObservedObject var appointmentViewModel: AppointmentViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var doctorNotes: String = ""
    @State private var isLoading = false
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Patient Information
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Patient Information")
                            .font(.headline)
                        
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text("Name:")
                                    .fontWeight(.medium)
                                Spacer()
                                Text(appointment.patientName)
                            }
                            
                            HStack {
                                Text("Date & Time:")
                                    .fontWeight(.medium)
                                Spacer()
                                Text(appointment.appointmentDate.formatted(date: .abbreviated, time: .shortened))
                            }
                            
                            HStack {
                                Text("Duration:")
                                    .fontWeight(.medium)
                                Spacer()
                                Text("\(appointment.durationMinutes) minutes")
                            }
                            
                            HStack {
                                Text("Type:")
                                    .fontWeight(.medium)
                                Spacer()
                                Text(appointment.appointmentType.capitalized)
                            }
                            
                            HStack {
                                Text("Status:")
                                    .fontWeight(.medium)
                                Spacer()
                                StatusBadge(status: appointment.status)
                            }
                        }
                    }
                    .padding()
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(12)
                    
                    // Appointment Details
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Appointment Details")
                            .font(.headline)
                        
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Title:")
                                .fontWeight(.medium)
                            Text(appointment.title)
                                .foregroundColor(.secondary)
                            
                            if let description = appointment.description, !description.isEmpty {
                                Text("Description:")
                                    .fontWeight(.medium)
                                Text(description)
                                    .foregroundColor(.secondary)
                            }
                            
                            if let patientNotes = appointment.patientNotes, !patientNotes.isEmpty {
                                Text("Patient Notes:")
                                    .fontWeight(.medium)
                                Text(patientNotes)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                    .padding()
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(12)
                    
                    // Doctor Notes Section
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Doctor Notes")
                            .font(.headline)
                        
                        TextField("Add your notes about this appointment...", text: $doctorNotes)
                            .textFieldStyle(.roundedBorder)
                            .lineLimit(6)
                    }
                    .padding()
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(12)
                    
                    // Action Buttons
                    VStack(spacing: 12) {
                        if appointment.status == "scheduled" {
                            Button(action: confirmAppointment) {
                                HStack {
                                    Image(systemName: "checkmark.circle.fill")
                                    Text("Confirm Appointment")
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.green)
                                .foregroundColor(.white)
                                .cornerRadius(12)
                            }
                            .disabled(isLoading)
                        }
                        
                        if appointment.status != "completed" {
                            Button(action: completeAppointment) {
                                HStack {
                                    Image(systemName: "checkmark.circle")
                                    Text("Mark as Completed")
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.blue)
                                .foregroundColor(.white)
                                .cornerRadius(12)
                            }
                            .disabled(isLoading)
                        }
                        
                        Button(action: saveNotes) {
                            HStack {
                                Image(systemName: "square.and.pencil")
                                Text("Save Notes")
                            }
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color.orange)
                            .foregroundColor(.white)
                            .cornerRadius(12)
                        }
                        .disabled(isLoading || doctorNotes.isEmpty)
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
            .onAppear {
                doctorNotes = appointment.doctorNotes ?? ""
            }
        }
    }
    
    private func confirmAppointment() {
        isLoading = true
        Task {
            do {
                let update = AppointmentUpdate(
                    title: nil,
                    description: nil,
                    appointmentDate: nil,
                    durationMinutes: nil,
                    status: "confirmed",
                    appointmentType: nil,
                    patientNotes: nil,
                    doctorNotes: nil
                )
                try await appointmentViewModel.updateAppointment(id: appointment.id, update: update)
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
    
    private func completeAppointment() {
        isLoading = true
        Task {
            do {
                let update = AppointmentUpdate(
                    title: nil,
                    description: nil,
                    appointmentDate: nil,
                    durationMinutes: nil,
                    status: "completed",
                    appointmentType: nil,
                    patientNotes: nil,
                    doctorNotes: doctorNotes.isEmpty ? "Appointment completed" : doctorNotes
                )
                try await appointmentViewModel.updateAppointment(id: appointment.id, update: update)
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
    
    private func saveNotes() {
        isLoading = true
        Task {
            do {
                let update = AppointmentUpdate(
                    title: nil,
                    description: nil,
                    appointmentDate: nil,
                    durationMinutes: nil,
                    status: nil,
                    appointmentType: nil,
                    patientNotes: nil,
                    doctorNotes: doctorNotes
                )
                try await appointmentViewModel.updateAppointment(id: appointment.id, update: update)
                await MainActor.run {
                    isLoading = false
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