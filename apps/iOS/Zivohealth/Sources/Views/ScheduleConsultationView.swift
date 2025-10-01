import SwiftUI

struct ScheduleConsultationView: View {
    @Environment(\.presentationMode) var presentationMode
    @StateObject private var viewModel = ScheduleConsultationViewModel()

    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Progress indicator
                ProgressIndicator(currentStep: viewModel.currentStep)
                    .padding()

                // Content based on current step
                ScrollView {
                    VStack(spacing: 20) {
                        switch viewModel.currentStep {
                        case .consultationType:
                            ConsultationTypeSelectionView(viewModel: viewModel)
                        case .doctorSelection:
                            DoctorSelectionStepView(viewModel: viewModel)
                        case .timeSlot:
                            TimeSlotSelectionView(viewModel: viewModel)
                        case .confirmation:
                            ConfirmationView(viewModel: viewModel)
                        }
                    }
                    .padding()
                }

                // Navigation buttons
                HStack(spacing: 16) {
                    if viewModel.currentStep != .consultationType {
                        Button("Back") {
                            viewModel.goBack()
                        }
                        .font(.subheadline.weight(.medium))
                        .foregroundColor(.blue)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.blue.opacity(0.1))
                        .cornerRadius(12)
                    }

                    Button(viewModel.nextButtonTitle) {
                        if viewModel.currentStep == .confirmation {
                            // Schedule and dismiss
                            Task {
                                do {
                                    try await viewModel.scheduleAppointment()
                                    presentationMode.wrappedValue.dismiss()
                                } catch {
                                    print("❌ [ScheduleConsultation] Error scheduling appointment: \(error)")
                                }
                            }
                        } else {
                            viewModel.goNext()
                        }
                    }
                    .font(.subheadline.weight(.medium))
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background((viewModel.canProceed && !viewModel.isCreatingAppointment) ? Color.blue : Color.gray)
                    .cornerRadius(12)
                    .disabled(!viewModel.canProceed || viewModel.isCreatingAppointment)
                    .overlay(
                        Group {
                            if viewModel.isCreatingAppointment {
                                HStack(spacing: 8) {
                                    ProgressView()
                                        .scaleEffect(0.8)
                                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                                    Text("Creating...")
                                        .font(.subheadline.weight(.medium))
                                        .foregroundColor(.white)
                                }
                            }
                        }
                    )
                }
                .padding()
            }
            .navigationTitle("Schedule Consultation")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") {
                        presentationMode.wrappedValue.dismiss()
                    }
                }
            }
        }
        .onAppear {
            viewModel.loadDoctors()
        }
        .alert("Error Creating Appointment", isPresented: .constant(viewModel.appointmentError != nil)) {
            Button("OK") {
                viewModel.appointmentError = nil
            }
        } message: {
            Text(viewModel.appointmentError ?? "")
        }
    }
}

// MARK: - Step Views

struct ConsultationTypeSelectionView: View {
    @ObservedObject var viewModel: ScheduleConsultationViewModel

    var body: some View {
        VStack(spacing: 24) {
            VStack(spacing: 12) {
                Image(systemName: "calendar.badge.plus")
                    .font(.system(size: 50))
                    .foregroundColor(.blue)

                Text("Choose Consultation Type")
                    .font(.title2.weight(.semibold))

                Text("Select how you'd like to have your consultation")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }

            VStack(spacing: 16) {
                ConsultationTypeCard(
                    icon: "video.circle.fill",
                    title: "Online Consultation",
                    subtitle: "Video call with doctor",
                    features: ["Video/Audio call", "Digital prescription", "Instant connection"],
                    isSelected: viewModel.selectedConsultationType == .online
                ) {
                    viewModel.selectedConsultationType = .online
                }

                ConsultationTypeCard(
                    icon: "building.2.fill",
                    title: "Hospital Visit",
                    subtitle: "In-person consultation",
                    features: ["Face-to-face consultation", "Physical examination", "Lab tests available"],
                    isSelected: viewModel.selectedConsultationType == .hospital
                ) {
                    viewModel.selectedConsultationType = .hospital
                }
            }
        }
    }
}

