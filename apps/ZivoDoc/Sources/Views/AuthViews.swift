import SwiftUI
import UIKit

struct DoctorLoginView: View {
    @AppStorage("userMode") private var userMode: UserMode = .doctor
    @AppStorage("didDoctorLogin") private var didDoctorLogin: Bool = false
    @State private var email: String = ""
    @State private var password: String = ""
    @State private var isLoading: Bool = false
    @State private var error: String?
    @State private var showPassword: Bool = false
    @FocusState private var focusedField: Field?

    var onSuccess: () -> Void

    private enum Field {
        case email
        case password
    }

    private var isValid: Bool {
        // basic email and non-empty password check
        let hasAt = email.contains("@") && email.contains(".")
        return hasAt && !password.isEmpty
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                // Header with logo and title
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
                // Error banner
                if let error = error {
                    HStack(spacing: 12) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundColor(.white)
                        Text(error)
                            .foregroundColor(.white)
                            .font(.subheadline)
                    }
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.red)
                    .cornerRadius(12)
                }

                VStack(spacing: 16) {
                    // Email field
                    Text("Email")
                        .font(.headline)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    TextField("Enter your email", text: $email)
                        .keyboardType(.emailAddress)
                        .textContentType(.username)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled(true)
                        .padding(14)
                        .background(Color.white)
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(Color(.systemGray4), lineWidth: 1)
                        )
                        .cornerRadius(12)
                        .focused($focusedField, equals: .email)
                        .submitLabel(.next)
                        .onSubmit { focusedField = .password }

                    Text("Password")
                        .font(.headline)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    // Password field with show/hide
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
                            Image(systemName: showPassword ? "eye.slash" : "eye")
                                .foregroundColor(.secondary)
                        }
                    }
                    .padding(14)
                    .background(Color.white)
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(Color(.systemGray4), lineWidth: 1)
                    )
                    .cornerRadius(12)
                }

                // Primary actions
                VStack(spacing: 12) {
                    Button(action: submit) {
                        HStack {
                            if isLoading { ProgressView().tint(.white) }
                            Text("Log In")
                                .fontWeight(.semibold)
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.zivoRed)
                    .controlSize(.regular)
                    .disabled(!isValid || isLoading)

                    HStack(spacing: 16) {
                        NavigationLink("Forgot Password?") {
                            DoctorPasswordResetView()
                        }
                        Text("|")
                            .foregroundColor(.secondary)
                        NavigationLink("Sign Up") {
                            DoctorRegistrationView { onSuccess() }
                        }
                    }
                    .font(.footnote)
                    .tint(.zivoRed)
                    .frame(maxWidth: .infinity)
                }

                // Secondary
                Divider().padding(.vertical, 4)
            }
            .padding()
        }
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .modifier(HideNavBarCompat())
        .background(Color.white)
        // Keyboard safe area handling kept default for compatibility
    }

    private struct HideNavBarCompat: ViewModifier {
        func body(content: Content) -> some View {
            if #available(iOS 16.0, *) {
                content.toolbar(.hidden, for: .navigationBar)
            } else {
                content.navigationBarHidden(true)
            }
        }
    }

    private func submit() {
        error = nil
        isLoading = true
        Task {
            do {
                userMode = .doctor
                NetworkService.shared.handleRoleChange()
                _ = try await NetworkService.shared.login(email: email, password: password)
                didDoctorLogin = true
                onSuccess()
            } catch {
                self.error = "Login failed. Please check credentials."
            }
            isLoading = false
        }
    }
}

struct DoctorRegistrationView: View {
    @AppStorage("userMode") private var userMode: UserMode = .doctor
    @AppStorage("didDoctorLogin") private var didDoctorLogin: Bool = false
    @State private var fullName: String = ""
    @State private var email: String = ""
    @State private var password: String = ""
    @State private var licenseNumber: String = ""
    @State private var specialization: String = "General Medicine"
    @State private var yearsExperience: String = "5"
    @State private var contactNumber: String = ""
    @State private var dateOfBirth: Date = Calendar.current.date(byAdding: .year, value: -35, to: Date()) ?? Date()
    @State private var bio: String = ""
    @State private var isAvailable: Bool = true
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
                DatePicker("Date of Birth", selection: $dateOfBirth, displayedComponents: .date)
                TextField("Contact number", text: $contactNumber)
                    .keyboardType(.phonePad)
            }
            Section(header: Text("Professional")) {
                TextField("License number", text: $licenseNumber)
                TextField("Specialization", text: $specialization)
                TextField("Years of experience", text: $yearsExperience)
                    .keyboardType(.numberPad)
                TextField("Bio (optional)", text: $bio)
                Toggle("Available", isOn: $isAvailable)
            }
            if let error = error {
                Text(error).foregroundColor(.red)
            }
            Button(action: submit) {
                if isLoading { ProgressView() } else { Text("Create account") }
            }
            .disabled(isLoading || !isValid)

            Section {
                NavigationLink("Already have an account? Log in") {
                    DoctorLoginView { onSuccess() }
                }
            }
        }
        .navigationTitle("Doctor Sign Up")
    }

    private var isValid: Bool {
        !fullName.isEmpty && !email.isEmpty && !password.isEmpty && !licenseNumber.isEmpty && !specialization.isEmpty && Int(yearsExperience) != nil
    }

    private func submit() {
        error = nil
        isLoading = true
        Task {
            do {
                userMode = .doctor
                let input = NetworkService.DoctorRegistrationInput(
                    email: email,
                    password: password,
                    fullName: fullName,
                    dateOfBirth: dateOfBirth,
                    contactNumber: contactNumber.isEmpty ? nil : contactNumber,
                    licenseNumber: licenseNumber,
                    specialization: specialization,
                    yearsExperience: Int(yearsExperience) ?? 0,
                    bio: bio.isEmpty ? nil : bio,
                    isAvailable: isAvailable
                )
                try await NetworkService.shared.registerDoctor(input)
                // Show success message and navigate back to login
                self.error = nil
                // Pop back one level to login
                onSuccess()
            } catch {
                self.error = "Registration failed. Please review input."
            }
            isLoading = false
        }
    }
}

// MARK: - Password Reset
struct DoctorPasswordResetView: View {
    @State private var email: String = ""
    @State private var isSubmitting: Bool = false
    @State private var message: String?

    private var isValid: Bool {
        email.contains("@") && email.contains(".")
    }

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
                Text(message)
                    .font(.footnote)
                    .foregroundColor(.green)
            }

            Button(action: submit) {
                HStack {
                    if isSubmitting { ProgressView() }
                    Text("Send Reset Link")
                }
            }
            .disabled(!isValid || isSubmitting)
        }
        .navigationTitle("Forgot Password")
    }

    private func submit() {
        isSubmitting = true
        // Placeholder UX; backend endpoint not implemented yet
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
            message = "If this email exists, a reset link has been sent."
            isSubmitting = false
        }
    }
}



