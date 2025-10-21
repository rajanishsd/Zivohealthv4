import SwiftUI

struct AppointmentsView: View {
    @ObservedObject private var appointmentViewModel = AppointmentViewModel.shared
    @State private var showingCreateAppointment = false
    @State private var showingConsultationOptions = false
    @State private var selectedAppointment: AppointmentWithDetails?
    @State private var selectedTab = 0
    
    var body: some View {
        GeometryReader { geometry in
            VStack(spacing: 0) {
                // Reserve space equal to the visible header height (excluding status bar)
                Color.clear.frame(height: 220)

                // Custom Tab Selector
                HStack(spacing: 0) {
                    Button(action: { selectedTab = 0 }) {
                        Text("Upcoming")
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundColor(selectedTab == 0 ? .white : .gray)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 6)
                            .background(selectedTab == 0 ? Color.zivoRed : Color.clear)
                    }
                    
                    Button(action: { selectedTab = 1 }) {
                        Text("History")
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundColor(selectedTab == 1 ? .white : .gray)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 6)
                            .background(selectedTab == 1 ? Color.zivoRed : Color.clear)
                    }
                }
                .background(Color(.systemGray6))
                .cornerRadius(8)
                .padding(.horizontal, 16)
                .padding(.vertical, 4)
                
                // Content based on selected tab
                if selectedTab == 0 {
                    upcomingTab
                } else {
                    historyTab
                }
            }
            .frame(width: geometry.size.width)
            // Draw the header at the very top, extending under the status bar
            .overlay(alignment: .top) {
                headerCard(topInset: geometry.safeAreaInsets.top)
            }
            .ignoresSafeArea(.container, edges: .top)
        }
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .navigationBarHidden(true)
        .sheet(isPresented: $showingCreateAppointment) {
            CreateAppointmentView(
                appointmentViewModel: appointmentViewModel,
                editingAppointment: selectedAppointment
            )
        }
        .sheet(isPresented: $showingConsultationOptions, onDismiss: {
            // Refresh appointments when consultation sheet is dismissed
            appointmentViewModel.refreshAppointments()
        }) {
            ConsultationOptionsView()
        }
        .sheet(item: $selectedAppointment) { appointment in
            AppointmentDetailView(appointment: appointment, appointmentViewModel: appointmentViewModel)
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
    
    // MARK: - Header
    private var brandRedGradient: Gradient {
        // Left-to-right gradient with darker left side
        Gradient(colors: [
            Color.zivoRed,                 // darker (left)
            Color.zivoRed.opacity(0.7)     // lighter (right)
        ])
    }
    
    private func headerCard(topInset: CGFloat) -> some View {
        VStack(spacing: 0) {
            // Top spacer for status bar
            Color.clear
                .frame(height: topInset)
            
            // Card content
            ZStack(alignment: .bottomLeading) {
                LinearGradient(gradient: brandRedGradient, startPoint: .leading, endPoint: .trailing)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)

                HStack {
                    Text("Appointments")
                        .font(.title2).bold()
                        .foregroundColor(.white)
                    
                    Spacer()
                    
                    // Consultation button with label
                    Button(action: {
                        showingConsultationOptions = true
                    }) {
                        VStack(spacing: 6) {
                            Image(systemName: "person.circle.fill")
                                .font(.title2)
                                .foregroundColor(.white)
                                .frame(width: 44, height: 44)
                                .background(Color.white.opacity(0.2))
                                .clipShape(Circle())
                            
                            Text("Book Now")
                                .font(.caption)
                                .fontWeight(.medium)
                                .foregroundColor(.white)
                        }
                    }
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 20)
            }
            .frame(height: 140)
            .cornerRadius(20)
            .padding(.horizontal, 16)
            .padding(.top, 8)
        }
        .frame(height: 140 + topInset + 8)
        .ignoresSafeArea(.container, edges: .top)
    }
    
    // MARK: - Tabs
    private var upcomingTab: some View {
        VStack {
            if appointmentViewModel.isLoading {
                ProgressView("Loading appointments...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                let upcomingAppointments = appointmentViewModel.upcomingAppointments()
                if upcomingAppointments.isEmpty {
                    // Empty state for upcoming
                    VStack(spacing: 24) {
                        Spacer()
                        
                        Image(systemName: "calendar.badge.plus")
                            .font(.system(size: 64))
                            .foregroundColor(.blue.opacity(0.6))
                        
                        VStack(spacing: 8) {
                            Text("No Upcoming Appointments")
                                .font(.title2)
                                .fontWeight(.semibold)
                            
                            Text("Your upcoming appointments will appear here")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                        }
                        
                        Spacer()
                    }
                    .padding()
                } else {
                    List {
                        ForEach(upcomingAppointments) { appointment in
                            AppointmentRow(appointment: appointment)
                                .onTapGesture {
                                    selectedAppointment = appointment
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
                                .listRowSeparator(.hidden)
                        }
                    }
                    .listStyle(PlainListStyle())
                    .background(Color.white)
                    .refreshable {
                        appointmentViewModel.refreshAppointments()
                    }
                }
            }
        }
    }
    
    private var historyTab: some View {
        VStack {
            if appointmentViewModel.isLoading {
                ProgressView("Loading appointments...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                let pastAppointments = appointmentViewModel.pastAppointments()
                let cancelledAppointments = appointmentViewModel.cancelledAppointments()
                let allHistoryAppointments = pastAppointments + cancelledAppointments
                
                if allHistoryAppointments.isEmpty {
                    // Empty state for history
                    VStack(spacing: 24) {
                        Spacer()
                        
                        Image(systemName: "clock.arrow.circlepath")
                            .font(.system(size: 64))
                            .foregroundColor(.gray.opacity(0.6))
                        
                        VStack(spacing: 8) {
                            Text("No Past Appointments")
                                .font(.title2)
                                .fontWeight(.semibold)
                            
                            Text("Your appointment history will appear here")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                        }
                        
                        Spacer()
                    }
                    .padding()
                } else {
                    List {
                        ForEach(allHistoryAppointments) { appointment in
                            AppointmentRow(appointment: appointment)
                                .onTapGesture {
                                    selectedAppointment = appointment
                                }
                                .listRowSeparator(.hidden)
                        }
                    }
                    .listStyle(PlainListStyle())
                    .background(Color.white)
                    .refreshable {
                        appointmentViewModel.refreshAppointments()
                    }
                }
            }
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
        HStack(spacing: 16) {
            // Left side - Doctor info
            VStack(alignment: .leading, spacing: 8) {
                Text(appointment.doctorName)
                    .font(.headline)
                    .fontWeight(.semibold)
                    .foregroundColor(.primary)
                
                Text("General Practitioner")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                VStack(alignment: .leading, spacing: 4) {
                    Label(
                        appointment.appointmentDate.formatted(date: .abbreviated, time: .shortened),
                        systemImage: "calendar"
                    )
                    .font(.caption)
                    .foregroundColor(.secondary)
                    
                    Label(
                        appointment.appointmentType.capitalized.replacingOccurrences(of: "_", with: " "),
                        systemImage: "video"
                    )
                    .font(.caption)
                    .foregroundColor(.blue)
                }
            }
            
            Spacer()
            
            // Right side - Status
            VStack(alignment: .trailing, spacing: 4) {
                StatusBadge(status: appointment.status)
                
                Text("\(appointment.durationMinutes) min")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding(16)
        .background(Color.white)
        .cornerRadius(12)
        .shadow(color: .gray.opacity(0.2), radius: 8, x: 0, y: 4)
    }
}

// Custom shape for bottom rounded corners only
struct BottomRoundedRectangle: Shape {
    let cornerRadius: CGFloat
    
    func path(in rect: CGRect) -> Path {
        var path = Path()
        
        // Start from top-left (no rounding)
        path.move(to: CGPoint(x: 0, y: 0))
        
        // Top edge (no rounding)
        path.addLine(to: CGPoint(x: rect.width, y: 0))
        
        // Top-right corner (no rounding)
        path.addLine(to: CGPoint(x: rect.width, y: rect.height - cornerRadius))
        
        // Bottom-right corner (rounded)
        path.addQuadCurve(
            to: CGPoint(x: rect.width - cornerRadius, y: rect.height),
            control: CGPoint(x: rect.width, y: rect.height)
        )
        
        // Bottom edge
        path.addLine(to: CGPoint(x: cornerRadius, y: rect.height))
        
        // Bottom-left corner (rounded)
        path.addQuadCurve(
            to: CGPoint(x: 0, y: rect.height - cornerRadius),
            control: CGPoint(x: 0, y: rect.height)
        )
        
        // Left edge (no rounding)
        path.addLine(to: CGPoint(x: 0, y: 0))
        
        return path
    }
} 