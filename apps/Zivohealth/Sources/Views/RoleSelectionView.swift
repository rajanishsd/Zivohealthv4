import SwiftUI

struct RoleSelectionView: View {
    @AppStorage("userMode") private var userMode: UserMode = .patient
    @AppStorage("hasSelectedRole") private var hasSelectedRole = false

    @State private var selectedRole: UserMode = .patient

    var body: some View {
        ZStack {
            // Background gradient
            LinearGradient(
                gradient: Gradient(colors: [Color.blue.opacity(0.1), Color.purple.opacity(0.1)]),
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            VStack(spacing: 40) {
                Spacer()

                // App Logo and Title
                VStack(spacing: 16) {
                    Image(systemName: "heart.circle.fill")
                        .font(.system(size: 80))
                        .foregroundColor(.blue)

                    Text("ZivoHealth")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                        .foregroundColor(.primary)

                    Text("Smart Healthcare Platform")
                        .font(.title3)
                        .foregroundColor(.secondary)
                }

                Spacer()

                // Role Selection Cards
                VStack(spacing: 20) {
                    Text("Choose Your Role")
                        .font(.title2)
                        .fontWeight(.semibold)
                        .padding(.bottom, 10)

                    // Patient Role Card
                    RoleCard(
                        role: .patient,
                        title: "Patient",
                        subtitle: "Access healthcare services",
                        icon: "person.circle.fill",
                        description: "Chat with AI, consult healthcare professionals, and manage your health",
                        isSelected: selectedRole == .patient
                    ) {
                        selectedRole = .patient
                    }

                    // Doctor Role Card
                    RoleCard(
                        role: .doctor,
                        title: "Healthcare Professional",
                        subtitle: "Manage patient consultations",
                        icon: "stethoscope.circle.fill",
                        description: "Review consultation requests, manage patient cases, and provide care",
                        isSelected: selectedRole == .doctor
                    ) {
                        selectedRole = .doctor
                    }
                }

                Spacer()

                // Continue Button
                Button(action: {
                    userMode = selectedRole
                    hasSelectedRole = true

                    // Clear auth token when role changes
                    NetworkService.shared.handleRoleChange()
                }) {
                    HStack {
                        Text("Continue as \(selectedRole == .patient ? "Patient" : "Healthcare Professional")")
                        Image(systemName: "arrow.right")
                    }
                    .font(.headline)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.blue)
                    .cornerRadius(12)
                }
                .padding(.horizontal, 40)

                Spacer()
            }
            .padding()
        }
    }
}

struct RoleCard: View {
    let role: UserMode
    let title: String
    let subtitle: String
    let icon: String
    let description: String
    let isSelected: Bool
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 16) {
                // Icon
                Image(systemName: icon)
                    .font(.system(size: 40))
                    .foregroundColor(isSelected ? .white : .blue)
                    .frame(width: 60, height: 60)

                // Content
                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.headline)
                        .foregroundColor(isSelected ? .white : .primary)

                    Text(subtitle)
                        .font(.subheadline)
                        .foregroundColor(isSelected ? .white.opacity(0.8) : .secondary)

                    Text(description)
                        .font(.caption)
                        .foregroundColor(isSelected ? .white.opacity(0.7) : .secondary)
                        .multilineTextAlignment(.leading)
                        .lineLimit(2)
                }

                Spacer()

                // Selection indicator
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.title2)
                    .foregroundColor(isSelected ? .white : .gray)
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(isSelected ? Color.blue : Color.gray.opacity(0.1))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? Color.blue : Color.gray.opacity(0.3), lineWidth: 1)
            )
        }
        .buttonStyle(PlainButtonStyle())
    }
}

#Preview {
    RoleSelectionView()
}