struct ConsultationTypeCard: View {
    let icon: String
    let title: String
    let subtitle: String
    let features: [String]
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Image(systemName: icon)
                        .font(.title2)
                        .foregroundColor(isSelected ? .blue : .gray)

                    VStack(alignment: .leading, spacing: 4) {
                        Text(title)
                            .font(.headline.weight(.semibold))
                            .foregroundColor(.primary)

                        Text(subtitle)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }

                    Spacer()

                    Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                        .font(.title3)
                        .foregroundColor(isSelected ? .blue : .gray)
                }

                VStack(alignment: .leading, spacing: 8) {
                    ForEach(features, id: \.self) { feature in
                        HStack(spacing: 8) {
                            Image(systemName: "checkmark")
                                .font(.caption)
                                .foregroundColor(.green)

                            Text(feature)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }
            }
            .padding()
            .background(Color(UIColor.systemBackground))
            .cornerRadius(12)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? Color.blue : Color.gray.opacity(0.3), lineWidth: isSelected ? 2 : 1)
            )
        }
        .buttonStyle(PlainButtonStyle())
    }
}

struct DoctorSelectionStepView: View {
    @ObservedObject var viewModel: ScheduleConsultationViewModel

    var body: some View {
        VStack(spacing: 20) {
            VStack(spacing: 12) {
                Image(systemName: "person.2.circle")
                    .font(.system(size: 50))
                    .foregroundColor(.blue)

                Text("Select Doctor")
                    .font(.title2.weight(.semibold))

                Text("Choose a doctor for your \(viewModel.selectedConsultationType?.displayName ?? "") consultation")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }

            if viewModel.isLoadingDoctors {
                VStack(spacing: 12) {
                    ProgressView()
                    Text("Loading doctors...")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding()
            } else {
                LazyVStack(spacing: 12) {
                    ForEach(viewModel.availableDoctors) { doctor in
                        ScheduleDoctorCard(
                            doctor: doctor,
                            consultationType: viewModel.selectedConsultationType ?? .online,
                            isSelected: viewModel.selectedDoctor?.id == doctor.id
                        ) {
                            viewModel.selectedDoctor = doctor
                        }
                    }
                }
            }
        }
    }
}

struct ScheduleDoctorCard: View {
    let doctor: Doctor
    let consultationType: ConsultationType
    let isSelected: Bool
    let onSelect: () -> Void

    var body: some View {
        Button(action: onSelect) {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    // Doctor avatar
                    ZStack {
                        Circle()
                            .fill(Color.blue.opacity(0.2))
                            .frame(width: 60, height: 60)

                        Text(doctor.fullName.prefix(2).uppercased())
                            .font(.headline.weight(.semibold))
                            .foregroundColor(.blue)
                    }

                    // Doctor info
                    VStack(alignment: .leading, spacing: 4) {
                        Text(doctor.fullName)
                            .font(.headline.weight(.semibold))
                            .foregroundColor(.primary)

                        Text(doctor.specialization)
                            .font(.subheadline.weight(.semibold))
                            .foregroundColor(.blue)

                        HStack(spacing: 12) {
                            Label("\(String(format: "%.1f", doctor.rating))", systemImage: "star.fill")
                                .font(.caption)
                                .foregroundColor(.orange)

                            Label("\(doctor.yearsExperience) yrs", systemImage: "clock")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }

                    Spacer()

                    Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                        .font(.title3)
                        .foregroundColor(isSelected ? .blue : .gray)
                }

                // Availability info
                if consultationType == .online {
                    Text("Available for online consultation")
                        .font(.caption)
                        .foregroundColor(.green)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.green.opacity(0.1))
                        .cornerRadius(6)
                } else {
                    Text("Available at ZivoHealth Medical Center")
                        .font(.caption)
                        .foregroundColor(.blue)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.blue.opacity(0.1))
                        .cornerRadius(6)
                }
            }
            .padding()
            .background(Color(UIColor.systemBackground))
            .cornerRadius(12)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? Color.blue : Color.gray.opacity(0.3), lineWidth: isSelected ? 2 : 1)
            )
        }
        .buttonStyle(PlainButtonStyle())
    }
}

