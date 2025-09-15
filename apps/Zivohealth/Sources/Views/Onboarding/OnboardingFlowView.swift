import SwiftUI

struct OnboardingFlowView: View {
    @StateObject var vm = OnboardingViewModel()
    @EnvironmentObject var network: NetworkService
    @State private var currentStep = 0
    @State private var isSubmitting = false
    @State private var errorMessage: String?
    @Environment(\.dismiss) private var dismiss
    
    // Pre-filled data from registration
    let prefilledEmail: String?
    let prefilledFullName: String?
    
    init(prefilledEmail: String? = nil, prefilledFullName: String? = nil) {
        self.prefilledEmail = prefilledEmail
        self.prefilledFullName = prefilledFullName
    }
    
    private let steps = [
        "Basic Details",
        "Health Conditions", 
        "Lifestyle",
        "Notifications",
        "Consents"
    ]
    
    private var progress: Double {
        Double(currentStep + 1) / Double(steps.count)
    }

    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Progress indicator
                VStack(spacing: 8) {
                    HStack {
                        Text("Step \(currentStep + 1) of \(steps.count)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Spacer()
                        Text("\(Int(progress * 100))%")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    
                    ProgressView(value: progress)
                        .progressViewStyle(LinearProgressViewStyle(tint: .zivoRed))
                }
                .padding(.horizontal)
                .padding(.top)
                
                // Current step content
                Group {
                    switch currentStep {
                    case 0:
                        BasicDetailsView(vm: vm)
                    case 1:
                        HealthConditionsView(vm: vm)
                    case 2:
                        LifestyleView(vm: vm)
                    case 3:
                        NotificationsView(vm: vm)
                    case 4:
                        ConsentsView(vm: vm)
                    default:
                        BasicDetailsView(vm: vm)
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                
                // Navigation buttons
                VStack(spacing: 12) {
                    if let msg = errorMessage {
                        Text(msg)
                            .foregroundColor(.red)
                            .font(.caption)
                            .padding(.horizontal)
                    }
                    
                    HStack(spacing: 16) {
                        if currentStep > 0 {
                            Button("Back") {
                                withAnimation(.easeInOut(duration: 0.3)) {
                                    currentStep -= 1
                                }
                            }
                            .buttonStyle(.bordered)
                            .frame(maxWidth: .infinity)
                        }
                        
                        Button(action: {
                            if currentStep == steps.count - 1 {
                                submit()
                            } else {
                                withAnimation(.easeInOut(duration: 0.3)) {
                                    currentStep += 1
                                }
                            }
                        }) {
                            HStack {
                                if currentStep == steps.count - 1 {
                                    if isSubmitting {
                                        ProgressView()
                                            .scaleEffect(0.8)
                                    } else {
                                        Image(systemName: "checkmark")
                                    }
                                    Text(isSubmitting ? "Submitting..." : "Submit")
                                } else {
                                    Text("Next")
                                    Image(systemName: "arrow.right")
                                }
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.zivoRed)
                        .frame(maxWidth: .infinity)
                        .disabled(!canProceed)
                    }
                    .frame(maxWidth: .infinity)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
                    .padding(.bottom)
                }
                .background(.ultraThinMaterial)
            }
            .navigationTitle(steps[currentStep])
            .navigationBarTitleDisplayMode(.inline)
            .onAppear {
                // Pre-fill data from registration if available
                if let email = prefilledEmail, let fullName = prefilledFullName {
                    vm.prefillFromRegistration(email: email, fullName: fullName)
                } else {
                    // Fallback to Google data if available
                    vm.prefillFromGoogle()
                }
            }
        }
    }
    
    private var canProceed: Bool {
        switch currentStep {
        case 0: // Basic Details
            return vm.isValidBasics()
        case 1, 2, 3: // Health, Lifestyle, Notifications
            return true // These steps are optional
        case 4: // Consents
            return vm.consentDataStorage && vm.consentRecommendations && vm.consentTermsPrivacy
        default:
            return false
        }
    }

    func submit() {
        guard vm.isValidBasics() else { 
            errorMessage = "Email and phone are required"
            return 
        }
        isSubmitting = true
        errorMessage = nil
        Task {
            do {
                let payload = vm.buildPayload()
                print("📤 [OnboardingFlowView] Submitting onboarding data...")
                _ = try await network.post("/onboarding/submit", body: payload, requiresAuth: true)
                print("✅ [OnboardingFlowView] Onboarding data submitted successfully")
                await MainActor.run {
                    isSubmitting = false
                    network.markOnboardingCompleted()
                    // Update authentication state to trigger ContentView refresh
                    network.updateAuthenticationState()
                    // Close the onboarding flow
                    dismiss()
                }
            } catch {
                print("❌ [OnboardingFlowView] Onboarding submission failed: \(error)")
                await MainActor.run {
                    isSubmitting = false
                    errorMessage = "Failed to save your information. Please try again."
                }
            }
        }
    }
}


