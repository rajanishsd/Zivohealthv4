import SwiftUI

struct ConsultationOptionsView: View {
    @Environment(\.presentationMode) var presentationMode
    @State private var showingVideoConsultation = false
    @State private var showingScheduleConsultation = false

    var body: some View {
        NavigationView {
            VStack(spacing: 24) {
                // Header
                VStack(spacing: 12) {
                    Image(systemName: "heart.text.square")
                        .font(.system(size: 60))
                        .foregroundColor(.blue)

                    Text("Choose Consultation Type")
                        .font(.title2)
                        .fontWeight(.semibold)

                    Text("Select how you'd like to consult with our healthcare professionals")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                }
                .padding(.top, 20)

                // Options
                VStack(spacing: 16) {
                    // Option 1: Video Consultation Now
                    ConsultationOptionCard(
                        icon: "video.circle.fill",
                        title: "Online Video Consultation",
                        subtitle: "Connect with available doctors now",
                        description: "Get immediate medical consultation via video call with our available doctors",
                        color: .green,
                        badge: "IMMEDIATE"
                    ) {
                        showingVideoConsultation = true
                    }

                    // Option 2: Schedule Consultation
                    ConsultationOptionCard(
                        icon: "calendar.circle.fill",
                        title: "Schedule Consultation",
                        subtitle: "Book online or hospital visit",
                        description: "Schedule a consultation at your preferred time, online or at our facilities",
                        color: .blue,
                        badge: "SCHEDULE"
                    ) {
                        showingScheduleConsultation = true
                    }
                }
                .padding(.horizontal)

                Spacer()
            }
            .navigationTitle("Consultation")
            .navigationBarItems(leading:
                Button("Cancel") {
                    presentationMode.wrappedValue.dismiss()
                }
            )
        }
        .sheet(isPresented: $showingVideoConsultation) {
            // Doctor app: present direct video call screen with placeholder doctor
            VideoCallView(doctor: Doctor(
                id: -1,
                fullName: "Current Doctor",
                specialization: "General Medicine",
                yearsExperience: 5,
                rating: 4.5,
                totalConsultations: 100,
                bio: "",
                isAvailable: true
            ))
        }
        .sheet(isPresented: $showingScheduleConsultation) {
            // Doctor app: use appointments screen for scheduling
            AppointmentsView()
        }
    }
}

struct ConsultationOptionCard: View {
    let icon: String
    let title: String
    let subtitle: String
    let description: String
    let color: Color
    let badge: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 16) {
                // Header with icon and badge
                HStack {
                    Image(systemName: icon)
                        .font(.system(size: 32))
                        .foregroundColor(color)

                    Spacer()

                    Text(badge)
                        .font(.caption)
                        .fontWeight(.semibold)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(color.opacity(0.2))
                        .foregroundColor(color)
                        .cornerRadius(8)
                }

                // Content
                VStack(alignment: .leading, spacing: 8) {
                    Text(title)
                        .font(.headline)
                        .fontWeight(.semibold)
                        .foregroundColor(.primary)

                    Text(subtitle)
                        .font(.subheadline)
                        .foregroundColor(color)
                        .fontWeight(.medium)

                    Text(description)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(3)
                }

                // Action indicator
                HStack {
                    Spacer()
                    Image(systemName: "arrow.right.circle")
                        .foregroundColor(color)
                        .font(.title3)
                }
            }
            .padding(20)
            .background(Color(UIColor.systemBackground))
            .cornerRadius(16)
            .shadow(color: Color.black.opacity(0.1), radius: 8, x: 0, y: 4)
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(color.opacity(0.3), lineWidth: 1)
            )
        }
        .buttonStyle(PlainButtonStyle())
    }
}

#Preview {
    ConsultationOptionsView()
}
