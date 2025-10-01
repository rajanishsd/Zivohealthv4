import SwiftUI

struct ConsentsView: View {
    @ObservedObject var vm: OnboardingViewModel

    var body: some View {
        Form {
            Toggle("Consent to store health and nutrition data", isOn: $vm.consentDataStorage)
            Toggle("Consent to receive recommendations and reminders", isOn: $vm.consentRecommendations)
            Toggle("Acknowledge Terms & Privacy Policy", isOn: $vm.consentTermsPrivacy)
        }
    }
}