struct TimeSlotSelectionView: View {
    @ObservedObject var viewModel: ScheduleConsultationViewModel

    var body: some View {
        VStack(spacing: 20) {
            VStack(spacing: 12) {
                Image(systemName: "calendar.circle")
                    .font(.system(size: 50))
                    .foregroundColor(.blue)

                Text("Select Date & Time")
                    .font(.title2.weight(.semibold))

                Text("Choose your preferred appointment time")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }

            // Date picker
            VStack(alignment: .leading, spacing: 12) {
                Text("Select Date")
                    .font(.headline.weight(.medium))

                DatePicker(
                    "Appointment Date",
                    selection: $viewModel.selectedDate,
                    in: Date()...,
                    displayedComponents: .date
                )
                .datePickerStyle(GraphicalDatePickerStyle())
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(12)
            }

            // Time slots
            VStack(alignment: .leading, spacing: 12) {
                Text("Available Times")
                    .font(.headline.weight(.medium))

                LazyVGrid(columns: [
                    GridItem(.flexible()),
                    GridItem(.flexible()),
                    GridItem(.flexible()),
                ], spacing: 12) {
                    ForEach(viewModel.availableTimeSlots, id: \.self) { timeSlot in
                        TimeSlotButton(
                            timeSlot: timeSlot,
                            isSelected: viewModel.selectedTimeSlot == timeSlot
                        ) {
                            viewModel.selectedTimeSlot = timeSlot
                        }
                    }
                }
            }
        }
        .onChange(of: viewModel.selectedDate) { _ in
            viewModel.loadTimeSlots()
        }
        .onAppear {
            viewModel.loadTimeSlots()
        }
    }
}

struct TimeSlotButton: View {
    let timeSlot: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(timeSlot)
                .font(.subheadline.weight(.medium))
                .foregroundColor(isSelected ? .white : .primary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(isSelected ? Color.blue : Color(.systemGray6))
                .cornerRadius(8)
        }
        .buttonStyle(PlainButtonStyle())
    }
}

struct ConfirmationView: View {
    @ObservedObject var viewModel: ScheduleConsultationViewModel

    var body: some View {
        VStack(spacing: 24) {
            VStack(spacing: 12) {
                Image(systemName: "checkmark.circle")
                    .font(.system(size: 50))
                    .foregroundColor(.green)

                Text("Confirm Appointment")
                    .font(.title2.weight(.semibold))

                Text("Please review your appointment details")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }

            // Appointment summary
            VStack(spacing: 16) {
                AppointmentDetailRow(
                    icon: "person.circle",
                    title: "Doctor",
                    value: viewModel.selectedDoctor?.fullName ?? ""
                )

                AppointmentDetailRow(
                    icon: "stethoscope",
                    title: "Specialization",
                    value: viewModel.selectedDoctor?.specialization ?? ""
                )

                AppointmentDetailRow(
                    icon: viewModel.selectedConsultationType == .online ? "video.circle" : "building.2",
                    title: "Type",
                    value: viewModel.selectedConsultationType?.displayName ?? ""
                )

                AppointmentDetailRow(
                    icon: "calendar",
                    title: "Date",
                    value: viewModel.selectedDate.formatted(date: .complete, time: .omitted)
                )

                AppointmentDetailRow(
                    icon: "clock",
                    title: "Time",
                    value: viewModel.selectedTimeSlot ?? ""
                )

                if viewModel.selectedConsultationType == .hospital {
                    AppointmentDetailRow(
                        icon: "location",
                        title: "Location",
                        value: "ZivoHealth Medical Center\n123 Health Street, Medical District"
                    )
                }
            }
            .padding()
            .background(Color(UIColor.systemBackground))
            .cornerRadius(12)

            // Important notes
            VStack(alignment: .leading, spacing: 8) {
                Text("Important Notes:")
                    .font(.subheadline.weight(.semibold))

                if viewModel.selectedConsultationType == .online {
                    Text("• Ensure you have a stable internet connection")
                    Text("• Join the call 5 minutes before your appointment")
                    Text("• Have your medical history ready")
                } else {
                    Text("• Arrive 15 minutes before your appointment")
                    Text("• Bring a valid ID and insurance card")
                    Text("• Fasting may be required for certain tests")
                }
            }
            .font(.caption)
            .foregroundColor(.secondary)
            .padding()
            .background(Color.blue.opacity(0.1))
            .cornerRadius(8)
        }
    }
}

