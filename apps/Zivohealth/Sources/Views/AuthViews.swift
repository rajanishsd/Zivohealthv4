import SwiftUI
import UIKit

struct PatientLoginView: View {
    @AppStorage("userMode") private var userMode: UserMode = .patient
    @AppStorage("patientAuthToken") private var patientAuthToken: String = ""
    @State private var email: String = ""
    @State private var password: String = ""
    @State private var isLoading: Bool = false
    @State private var error: String?
    @State private var showPassword: Bool = false
    @FocusState private var focusedField: Field?

    var onSuccess: () -> Void

    private enum Field { case email, password }

    private var isValid: Bool {
        let hasAt = email.contains("@") && email.contains(".")
        return hasAt && !password.isEmpty
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                VStack(spacing: 12) {
                    if UIImage(named: "ZivoDocLogo") != nil {
                        Image("ZivoDocLogo")
                            .resizable()
                            .scaledToFit()
                            .frame(height: 140)
                            .accessibilityHidden(true)
                    } else {
                        Text("zivo")
                            .font(.system(size: 100, weight: .bold))
                            .foregroundColor(.zivoRed)
                            .accessibilityLabel("Zivo logo")
                    }

                    Text("Welcome Back")
                        .font(.system(size: 26, weight: .bold))
                        .foregroundColor(.zivoRed)
                        .frame(maxWidth: .infinity, alignment: .center)
                }
                .frame(maxWidth: .infinity)
                .padding(.top, 8)

                if let error = error {
                    HStack(spacing: 12) {
                        Image(systemName: "exclamationmark.triangle.fill").foregroundColor(.white)
                        Text(error).foregroundColor(.white).font(.subheadline)
                    }
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.red)
                    .cornerRadius(12)
                }

                VStack(spacing: 16) {
                    Text("Email").font(.headline).frame(maxWidth: .infinity, alignment: .leading)
                    TextField("Enter your email", text: $email)
                        .keyboardType(.emailAddress)
                        .textContentType(.username)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled(true)
                        .padding(14)
                        .background(Color.white)
                        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(.systemGray4), lineWidth: 1))
                        .cornerRadius(12)
                        .focused($focusedField, equals: .email)
                        .submitLabel(.next)
                        .onSubmit { focusedField = .password }

                    Text("Password").font(.headline).frame(maxWidth: .infinity, alignment: .leading)
                    HStack {
                        Group {
                            if showPassword {
                                TextField("Enter your password", text: $password)
                                    .textContentType(.password)
                                    .textInputAutocapitalization(.never)
                                    .autocorrectionDisabled(true)
                            } else {
                                SecureField("Enter your password", text: $password)
                                    .textContentType(.password)
                            }
                        }
                        .focused($focusedField, equals: .password)
                        .submitLabel(.go)
                        .onSubmit { if isValid { submit() } }

                        Button(action: { showPassword.toggle() }) {
                            Image(systemName: showPassword ? "eye.slash" : "eye").foregroundColor(.secondary)
                        }
                    }
                    .padding(14)
                    .background(Color.white)
                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(.systemGray4), lineWidth: 1))
                    .cornerRadius(12)
                }

                VStack(spacing: 12) {
                    Button(action: submit) {
                        HStack { if isLoading { ProgressView().tint(.white) }; Text("Log In").fontWeight(.semibold) }
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.zivoRed)
                    .controlSize(.regular)
                    .disabled(!isValid || isLoading)

                    // Debug button to force endpoint update
                    Button(action: {
                        NetworkService.shared.forceUpdateEndpoint()
                        NetworkService.shared.debugAuthenticationState()
                    }) {
                        Text("🔄 Force Local Endpoint")
                            .font(.caption)
                            .foregroundColor(.blue)
                    }

                    HStack(spacing: 16) {
                        NavigationLink("Forgot Password?") { PatientPasswordResetView() }
                        Text("|").foregroundColor(.secondary)
                        NavigationLink("Sign Up") { PatientRegistrationView { onSuccess() } }
                    }
                    .font(.footnote)
                    .tint(.zivoRed)
                    .frame(maxWidth: .infinity)
                }

                Divider().padding(.vertical, 4)
            }
            .padding()
        }
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .modifier(HideNavBarCompat())
        .background(Color.white)
    }

    private struct HideNavBarCompat: ViewModifier {
        func body(content: Content) -> some View {
            if #available(iOS 16.0, *) { content.toolbar(.hidden, for: .navigationBar) } else { content.navigationBarHidden(true) }
        }
    }

    private func submit() {
        error = nil
        isLoading = true
        Task {
            do {
                userMode = .patient
                NetworkService.shared.handleRoleChange()
                _ = try await NetworkService.shared.login(email: email, password: password)
                onSuccess()
            } catch {
                self.error = "Login failed. Please check credentials."
            }
            isLoading = false
        }
    }
}

struct PatientRegistrationView: View {
    @AppStorage("userMode") private var userMode: UserMode = .patient
    @State private var fullName: String = ""
    @State private var email: String = ""
    @State private var password: String = ""
    @State private var isLoading: Bool = false
    @State private var error: String?

    var onSuccess: () -> Void

    var body: some View {
        Form {
            Section(header: Text("Personal")) {
                TextField("Full name", text: $fullName)
                TextField("Email", text: $email)
                    .keyboardType(.emailAddress)
                    .autocapitalization(.none)
                SecureField("Password", text: $password)
            }
            if let error = error { Text(error).foregroundColor(.red) }
            Button(action: submit) { if isLoading { ProgressView() } else { Text("Create account") } }
                .disabled(isLoading || !isValid)

            Section {
                NavigationLink("Already have an account? Log in") { PatientLoginView { onSuccess() } }
            }
        }
        .navigationTitle("Sign Up")
    }

    private var isValid: Bool { !fullName.isEmpty && !email.isEmpty && !password.isEmpty }

    private func submit() {
        error = nil
        isLoading = true
        Task {
            do {
                userMode = .patient
                _ = try await NetworkService.shared.register(email: email, password: password, fullName: fullName)
                onSuccess()
            } catch {
                self.error = "Registration failed. Please review input."
            }
            isLoading = false
        }
    }
}

struct PatientPasswordResetView: View {
    @State private var email: String = ""
    @State private var isSubmitting: Bool = false
    @State private var message: String?

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


