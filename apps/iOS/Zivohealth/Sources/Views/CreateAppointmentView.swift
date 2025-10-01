import SwiftUI

struct CreateAppointmentView: View {
    @ObservedObject var appointmentViewModel: AppointmentViewModel
    let editingAppointment: AppointmentWithDetails?
    @Environment(\.dismiss) private var dismiss
    
    @State private var title = ""
    @State private var description = ""
    @State private var appointmentDate = Date()
    @State private var durationMinutes = 30
    @State private var appointmentType = "consultation"
    @State private var patientNotes = ""
    @State private var selectedDoctor: Doctor?
    @State private var doctors: [Doctor] = []
    @State private var isLoading = false
    @State private var error: String?
    
    private let appointmentTypes = ["consultation", "follow_up", "emergency"]
    private let durations = [15, 30, 45, 60, 90, 120]
    
    var isEditing: Bool {
        editingAppointment != nil
    }
    
    var body: some View {
        NavigationView {
            Form {
                if !isEditing {
                Section("Appointment Details") {
                    TextField("Title", text: $title)
                    
                    TextField("Description (Optional)", text: $description)
                        .lineLimit(5)
                }
                }
                
                if !isEditing {
                Section("Doctor") {
                    if doctors.isEmpty {
                        HStack {
                            ProgressView()
                                .scaleEffect(0.8)
                            Text("Loading doctors...")
                                .foregroundColor(.secondary)
                        }
                    } else {
                        Picker("Select Doctor", selection: $selectedDoctor) {
                            Text("Select a doctor").tag(nil as Doctor?)
                            ForEach(doctors, id: \.id) { doctor in
                                VStack(alignment: .leading) {
                                    Text("Dr. \(doctor.fullName)")
                                        .font(.headline)
                                    Text(doctor.specialization)
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                                .tag(doctor as Doctor?)
                            }
                        }
                        .pickerStyle(.menu)
                    }
                }
                }
                
                Section("Schedule") {
                    DatePicker("Date & Time", selection: $appointmentDate, in: Date()...)
                        .datePickerStyle(.compact)
                    
                    if !isEditing {
                        Picker("Duration", selection: $durationMinutes) {
                            ForEach(durations, id: \.self) { duration in
                                Text("\(duration) minutes").tag(duration)
                            }
                        }
                        .pickerStyle(.menu)
                        
                        Picker("Type", selection: $appointmentType) {
                            ForEach(appointmentTypes, id: \.self) { type in
                                Text(type.capitalized).tag(type)
                            }
                        }
                        .pickerStyle(.segmented)
                    }
                }
                
                if !isEditing {
                Section("Notes") {
                    TextField("Patient notes (Optional)", text: $patientNotes)
                        .lineLimit(5)
                }
                }
            }
            .navigationTitle(isEditing ? "Edit Appointment" : "New Appointment")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar(content: toolbarContent)
            .onAppear {
                if let appointment = editingAppointment {
                    populateFields(from: appointment)
                } else {
                    loadDoctors()
                }
            }
            .alert("Error", isPresented: .constant(error != nil)) {
                Button("OK") {
                    error = nil
                }
            } message: {
                Text(error ?? "")
            }
        }
    }
    
    @ToolbarContentBuilder
    private func toolbarContent() -> some ToolbarContent {
        ToolbarItem(placement: .navigationBarLeading) {
            Button("Cancel") {
                dismiss()
            }
        }
        
        ToolbarItem(placement: .navigationBarTrailing) {
            Button(isEditing ? "Update" : "Schedule") {
                if isEditing {
                    updateAppointment()
                } else {
                    createAppointment()
                }
            }
            .disabled(isEditing ? isLoading : (title.isEmpty || selectedDoctor == nil || isLoading))
        }
    }
    
    private func loadDoctors() {
        // For now, create some sample doctors
        // In a real app, this would fetch from the API
        doctors = [
            Doctor(
                id: 1,
                fullName: "John Smith",
                specialization: "General Medicine",
                yearsExperience: 10,
                rating: 4.8,
                totalConsultations: 150,
                bio: "Experienced general practitioner",
                isAvailable: true
            ),
            Doctor(
                id: 2,
                fullName: "Sarah Johnson",
                specialization: "Cardiology",
                yearsExperience: 15,
                rating: 4.9,
                totalConsultations: 200,
                bio: "Heart specialist",
                isAvailable: true
            )
        ]
        
        // Set default doctor if editing
        if let appointment = editingAppointment {
            selectedDoctor = doctors.first { $0.id == appointment.doctorId }
        }
    }
    
    private func populateFields(from appointment: AppointmentWithDetails) {
        title = appointment.title
        description = appointment.description ?? ""
        appointmentDate = appointment.appointmentDate
        durationMinutes = appointment.durationMinutes
        appointmentType = appointment.appointmentType
        patientNotes = appointment.patientNotes ?? ""
    }
    
    private func createAppointment() {
        guard let doctor = selectedDoctor else { return }
        
        isLoading = true
        
        let appointmentCreate = AppointmentCreate(
            doctorId: doctor.id,
            consultationRequestId: nil,
            title: title,
            description: description.isEmpty ? nil : description,
            appointmentDate: appointmentDate,
            durationMinutes: durationMinutes,
            status: "scheduled",
            appointmentType: appointmentType,
            patientNotes: patientNotes.isEmpty ? nil : patientNotes
        )
        
        Task {
            do {
                _ = try await appointmentViewModel.createAppointment(appointmentCreate)
                await MainActor.run {
                    isLoading = false
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                    self.error = error.localizedDescription
                }
            }
        }
    }
    
    private func updateAppointment() {
        guard let appointment = editingAppointment else { return }
        
        isLoading = true
        
        let appointmentUpdate = AppointmentUpdate(
            title: nil,
            description: nil,
            appointmentDate: appointmentDate,
            durationMinutes: nil,
            status: nil, // Don't change status when editing
            appointmentType: nil,
            patientNotes: nil,
            doctorNotes: nil // Patients can't edit doctor notes
        )
        
        Task {
            do {
                try await appointmentViewModel.updateAppointment(id: appointment.id, update: appointmentUpdate)
                await MainActor.run {
                    isLoading = false
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                    self.error = error.localizedDescription
                }
            }
        }
    }
} 