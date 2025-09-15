import SwiftUI
import UIKit

// MARK: - Main Dual Login View
struct DualLoginView: View {
    @AppStorage("userMode") private var userMode: UserMode = .patient
    @AppStorage("patientAuthToken") private var patientAuthToken: String = ""
    @State private var email: String = ""
    @State private var password: String = ""
    @State private var otpCode: String = ""
    @State private var isLoading: Bool = false
    @State private var error: String?
    @State private var successMessage: String?
    @State private var showPassword: Bool = false
    @State private var currentStep: LoginStep = .methodSelection
    @State private var emailExists: Bool = false
    @State private var otpSent: Bool = false
    @FocusState private var focusedField: Field?
    @State private var showOnboarding: Bool = false

    var onSuccess: () -> Void

    private enum Field { case email, password, otp }
    
    private enum LoginStep {
        case methodSelection
        case emailInput
        case passwordLogin
        case otpRequest
        case otpVerification
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                // Logo and Welcome Section (Maintaining existing aesthetics)
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

                // Error Display (Maintaining existing style)
                if let error = error {
                    HStack {
                        Image(systemName: "exclamationmark.triangle.fill").foregroundColor(.white)
                        Text(error).foregroundColor(.white).font(.subheadline)
                    }
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.red)
                    .cornerRadius(12)
                }
                
