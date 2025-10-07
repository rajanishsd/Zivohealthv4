import SwiftUI

struct OnboardingSettingsView: View {
    @ObservedObject var vm: OnboardingViewModel

    var body: some View {
        Form {
            DatePicker("Notification start time", selection: $vm.windowStart, displayedComponents: .hourAndMinute)
            DatePicker("Notification end time", selection: $vm.windowEnd, displayedComponents: .hourAndMinute)
            Toggle("Email notifications", isOn: $vm.emailEnabled)
            Toggle("SMS notifications", isOn: $vm.smsEnabled)
            Toggle("Push notifications", isOn: $vm.pushEnabled)
        }
    }
}