struct AppointmentDetailRow: View {
    let icon: String
    let title: String
    let value: String

    var body: some View {
        HStack {
            Image(systemName: icon)
                .font(.subheadline)
                .foregroundColor(.blue)
                .frame(width: 20)

            Text(title)
                .font(.subheadline.weight(.medium))
                .frame(width: 100, alignment: .leading)

            Text(value)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.leading)

            Spacer()
        }
    }
}

struct ProgressIndicator: View {
    let currentStep: SchedulingStep

    var body: some View {
        HStack(spacing: 8) {
            ForEach(SchedulingStep.allCases, id: \.self) { step in
                HStack(spacing: 8) {
                    Circle()
                        .fill(step.rawValue <= currentStep.rawValue ? Color.blue : Color.gray.opacity(0.3))
                        .frame(width: 12, height: 12)

                    if step != SchedulingStep.allCases.last {
                        Rectangle()
                            .fill(step.rawValue < currentStep.rawValue ? Color.blue : Color.gray.opacity(0.3))
                            .frame(height: 2)
                            .frame(maxWidth: .infinity)
                    }
                }
            }
        }
    }
}

// MARK: - View Model and Types

enum SchedulingStep: Int, CaseIterable {
    case consultationType = 0
    case doctorSelection = 1
    case timeSlot = 2
    case confirmation = 3
}

enum ConsultationType: CaseIterable {
    case online
    case hospital

    var displayName: String {
        switch self {
        case .online: return "Online Consultation"
        case .hospital: return "Hospital Visit"
        }
    }
}

@MainActor
class ScheduleConsultationViewModel: ObservableObject {
    @Published var currentStep: SchedulingStep = .consultationType
    @Published var selectedConsultationType: ConsultationType?
    @Published var selectedDoctor: Doctor?
    @Published var selectedDate = Date()
    @Published var selectedTimeSlot: String?
    @Published var availableDoctors: [Doctor] = []
    @Published var availableTimeSlots: [String] = []
    @Published var isLoadingDoctors = false
    @Published var isCreatingAppointment = false
    @Published var appointmentError: String?

    private let networkService = NetworkService.shared
    private let appointmentViewModel = AppointmentViewModel.shared

    var canProceed: Bool {
        switch currentStep {
        case .consultationType:
            return selectedConsultationType != nil
        case .doctorSelection:
            return selectedDoctor != nil
        case .timeSlot:
            return selectedTimeSlot != nil
        case .confirmation:
            return true
        }
    }

    var nextButtonTitle: String {
        switch currentStep {
        case .consultationType, .doctorSelection, .timeSlot:
            return "Next"
        case .confirmation:
            return "Schedule Appointment"
        }
    }

    func goNext() {
        guard canProceed else { return }

        if let nextStep = SchedulingStep(rawValue: currentStep.rawValue + 1) {
            currentStep = nextStep
        }
    }