                // Success Message Display
                if let successMessage = successMessage {
                    HStack {
                        Image(systemName: "checkmark.circle.fill").foregroundColor(.white)
                        Text(successMessage).foregroundColor(.white).font(.subheadline)
                    }
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.green)
                    .cornerRadius(12)
                }

                // Dynamic Content Based on Current Step
                switch currentStep {
                case .methodSelection:
                    methodSelectionView
                case .emailInput:
                    emailInputView
                case .passwordLogin:
                    passwordLoginView
                case .otpRequest:
                    otpRequestView
                case .otpVerification:
                    otpVerificationView
                }
            }
            .padding()
        }
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .modifier(HideNavBarCompat())
        .background(Color.white)
    }
    
    // MARK: - Method Selection View
    private var methodSelectionView: some View {
        VStack(spacing: 16) {
            Text("Choose how you'd like to sign in")
                .font(.headline)
                .frame(maxWidth: .infinity, alignment: .center)
                .foregroundColor(.primary)
            
            // Email Login Button
            Button(action: {
                currentStep = .emailInput
            }) {
                HStack {
                    Image(systemName: "envelope.fill")
                        .foregroundColor(.white)
                    Text("Continue with Email")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.zivoRed)
                .foregroundColor(.white)
                .cornerRadius(12)
            }
            
            // Google Sign-In Button
            Button(action: {
                signInWithGoogle()
            }) {
                HStack {
                    Image(systemName: "globe")
                        .foregroundColor(.primary)
                    Text("Continue with Google")
                        .fontWeight(.semibold)
                        .foregroundColor(.primary)
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.white)
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(.systemGray4), lineWidth: 1))
                .cornerRadius(12)
            }
            
            // Sign Up Link
            NavigationLink("Don't have an account? Sign up") { 
                DualRegistrationView { onSuccess() } 
            }
            .foregroundColor(.zivoRed)
            .frame(maxWidth: .infinity)
            .padding(.top, 8)
        }
    }
    
    // MARK: - Email Input View
    private var emailInputView: some View {
        VStack(spacing: 16) {
            Text("Enter your email address")
                .font(.headline)
                .frame(maxWidth: .infinity, alignment: .leading)
            
            VStack(spacing: 8) {
                TextField("Enter your email", text: $email)
                    .keyboardType(.emailAddress)
                    .textContentType(.username)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled(true)
                    .padding(14)
                    .background(Color.white)
                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(!email.isEmpty && !isValidEmail ? Color.red : Color(.systemGray4), lineWidth: 1))
                    .cornerRadius(12)
                    .focused($focusedField, equals: .email)
                    .submitLabel(.next)
                    .onSubmit { checkEmailAndProceed() }
                
                if !email.isEmpty && !isValidEmail {
                    Text("Please enter a valid email address")
                        .font(.caption)
                        .foregroundColor(.red)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            
            Button(action: checkEmailAndProceed) {
                HStack {
                    if isLoading { ProgressView().tint(.white) }
                    Text("Continue")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(.zivoRed)
            .controlSize(.regular)
            .disabled(!isValidEmail || isLoading)
            
            Button("Back") {
                currentStep = .methodSelection
                email = ""
                error = nil
                successMessage = nil
            }
            .foregroundColor(.zivoRed)
        }
    }
    
    // MARK: - Password Login View
    private var passwordLoginView: some View {
        VStack(spacing: 16) {
            Text("Enter your password")
                .font(.headline)
                .frame(maxWidth: .infinity, alignment: .leading)
            
            Text("Signing in as \(email)")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
            
            HStack {
                if showPassword {
                    TextField("Enter your password", text: $password)
                } else {
                    SecureField("Enter your password", text: $password)
                }
                
                Button(action: { showPassword.toggle() }) {
                    Image(systemName: showPassword ? "eye.slash.fill" : "eye.fill")
                        .foregroundColor(.gray)
                }
            }
            .padding(14)
            .background(Color.white)
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(.systemGray4), lineWidth: 1))
            .cornerRadius(12)
            .focused($focusedField, equals: .password)
            .submitLabel(.done)
            .onSubmit { loginWithPassword() }
            
            Button(action: loginWithPassword) {
                HStack {
                    if isLoading { ProgressView().tint(.white) }
                    Text("Sign In")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(.zivoRed)
            .controlSize(.regular)
            .disabled(password.isEmpty || isLoading)
            
            // Alternative login options
            VStack(spacing: 12) {
                Button("Use verification code instead") {
                    currentStep = .otpRequest
                    password = ""
                }
                .foregroundColor(.zivoRed)
                
                NavigationLink("Forgot Password?") {
                    PatientPasswordResetView(email: email)
                }
                .foregroundColor(.zivoRed)
                
                Button("Back") {
                    currentStep = .emailInput
                    password = ""
                    error = nil
                    successMessage = nil
                }
                .foregroundColor(.secondary)
            }
        }
    }
    
    // MARK: - OTP Request View
    private var otpRequestView: some View {
        VStack(spacing: 16) {
            Text("Send verification code")
                .font(.headline)
                .frame(maxWidth: .infinity, alignment: .leading)
            
            Text("We'll send a 6-digit code to \(email)")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
            
            Button(action: requestOTP) {
                HStack {
                    if isLoading { ProgressView().tint(.white) }
                    Text("Send Code")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(.zivoRed)
            .controlSize(.regular)
            .disabled(isLoading)
            
            Button("Back") {
                currentStep = .passwordLogin
                error = nil
                successMessage = nil
            }
            .foregroundColor(.secondary)
        }
    }
    
    // MARK: - OTP Verification View
    private var otpVerificationView: some View {
        VStack(spacing: 16) {
            Text("Enter verification code")
                .font(.headline)
                .frame(maxWidth: .infinity, alignment: .leading)
            
            Text("Enter the 6-digit code sent to \(email)")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
            
            TextField("000000", text: $otpCode)
                .keyboardType(.numberPad)
                .textContentType(.oneTimeCode)
                .multilineTextAlignment(.center)
                .font(.system(size: 24, weight: .bold, design: .monospaced))
                .padding(14)
                .background(Color.white)
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(.systemGray4), lineWidth: 1))
                .cornerRadius(12)
                .focused($focusedField, equals: .otp)
                .onChange(of: otpCode) { newValue in
                    if newValue.count == 6 {
                        verifyOTP()
                    }
                }
            
            Button(action: verifyOTP) {
                HStack {
                    if isLoading { ProgressView().tint(.white) }
                    Text("Verify Code")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(.zivoRed)
            .controlSize(.regular)
            .disabled(otpCode.count != 6 || isLoading)
            
            VStack(spacing: 12) {
                Button("Resend Code") {
                    requestOTP()
                }
                .foregroundColor(.zivoRed)
                
                Button("Back") {
                    currentStep = .otpRequest
                    otpCode = ""
                    error = nil
                    successMessage = nil
                }
                .foregroundColor(.secondary)
            }
        }
    }
    
    // MARK: - Helper Methods
    private var isValidEmail: Bool {
        let emailRegex = "^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$"
        let emailPredicate = NSPredicate(format: "SELF MATCHES %@", emailRegex)
        return emailPredicate.evaluate(with: email)
    }
    
    private func checkEmailAndProceed() {
        error = nil
        successMessage = nil
        isLoading = true
        
        Task {
            do {
                let response = try await NetworkService.shared.checkEmailExists(email: email)
                await MainActor.run {
                    emailExists = response.exists
                    if emailExists {
                        currentStep = .passwordLogin
                    } else {
                        currentStep = .otpRequest
                    }
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    self.error = "Failed to check email. Please try again."
                    isLoading = false
                }
            }
        }
    }
    
    private func loginWithPassword() {
        error = nil
        successMessage = nil
        isLoading = true
        
        Task {
            do {
                userMode = .patient
                NetworkService.shared.handleRoleChange()
                _ = try await NetworkService.shared.loginWithPassword(email: email, password: password)
                await MainActor.run {
                    if !NetworkService.shared.isOnboardingCompleted() { showOnboarding = true } else { onSuccess() }
                }
            } catch {
                await MainActor.run {
                    self.error = "Login failed. Please check your credentials."
                    isLoading = false
                }
            }
        }
    }
    
    private func requestOTP() {
        error = nil
        successMessage = nil
        isLoading = true
        
        Task {
            do {
                _ = try await NetworkService.shared.requestOTP(email: email)
                await MainActor.run {
                    currentStep = .otpVerification
                    otpSent = true
                    isLoading = false
                    successMessage = "Code sent successfully"
                    
                    // Clear success message after 3 seconds
                    DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                        successMessage = nil
                    }
                }
            } catch {
                await MainActor.run {
                    self.error = "Failed to send verification code. Please try again."
                    isLoading = false
                }
            }
        }
    }
    
    private func verifyOTP() {
        error = nil
        successMessage = nil
        isLoading = true
        
        Task {
            do {
                userMode = .patient
                NetworkService.shared.handleRoleChange()
                _ = try await NetworkService.shared.verifyOTP(email: email, code: otpCode)
                await MainActor.run {
                    if !NetworkService.shared.isOnboardingCompleted() { showOnboarding = true } else { onSuccess() }
                }
            } catch {
                await MainActor.run {
                    self.error = "Invalid verification code. Please try again."
                    isLoading = false
                }
            }
        }
    }
    
    private func signInWithGoogle() {
        error = nil
        successMessage = nil
        isLoading = true
        
        Task {
            do {
                userMode = .patient
                NetworkService.shared.handleRoleChange()
                _ = try await NetworkService.shared.signInWithGoogle()
                await MainActor.run {
                    if !NetworkService.shared.isOnboardingCompleted() { showOnboarding = true } else { onSuccess() }
                }
            } catch {
                await MainActor.run {
                    self.error = "Google sign-in failed. Please try again."
                    isLoading = false
                }
            }
        }
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
}

// MARK: - Registration View (Updated)
struct DualRegistrationView: View {
    @AppStorage("userMode") private var userMode: UserMode = .patient
    @State private var fullName: String = ""
    @State private var email: String = ""
    @State private var password: String = ""
    @State private var confirmPassword: String = ""
    @State private var isLoading: Bool = false
    @State private var error: String?
    @State private var showPassword: Bool = false
    @State private var showConfirmPassword: Bool = false
    @State private var currentStep: RegistrationStep = .methodSelection
    @State private var otpCode: String = ""
    @State private var otpSent: Bool = false
    @FocusState private var focusedField: Field?
    @State private var showOnboarding: Bool = false

    var onSuccess: () -> Void

    private enum Field { case fullName, email, password, confirmPassword, otp }
    
    private enum RegistrationStep {
        case methodSelection
        case basicInfo
        case passwordSetup
        case otpVerification
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                // Logo and Welcome Section (Maintaining existing aesthetics)
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

                    Text("Create Account")
                        .font(.system(size: 26, weight: .bold))
                        .foregroundColor(.zivoRed)
                        .frame(maxWidth: .infinity, alignment: .center)
                }
                .frame(maxWidth: .infinity)
                .padding(.top, 8)

                // Error Display (Maintaining existing style)
                if let error = error {
                    HStack {
                        Image(systemName: "exclamationmark.triangle.fill").foregroundColor(.white)
                        Text(error).foregroundColor(.white).font(.subheadline)
                    }
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.red)
                    .cornerRadius(12)
                }

                // Dynamic Content Based on Current Step
                switch currentStep {
                case .methodSelection:
                    registrationMethodSelectionView
                case .basicInfo:
                    basicInfoView
                case .passwordSetup:
                    passwordSetupView
                case .otpVerification:
                    otpVerificationView
                }
            }
            .padding()
        }
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .modifier(HideNavBarCompat())
        .background(Color.white)
        .sheet(isPresented: $showOnboarding, onDismiss: {
            onSuccess()
        }) {
            OnboardingFlowView(
                prefilledEmail: email,
                prefilledFullName: fullName
            )
            .environmentObject(NetworkService.shared)
        }
    }
    
    // MARK: - Registration Method Selection
    private var registrationMethodSelectionView: some View {
        VStack(spacing: 16) {
            Text("Choose how you'd like to create your account")
                .font(.headline)
                .frame(maxWidth: .infinity, alignment: .center)
                .foregroundColor(.primary)
            
            // Email Registration Button
            Button(action: {
                currentStep = .basicInfo
            }) {
                HStack {
                    Image(systemName: "envelope.fill")
                        .foregroundColor(.white)
                    Text("Continue with Email")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.zivoRed)
                .foregroundColor(.white)
                .cornerRadius(12)
            }
            
            // Google Sign-Up Button
            Button(action: {
                signUpWithGoogle()
            }) {
                HStack {
                    Image(systemName: "globe")
                        .foregroundColor(.primary)
                    Text("Continue with Google")
                        .fontWeight(.semibold)
                        .foregroundColor(.primary)
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.white)
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(.systemGray4), lineWidth: 1))
                .cornerRadius(12)
            }
            
            NavigationLink("Already have an account? Sign in") { 
                DualLoginView { onSuccess() } 
            }
            .foregroundColor(.zivoRed)
            .frame(maxWidth: .infinity)
            .padding(.top, 8)
        }
    }
    
    // MARK: - Basic Info View
    private var basicInfoView: some View {
        VStack(spacing: 16) {
            Text("Personal Information")
                .font(.headline)
                .frame(maxWidth: .infinity, alignment: .leading)
            
            TextField("Full name", text: $fullName)
                .textContentType(.name)
                .padding(14)
                .background(Color.white)
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(.systemGray4), lineWidth: 1))
                .cornerRadius(12)
                .focused($focusedField, equals: .fullName)
                .submitLabel(.next)
                .onSubmit { focusedField = .email }
            
            VStack(spacing: 8) {
                TextField("Email address", text: $email)
                    .keyboardType(.emailAddress)
                    .textContentType(.username)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled(true)
                    .padding(14)
                    .background(Color.white)
                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(!email.isEmpty && !isValidEmail ? Color.red : Color(.systemGray4), lineWidth: 1))
                    .cornerRadius(12)
                    .focused($focusedField, equals: .email)
                    .submitLabel(.next)
                    .onSubmit { proceedToPasswordSetup() }
                
                if !email.isEmpty && !isValidEmail {
                    Text("Please enter a valid email address")
                        .font(.caption)
                        .foregroundColor(.red)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            
            Button(action: proceedToPasswordSetup) {
                HStack {
                    if isLoading { ProgressView().tint(.white) }
                    Text("Continue")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(.zivoRed)
            .controlSize(.regular)
            .disabled(!isValidBasicInfo || isLoading)
            
            Button("Back") {
                currentStep = .methodSelection
                fullName = ""
                email = ""
                password = ""
                confirmPassword = ""
                error = nil
            }
            .foregroundColor(.zivoRed)
        }
    }
    
    // MARK: - Password Setup View
    private var passwordSetupView: some View {
        VStack(spacing: 16) {
            Text("Create Password")
                .font(.headline)
                .frame(maxWidth: .infinity, alignment: .leading)
            
            VStack(spacing: 12) {
                HStack {
                    if showPassword {
                        TextField("Create a password", text: $password)
                    } else {
                        SecureField("Create a password", text: $password)
                    }
                    
                    Button(action: { showPassword.toggle() }) {
                        Image(systemName: showPassword ? "eye.slash.fill" : "eye.fill")
                            .foregroundColor(.gray)
                    }
                }
                .padding(14)
                .background(Color.white)
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(.systemGray4), lineWidth: 1))
                .cornerRadius(12)
                .focused($focusedField, equals: .password)
                .submitLabel(.next)
                .onSubmit { focusedField = .confirmPassword }
                
                HStack {
                    if showConfirmPassword {
                        TextField("Confirm password", text: $confirmPassword)
                    } else {
                        SecureField("Confirm password", text: $confirmPassword)
                    }
                    
                    Button(action: { showConfirmPassword.toggle() }) {
                        Image(systemName: showConfirmPassword ? "eye.slash.fill" : "eye.fill")
                            .foregroundColor(.gray)
                    }
                }
                .padding(14)
                .background(Color.white)
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(password != confirmPassword && !confirmPassword.isEmpty ? Color.red : Color(.systemGray4), lineWidth: 1))
                .cornerRadius(12)
                .focused($focusedField, equals: .confirmPassword)
                .submitLabel(.done)
                .onSubmit { if isValidPassword { registerWithPassword() } }
                
                // Password validation messages
                if !password.isEmpty && password.count < 8 {
                    Text("Password must be at least 8 characters")
                        .font(.caption)
                        .foregroundColor(.red)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                
                if !confirmPassword.isEmpty && password != confirmPassword {
                    Text("Passwords do not match")
                        .font(.caption)
                        .foregroundColor(.red)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            
            Button(action: registerWithPassword) {
                HStack {
                    if isLoading { ProgressView().tint(.white) }
                    Text("Create Account")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(.zivoRed)
            .controlSize(.regular)
            .disabled(!isValidPassword || isLoading)
            
            // Alternative: OTP registration
            Button("Use verification code instead") {
                currentStep = .otpVerification
                password = ""
                confirmPassword = ""
            }
            .foregroundColor(.zivoRed)
            
            Button("Back") {
                currentStep = .basicInfo
                password = ""
                confirmPassword = ""
                error = nil
            }
            .foregroundColor(.secondary)
        }
    }
    
    // MARK: - OTP Verification View
    private var otpVerificationView: some View {
        VStack(spacing: 16) {
            Text("Verify your email")
                .font(.headline)
                .frame(maxWidth: .infinity, alignment: .leading)
            
            Text("Enter the 6-digit code sent to \(email)")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
            
            TextField("000000", text: $otpCode)
                .keyboardType(.numberPad)
                .textContentType(.oneTimeCode)
                .multilineTextAlignment(.center)
                .font(.system(size: 24, weight: .bold, design: .monospaced))
                .padding(14)
                .background(Color.white)
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(.systemGray4), lineWidth: 1))
                .cornerRadius(12)
                .focused($focusedField, equals: .otp)
                .onChange(of: otpCode) { newValue in
                    if newValue.count == 6 {
                        registerWithOTP()
                    }
                }
            
            Button(action: registerWithOTP) {
                HStack {
                    if isLoading { ProgressView().tint(.white) }
                    Text("Verify & Create Account")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(.zivoRed)
            .controlSize(.regular)
            .disabled(otpCode.count != 6 || isLoading)
            
            VStack(spacing: 12) {
                Button("Resend Code") {
                    requestOTP()
                }
                .foregroundColor(.zivoRed)
                
                Button("Back") {
                    currentStep = .passwordSetup
                    otpCode = ""
                    password = ""
                    confirmPassword = ""
                    error = nil
                }
                .foregroundColor(.secondary)
            }
        }
    }
    
    // MARK: - Helper Methods
    private var isValidEmail: Bool {
        let emailRegex = "^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$"
        let emailPredicate = NSPredicate(format: "SELF MATCHES %@", emailRegex)
        return emailPredicate.evaluate(with: email)
    }
    
    private var isValidBasicInfo: Bool {
        !fullName.isEmpty && !email.isEmpty && isValidEmail
    }
    
    private var isValidPassword: Bool {
        password.count >= 8 && password == confirmPassword
    }
    
    private func proceedToPasswordSetup() {
        currentStep = .passwordSetup
    }
    
    private func registerWithPassword() {
        error = nil
        isLoading = true
        
        Task {
            do {
                userMode = .patient
                NetworkService.shared.handleRoleChange()
                // Reset onboarding status for new user
                NetworkService.shared.resetOnboardingStatus()
                _ = try await NetworkService.shared.register(email: email, password: password, fullName: fullName)
                await MainActor.run {
                    let onboardingCompleted = NetworkService.shared.isOnboardingCompleted()
                    print("🔍 [DualAuthViews] Registration successful - onboardingCompleted: \(onboardingCompleted)")
                    if !onboardingCompleted { 
                        print("📋 [DualAuthViews] Showing onboarding flow")
                        showOnboarding = true 
                    } else { 
                        print("✅ [DualAuthViews] Onboarding already completed, calling onSuccess")
                        onSuccess() 
                    }
                }
            } catch {
                await MainActor.run {
                    self.error = "Registration failed. Please try again."
                    isLoading = false
                }
            }
        }
    }
    
    private func requestOTP() {
        error = nil
        isLoading = true
        
        Task {
            do {
                _ = try await NetworkService.shared.requestOTP(email: email)
                await MainActor.run {
                    otpSent = true
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    self.error = "Failed to send verification code. Please try again."
                    isLoading = false
                }
            }
        }
    }
    
    private func registerWithOTP() {
        error = nil
        isLoading = true
        
        Task {
            do {
                userMode = .patient
                NetworkService.shared.handleRoleChange()
                // Reset onboarding status for new user
                NetworkService.shared.resetOnboardingStatus()
                _ = try await NetworkService.shared.registerWithOTP(email: email, code: otpCode, fullName: fullName)
                await MainActor.run {
                    let onboardingCompleted = NetworkService.shared.isOnboardingCompleted()
                    print("🔍 [DualAuthViews] OTP Registration successful - onboardingCompleted: \(onboardingCompleted)")
                    if !onboardingCompleted { 
                        print("📋 [DualAuthViews] Showing onboarding flow")
                        showOnboarding = true 
                    } else { 
                        print("✅ [DualAuthViews] Onboarding already completed, calling onSuccess")
                        onSuccess() 
                    }
                }
            } catch {
                await MainActor.run {
                    self.error = "Invalid verification code. Please try again."
                    isLoading = false
                }
            }
        }
    }
    
    private func signUpWithGoogle() {
        error = nil
        isLoading = true
        
        Task {
            do {
                userMode = .patient
                NetworkService.shared.handleRoleChange()
                // Reset onboarding status for new user
                NetworkService.shared.resetOnboardingStatus()
                _ = try await NetworkService.shared.signInWithGoogle()
                await MainActor.run {
                    let onboardingCompleted = NetworkService.shared.isOnboardingCompleted()
                    print("🔍 [DualAuthViews] Google Registration successful - onboardingCompleted: \(onboardingCompleted)")
                    if !onboardingCompleted { 
                        print("📋 [DualAuthViews] Showing onboarding flow")
                        showOnboarding = true 
                    } else { 
                        print("✅ [DualAuthViews] Onboarding already completed, calling onSuccess")
                        onSuccess() 
                    }
                }
            } catch {
                await MainActor.run {
                    self.error = "Google sign-up failed. Please try again."
                    isLoading = false
                }
            }
        }
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
}
