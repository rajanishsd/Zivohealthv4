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
    @State private var showReactivationAlert: Bool = false
    @State private var reactivationMessage: String = ""
    @State private var deferredNavigation: (() -> Void)? = nil

    var onSuccess: () -> Void

    private enum Field { case email, password, otp }
    
    private enum LoginStep {
        case methodSelection
        case emailInput
        case passwordLogin
        case otpRequest
        case otpVerification
        case emailVerificationWaiting
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
                    combinedLoginView
                case .passwordLogin:
                    passwordLoginView  // Keep for backward compatibility
                case .otpRequest:
                    otpRequestView
                case .otpVerification:
                    otpVerificationView
                case .emailVerificationWaiting:
                    emailVerificationWaitingView
                }
            }
            .padding()
        }
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .modifier(HideNavBarCompat())
        .background(Color.white)
        .sheet(isPresented: $showOnboarding, onDismiss: {
            if NetworkService.shared.isOnboardingCompleted() {
                onSuccess()
            }
        }) {
            OnboardingFlowView(
                prefilledEmail: email,
                prefilledFullName: GoogleSignInService.shared.currentUser?.profile?.name,
                prefilledFirstName: GoogleSignInService.shared.currentUser?.profile?.givenName,
                prefilledMiddleName: nil,
                prefilledLastName: GoogleSignInService.shared.currentUser?.profile?.familyName
            )
            .environmentObject(NetworkService.shared)
        }
        .alert("Account Restored", isPresented: $showReactivationAlert) {
            Button("OK") {
                // Perform any deferred navigation after acknowledging the alert
                deferredNavigation?()
                deferredNavigation = nil
            }
        } message: {
            Text(reactivationMessage.isEmpty ? "Your account has been reactivated. Welcome back!" : reactivationMessage)
        }
        .onReceive(NotificationCenter.default.publisher(for: .deletionCancelled)) { notification in
            if let message = notification.userInfo?["message"] as? String {
                reactivationMessage = message
            } else {
                reactivationMessage = "Your account has been reactivated. Welcome back!"
            }
            showReactivationAlert = true
        }
        .onReceive(NotificationCenter.default.publisher(for: NSNotification.Name("EmailVerificationSuccess"))) { notification in
            // Email was verified successfully via deep link
            print("✅ [DualLoginView] Email verification success notification received")
            if let message = notification.userInfo?["message"] as? String {
                successMessage = message
            } else {
                successMessage = "Email verified successfully!"
            }
            // Navigate back to login
            currentStep = .methodSelection
        }
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
    
    // MARK: - Combined Login View (Email + Password)
    private var combinedLoginView: some View {
        VStack(spacing: 16) {
            Text("Sign in to your account")
                .font(.headline)
                .frame(maxWidth: .infinity, alignment: .center)
                .foregroundColor(.primary)
            
            // Email Field
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
                    .onSubmit { focusedField = .password }
                
                if !email.isEmpty && !isValidEmail {
                    Text("Please enter a valid email address")
                        .font(.caption)
                        .foregroundColor(.red)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            
            // Password Field
            HStack {
                if showPassword {
                    TextField("Password", text: $password)
                        .textContentType(.password)
                } else {
                    SecureField("Password", text: $password)
                        .textContentType(.password)
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
            .onSubmit { if isValidEmail && !password.isEmpty { loginWithPassword() } }
            
            // Sign In Button
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
            .disabled(!isValidEmail || password.isEmpty || isLoading)
            
            // Divider
            HStack {
                Rectangle().frame(height: 1).foregroundColor(Color(.systemGray4))
                Text("or").font(.subheadline).foregroundColor(.secondary)
                Rectangle().frame(height: 1).foregroundColor(Color(.systemGray4))
            }
            .padding(.vertical, 8)
            
                // Alternative Login Options
                HStack(spacing: 8) {
                    // Forgot Password Link
                    NavigationLink("Forgot password?") {
                        PatientPasswordResetView(email: email)
                    }
                    .font(.subheadline)
                    .foregroundColor(.zivoRed)
                    
                    Text("|")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    // Use OTP Instead Link
                    Button(action: {
                        currentStep = .otpRequest
                        password = ""
                        otpSent = false
                        otpCode = ""
                    }) {
                        Text("Use OTP to login")
                    }
                    .font(.subheadline)
                    .foregroundColor(.zivoRed)
                }
            
            // Sign Up and Back Links
            VStack(spacing: 12) {
                NavigationLink("Don't have an account? Sign up") { 
                    DualRegistrationView { onSuccess() } 
                }
                .foregroundColor(.zivoRed)
                .frame(maxWidth: .infinity)
                
                Button("Back") {
                    currentStep = .methodSelection
                    email = ""
                    password = ""
                    error = nil
                    successMessage = nil
                }
                .foregroundColor(.zivoRed)
            }
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
                    otpSent = false
                    otpCode = ""
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
            Text("Sign in with verification code")
                .font(.headline)
                .frame(maxWidth: .infinity, alignment: .center)
                .foregroundColor(.primary)
            
            // Email Field
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
                    .submitLabel(.done)
                    .disabled(otpSent)  // Disable after OTP is sent
                
                if !email.isEmpty && !isValidEmail {
                    Text("Please enter a valid email address")
                        .font(.caption)
                        .foregroundColor(.red)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            
            // Send Verification Code Button
            if !otpSent {
                Button(action: requestOTP) {
                    HStack {
                        if isLoading { ProgressView().tint(.white) }
                        Text("Send Verification Code")
                            .fontWeight(.semibold)
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(.zivoRed)
                .controlSize(.regular)
                .disabled(!isValidEmail || isLoading)
            }
            
            // OTP Input Section (shown after code is sent)
            if otpSent {
                VStack(spacing: 16) {
                    Text("Enter the 6-digit code sent to")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    Text(email)
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(.primary)
                    
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
                    
                    Button("Resend Code") {
                        requestOTP()
                    }
                    .font(.subheadline)
                    .foregroundColor(.zivoRed)
                }
            }
            
            // Back Button
            Button("Back") {
                currentStep = .emailInput
                email = ""
                otpCode = ""
                otpSent = false
                error = nil
                successMessage = nil
            }
            .foregroundColor(.zivoRed)
            .padding(.top, 8)
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
                        self.error = "No User found with this email. Please sign up first."
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
                    isLoading = false
                    // Build the next navigation action
                    if !NetworkService.shared.isOnboardingCompleted() {
                        deferredNavigation = { showOnboarding = true }
                    } else {
                        deferredNavigation = { onSuccess() }
                    }
                    // If no reactivation alert is showing, proceed immediately; else wait for alert OK
                    if !showReactivationAlert {
                        deferredNavigation?()
                        deferredNavigation = nil
                    }
                }
            } catch {
                await MainActor.run {
                    // Check if error is due to unverified email
                    let errorMessage = "\(error)"
                    if errorMessage.contains("EMAIL_NOT_VERIFIED") || errorMessage.contains("Inactive user") {
                        self.error = nil
                        // Navigate to verification waiting screen
                        self.currentStep = .emailVerificationWaiting
                        self.successMessage = "Please verify your email to continue. Check your inbox for the verification link."
                    } else {
                        // Extract the actual error message from the backend
                        if let range = errorMessage.range(of: "HTTP \\d+: ", options: .regularExpression) {
                            // Extract everything after "HTTP 401: " and clean up trailing characters
                            var message = String(errorMessage[range.upperBound...])
                            // Remove trailing "))" or ")" that might be part of the error wrapper
                            message = message.trimmingCharacters(in: CharacterSet(charactersIn: ")\""))
                            self.error = message
                        } else if errorMessage.contains("serverError(") {
                            // Extract message from serverError("message")
                            if let start = errorMessage.firstIndex(of: "\""),
                               let end = errorMessage.lastIndex(of: "\""),
                               start < end {
                                self.error = String(errorMessage[errorMessage.index(after: start)..<end])
                            } else {
                                self.error = "Login failed. Please check your credentials."
                            }
                        } else {
                            self.error = "Login failed. Please check your credentials."
                        }
                    }
                    isLoading = false
                }
            }
        }
    }
    
    private func resendVerificationEmailFromLogin() {
        error = nil
        successMessage = nil
        isLoading = true
        
        Task {
            do {
                let message = try await NetworkService.shared.resendVerificationEmail(email: email)
                await MainActor.run {
                    print("✅ [DualLoginView] Verification email resent: \(message)")
                    successMessage = "Verification email sent! Please check your inbox."
                    isLoading = false
                    
                    // Clear success message after 5 seconds
                    DispatchQueue.main.asyncAfter(deadline: .now() + 5) {
                        successMessage = nil
                    }
                }
            } catch {
                await MainActor.run {
                    self.error = "Failed to resend verification email. Please try again."
                    isLoading = false
                }
            }
        }
    }
    
    // MARK: - Email Verification Waiting View (Login)
    private var emailVerificationWaitingView: some View {
        VStack(spacing: 24) {
            // Icon
            Image(systemName: "envelope.circle.fill")
                .resizable()
                .scaledToFit()
                .frame(width: 100, height: 100)
                .foregroundColor(.zivoRed)
                .padding(.top, 20)
            
            Text("Email Verification Required")
                .font(.system(size: 26, weight: .bold))
                .foregroundColor(.zivoRed)
                .frame(maxWidth: .infinity, alignment: .center)
            
            VStack(spacing: 16) {
                Text("We've sent a verification email to:")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                Text(email)
                    .font(.headline)
                    .foregroundColor(.primary)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 10)
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                
                Text("Please check your inbox and click the verification link to activate your account before signing in.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
            }
            
            Divider()
                .padding(.vertical, 8)
            
            VStack(spacing: 12) {
                Text("Didn't receive the email?")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                Button(action: resendVerificationEmailFromLogin) {
                    HStack {
                        if isLoading { ProgressView().tint(.zivoRed) }
                        Text("Resend Verification Email")
                            .fontWeight(.semibold)
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .tint(.zivoRed)
                .controlSize(.regular)
                .disabled(isLoading)
                
                Text("Check your spam folder if you don't see it")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
            
            Spacer()
            
            Button("Back to Sign In") {
                currentStep = .methodSelection
                email = ""
                password = ""
                error = nil
                successMessage = nil
            }
            .foregroundColor(.zivoRed)
            .padding(.bottom, 20)
        }
    }
    
    private func requestOTP() {
        error = nil
        successMessage = nil
        isLoading = true
        
        Task {
            do {
                let message = try await NetworkService.shared.requestOTP(email: email)
                await MainActor.run {
                    // Check if it's a generic message (user doesn't exist)
                    if message.contains("If an account exists") {
                        // Show generic message without moving to OTP input
                        otpSent = false
                        isLoading = false
                        successMessage = message
                        
                        // Clear success message after 5 seconds
                        DispatchQueue.main.asyncAfter(deadline: .now() + 5) {
                            successMessage = nil
                        }
                    } else {
                        // Real OTP sent - show OTP input
                        otpSent = true
                        isLoading = false
                        successMessage = "Code sent successfully. Please check your email."
                        focusedField = .otp  // Auto-focus on OTP field
                        
                        // Clear success message after 3 seconds
                        DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                            successMessage = nil
                        }
                    }
                }
            } catch {
                await MainActor.run {
                    // Check if error is due to unverified email
                    let errorMessage = "\(error)"
                    if errorMessage.contains("EMAIL_NOT_VERIFIED") {
                        self.error = nil
                        // Navigate to verification waiting screen
                        self.currentStep = .emailVerificationWaiting
                        self.successMessage = "Please verify your email first. Check your inbox for the verification link."
                    } else {
                        // Extract the actual error message or show generic one
                        if let range = errorMessage.range(of: "HTTP \\d+: ", options: .regularExpression) {
                            var message = String(errorMessage[range.upperBound...])
                            message = message.trimmingCharacters(in: CharacterSet(charactersIn: ")\""))
                            self.error = message
                        } else {
                            self.error = "Failed to send verification code. Please try again."
                        }
                    }
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
    @State private var email: String = ""
    @State private var password: String = ""
    @State private var confirmPassword: String = ""
    @State private var isLoading: Bool = false
    @State private var error: String?
    @State private var showPassword: Bool = false
    @State private var showConfirmPassword: Bool = false
    @State private var currentStep: RegistrationStep = .methodSelection
    @FocusState private var focusedField: Field?
    @State private var showOnboarding: Bool = false
    @State private var acceptedPrivacyPolicy: Bool = false
    @State private var acceptedTerms: Bool = false
    @State private var showPrivacyPolicy: Bool = false
    @State private var showTermsOfService: Bool = false

    var onSuccess: () -> Void

    private enum Field { case email, password, confirmPassword }
    
    private enum RegistrationStep {
        case methodSelection
        case emailPasswordSetup
        case emailVerificationWaiting
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
                case .emailPasswordSetup:
                    emailPasswordSetupView
                case .emailVerificationWaiting:
                    emailVerificationWaitingView
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
            OnboardingFlowView()
                .environmentObject(NetworkService.shared)
        }
        .onReceive(NotificationCenter.default.publisher(for: NSNotification.Name("EmailVerificationSuccess"))) { notification in
            // Email was verified successfully via deep link
            print("✅ [DualRegistrationView] Email verification success notification received")
            // Show success message and allow user to proceed to login
            error = nil
            if let message = notification.userInfo?["message"] as? String {
                // Show alert informing user they can now sign in
                Task {
                    await MainActor.run {
                        // Navigate back to method selection with a success indicator
                        currentStep = .methodSelection
                    }
                }
            }
        }
    }
    
    // MARK: - Registration Method Selection
    private var registrationMethodSelectionView: some View {
        VStack(spacing: 16) {
            // Email Registration Button
            Button(action: {
                currentStep = .emailPasswordSetup
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
    
    // MARK: - Combined Email & Password Setup View
    private var emailPasswordSetupView: some View {
        VStack(spacing: 16) {
            Text("Create Your Account")
                .font(.headline)
                .frame(maxWidth: .infinity, alignment: .leading)
            
            // Email Field
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
                    .onSubmit { focusedField = .password }
                
                if !email.isEmpty && !isValidEmail {
                    Text("Please enter a valid email address")
                        .font(.caption)
                        .foregroundColor(.red)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            
            // Password Fields
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
                .onSubmit { if isValidPasswordAndAgreed { registerWithPassword() } }
                
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
            
            // Privacy Policy and Terms Agreement
            privacyAndTermsAgreement
            
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
            .disabled(!isValidPasswordAndAgreed || isLoading)
            
            Button("Back") {
                currentStep = .methodSelection
                email = ""
                password = ""
                confirmPassword = ""
                error = nil
            }
            .foregroundColor(.secondary)
        }
        .sheet(isPresented: $showPrivacyPolicy) {
            NavigationView {
                PrivacyPolicyView()
                    .toolbar {
                        ToolbarItem(placement: .navigationBarTrailing) {
                            Button("Done") {
                                showPrivacyPolicy = false
                            }
                        }
                    }
            }
        }
        .sheet(isPresented: $showTermsOfService) {
            NavigationView {
                TermsOfServiceView()
                    .toolbar {
                        ToolbarItem(placement: .navigationBarTrailing) {
                            Button("Done") {
                                showTermsOfService = false
                            }
                        }
                    }
            }
        }
    }
    
    // MARK: - Email Verification Waiting View
    private var emailVerificationWaitingView: some View {
        VStack(spacing: 24) {
            // Icon
            Image(systemName: "envelope.circle.fill")
                .resizable()
                .scaledToFit()
                .frame(width: 100, height: 100)
                .foregroundColor(.zivoRed)
                .padding(.top, 20)
            
            Text("Verify Your Email")
                .font(.system(size: 28, weight: .bold))
                .foregroundColor(.zivoRed)
                .frame(maxWidth: .infinity, alignment: .center)
            
            VStack(spacing: 16) {
                Text("We've sent a verification email to:")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                Text(email)
                    .font(.headline)
                    .foregroundColor(.primary)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 10)
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                
                Text("Please check your inbox and click the verification link to activate your account.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
            }
            
            Divider()
                .padding(.vertical, 8)
            
            VStack(spacing: 12) {
                Text("Didn't receive the email?")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                Button(action: resendVerificationEmail) {
                    HStack {
                        if isLoading { ProgressView().tint(.zivoRed) }
                        Text("Resend Verification Email")
                            .fontWeight(.semibold)
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .tint(.zivoRed)
                .controlSize(.regular)
                .disabled(isLoading)
                
                Text("Check your spam folder if you don't see it")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
            
            Spacer()
            
            Button("Back to Sign In") {
                currentStep = .methodSelection
                email = ""
                password = ""
                confirmPassword = ""
                error = nil
            }
            .foregroundColor(.zivoRed)
            .padding(.bottom, 20)
        }
    }
    
    // MARK: - Privacy & Terms Agreement View
    private var privacyAndTermsAgreement: some View {
        VStack(spacing: 12) {
            Divider()
                .padding(.vertical, 4)
            
            // Privacy Policy Checkbox
            HStack(alignment: .top, spacing: 12) {
                Button(action: { acceptedPrivacyPolicy.toggle() }) {
                    Image(systemName: acceptedPrivacyPolicy ? "checkmark.square.fill" : "square")
                        .font(.system(size: 22))
                        .foregroundColor(acceptedPrivacyPolicy ? .zivoRed : .gray)
                }
                
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 4) {
                        Text("I have read and agree to the")
                            .font(.subheadline)
                            .foregroundColor(.primary)
                        Button(action: { showPrivacyPolicy = true }) {
                            Text("Privacy Policy")
                                .font(.subheadline)
                                .fontWeight(.semibold)
                                .foregroundColor(.zivoRed)
                                .underline()
                        }
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            
            // Terms and Conditions Checkbox
            HStack(alignment: .top, spacing: 12) {
                Button(action: { acceptedTerms.toggle() }) {
                    Image(systemName: acceptedTerms ? "checkmark.square.fill" : "square")
                        .font(.system(size: 22))
                        .foregroundColor(acceptedTerms ? .zivoRed : .gray)
                }
                
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 4) {
                        Text("I accept the")
                            .font(.subheadline)
                            .foregroundColor(.primary)
                        Button(action: { showTermsOfService = true }) {
                            Text("Terms and Conditions")
                                .font(.subheadline)
                                .fontWeight(.semibold)
                                .foregroundColor(.zivoRed)
                                .underline()
                        }
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            
            if !isAgreementsAccepted && (!acceptedPrivacyPolicy || !acceptedTerms) {
                Text("Please accept both Privacy Policy and Terms to continue")
                    .font(.caption)
                    .foregroundColor(.red)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, 4)
            }
        }
        .padding(.vertical, 8)
    }
    
    // MARK: - Helper Methods
    private var isValidEmail: Bool {
        let emailRegex = "^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$"
        let emailPredicate = NSPredicate(format: "SELF MATCHES %@", emailRegex)
        return emailPredicate.evaluate(with: email)
    }
    
    private var isValidPassword: Bool {
        password.count >= 8 && password == confirmPassword
    }
    
    private var isAgreementsAccepted: Bool {
        acceptedPrivacyPolicy && acceptedTerms
    }
    
    private var isValidPasswordAndAgreed: Bool {
        !email.isEmpty && isValidEmail && isValidPassword && isAgreementsAccepted
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
                let message = try await NetworkService.shared.register(email: email, password: password)
                await MainActor.run {
                    print("✅ [DualAuthViews] Registration successful: \(message)")
                    print("📧 [DualAuthViews] Moving to email verification waiting screen")
                    isLoading = false
                    currentStep = .emailVerificationWaiting
                }
            } catch {
                await MainActor.run {
                    // Extract the actual error message from the backend
                    let errorMessage = "\(error)"
                    if let range = errorMessage.range(of: "HTTP \\d+: ", options: .regularExpression) {
                        // Extract everything after "HTTP 400: " and clean up trailing characters
                        var message = String(errorMessage[range.upperBound...])
                        // Remove trailing "))" or ")" that might be part of the error wrapper
                        message = message.trimmingCharacters(in: CharacterSet(charactersIn: ")\""))
                        self.error = message
                    } else if errorMessage.contains("serverError(") {
                        // Extract message from serverError("message")
                        if let start = errorMessage.firstIndex(of: "\""),
                           let end = errorMessage.lastIndex(of: "\""),
                           start < end {
                            self.error = String(errorMessage[errorMessage.index(after: start)..<end])
                        } else {
                            self.error = "Registration failed. Please try again."
                        }
                    } else {
                        self.error = "Registration failed. Please try again."
                    }
                    isLoading = false
                }
            }
        }
    }
    
    private func resendVerificationEmail() {
        error = nil
        isLoading = true
        
        Task {
            do {
                let message = try await NetworkService.shared.resendVerificationEmail(email: email)
                await MainActor.run {
                    print("✅ [DualAuthViews] Verification email resent: \(message)")
                    // Show success message temporarily
                    self.error = nil
                    isLoading = false
                    
                    // You could add a success banner here if desired
                }
            } catch {
                await MainActor.run {
                    self.error = "Failed to resend verification email. Please try again."
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