    func goBack() {
        if let previousStep = SchedulingStep(rawValue: currentStep.rawValue - 1) {
            currentStep = previousStep
        }
    }

    func loadDoctors() {
        isLoadingDoctors = true

        Task {
            do {
                let doctors = try await networkService.findDoctorsByContext("general consultation available")

                await MainActor.run {
                    self.availableDoctors = doctors
                    self.isLoadingDoctors = false
                }
            } catch {
                await MainActor.run {
                    self.isLoadingDoctors = false
                    print("❌ [ScheduleConsultation] Error loading doctors: \(error)")
                }
            }
        }
    }

    func loadTimeSlots() {
        // Generate sample time slots for the selected date
        let timeSlots = [
            "09:00 AM", "09:30 AM", "10:00 AM", "10:30 AM",
            "11:00 AM", "11:30 AM", "02:00 PM", "02:30 PM",
            "03:00 PM", "03:30 PM", "04:00 PM", "04:30 PM",
        ]

        // Simulate some slots being unavailable
        availableTimeSlots = Array(timeSlots.shuffled().prefix(8))
    }

    func scheduleAppointment() async throws {
        guard let doctor = selectedDoctor,
              let consultationType = selectedConsultationType,
              let timeSlot = selectedTimeSlot else {
            throw NSError(domain: "ScheduleConsultation", code: 1, userInfo: [NSLocalizedDescriptionKey: "Missing required appointment details"])
        }
        
        isCreatingAppointment = true
        appointmentError = nil
        
        print("📅 [ScheduleConsultation] Scheduling appointment:")
        print("   Doctor: \(doctor.fullName)")
        print("   Type: \(consultationType.displayName)")
        print("   Date: \(selectedDate)")
        print("   Time: \(timeSlot)")

        do {
            // Create the appointment date by combining selected date and time
            let appointmentDate = createAppointmentDateTime(date: selectedDate, timeSlot: timeSlot)
            
            let appointmentCreate = AppointmentCreate(
                doctorId: doctor.id,
                consultationRequestId: nil,
                title: "\(consultationType.displayName) with Dr. \(doctor.fullName)",
                description: "Scheduled \(consultationType.displayName.lowercased()) appointment",
                appointmentDate: appointmentDate,
                durationMinutes: 30,
                status: "scheduled",
                appointmentType: consultationType == .online ? "online_consultation" : "hospital_visit",
                patientNotes: nil
            )
            
            // Create the appointment via AppointmentViewModel
            let createdAppointment = try await appointmentViewModel.createAppointment(appointmentCreate)
            
            await MainActor.run {
                self.isCreatingAppointment = false
                print("✅ [ScheduleConsultation] Appointment created successfully with ID: \(createdAppointment.id)")
            }
            
        } catch {
            await MainActor.run {
                self.isCreatingAppointment = false
                self.appointmentError = error.localizedDescription
                print("❌ [ScheduleConsultation] Error creating appointment: \(error)")
            }
            throw error
        }
    }
    
    private func createAppointmentDateTime(date: Date, timeSlot: String) -> Date {
        let calendar = Calendar.current
        var components = calendar.dateComponents([.year, .month, .day], from: date)
        
        // Parse time slot (e.g., "02:30 PM")
        let timeFormatter = DateFormatter()
        timeFormatter.dateFormat = "hh:mm a"
        
        if let timeDate = timeFormatter.date(from: timeSlot) {
            let timeComponents = calendar.dateComponents([.hour, .minute], from: timeDate)
            components.hour = timeComponents.hour
            components.minute = timeComponents.minute
        }
        
        return calendar.date(from: components) ?? date
    }

    private func saveToUpcomingConsultations() {
        // This method is no longer needed as we're creating real appointments
        print("💾 [ScheduleConsultation] Appointment saved to database")
    }
}

#Preview {
    ScheduleConsultationView()
}
