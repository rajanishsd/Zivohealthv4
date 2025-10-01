import SwiftUI

struct BasicDetailsView: View {
    @ObservedObject var vm: OnboardingViewModel

    var body: some View {
        Form {
            Section(header: Text("Contact")) {
                TextField("Email", text: $vm.email)
                    .keyboardType(.emailAddress)
                    .textInputAutocapitalization(.never)
                TextField("Phone number", text: $vm.phoneNumber)
                    .keyboardType(.phonePad)
            }
            Section(header: Text("Personal")) {
                TextField("Full name", text: $vm.fullName)
                DatePicker("Date of birth", selection: $vm.dateOfBirth, displayedComponents: .date)
                Picker("Gender", selection: $vm.gender) {
                    Text("Male").tag("male")
                    Text("Female").tag("female")
                    Text("Other").tag("other")
                }
                TextField("Height (cm)", text: $vm.heightCm).keyboardType(.numberPad)
                TextField("Weight (kg)", text: $vm.weightKg).keyboardType(.numberPad)
                Picker("Body Type", selection: $vm.bodyType) {
                    Text("None").tag("")
                    Text("Ectomorph").tag("ectomorph")
                    Text("Mesomorph").tag("mesomorph")
                    Text("Endomorph").tag("endomorph")
                }
                Picker("Activity Level", selection: $vm.activityLevel) {
                    Text("None").tag("")
                    Text("Sedentary").tag("sedentary")
                    Text("Lightly Active").tag("lightly_active")
                    Text("Moderately Active").tag("moderately_active")
                    Text("Very Active").tag("very_active")
                    Text("Super Active").tag("super_active")
                }
                TextField("Timezone", text: $vm.timezone)
                    .textInputAutocapitalization(.never)
            }
        }
        .onAppear { vm.prefillFromGoogle() }
    }
}


