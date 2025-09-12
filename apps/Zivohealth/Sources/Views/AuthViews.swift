import SwiftUI
import UIKit


struct PatientPasswordResetView: View {
    @State private var email: String = ""
    @State private var isSubmitting: Bool = false
    @State private var message: String?

    init(email: String = "") {
        _email = State(initialValue: email)
    }

    private var isValid: Bool { email.contains("@") && email.contains(".") }

    var body: some View {
        Form {
            Section(header: Text("Reset Password")) {
                Text("Enter your registered email. If an account exists, you will receive a password reset link.")
                    .font(.footnote)
                    .foregroundColor(.secondary)
                TextField("Email", text: $email)
                    .keyboardType(.emailAddress)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled(true)
            }

            if let message = message {
                Text(message).font(.footnote).foregroundColor(.green)
            }

            Button(action: submit) {
                HStack { if isSubmitting { ProgressView() }; Text("Send Reset Link") }
            }
            .disabled(!isValid || isSubmitting)
        }
        .navigationTitle("Forgot Password")
    }

    private func submit() {
        isSubmitting = true
        message = nil
        
        Task {
            do {
                let responseMessage = try await NetworkService.shared.requestPasswordReset(email: email)
                await MainActor.run {
                    message = responseMessage
                    isSubmitting = false
                }
            } catch {
                await MainActor.run {
                    message = "Failed to send reset link. Please try again."
                    isSubmitting = false
                }
            }
        }
    }
}


