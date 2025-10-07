import SwiftUI

struct BasicDetailsView: View {
    @ObservedObject var vm: OnboardingViewModel

    var body: some View {
        Form {
            Section(header: Text("Contact")) {
                TextField("Email", text: $vm.email)
                    .keyboardType(.emailAddress)
                    .textInputAutocapitalization(.never)
                HStack {
                    Picker("", selection: $vm.selectedCountryCodeId) {
                        Text("Code").tag(nil as Int?)
                        ForEach(vm.availableCountryCodes, id: \.id) { cc in
                            Text("\(cc.dialCode) \(cc.countryName)").tag(cc.id as Int?)
                        }
                    }
                    .labelsHidden()
                    .pickerStyle(.menu)
                    .onChange(of: vm.selectedCountryCodeId) { newId in
                        if let id = newId, let selected = vm.availableCountryCodes.first(where: { $0.id == id }) {
                            vm.phoneMinDigits = selected.minDigits
                            vm.phoneMaxDigits = selected.maxDigits
                        }
                    }
                    TextField("Phone number", text: $vm.phoneNumber)
                        .keyboardType(.phonePad)
                }
            }
            Section(header: Text("Personal")) {
                TextField("First name", text: $vm.firstName)
                TextField("Middle name (optional)", text: $vm.middleName)
                TextField("Last name", text: $vm.lastName)
                DatePicker("Date of birth", selection: $vm.dateOfBirth, displayedComponents: .date)
                Picker("Gender", selection: $vm.gender) {
                    Text("None").tag("")
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
                Picker("Timezone", selection: $vm.timezoneId) {
                    Text("Select timezone").tag(nil as Int?)
                    ForEach(vm.availableTimezones, id: \.id) { timezone in
                        Text("\(timezone.displayName)").tag(timezone.id as Int?)
                    }
                }
                .onChange(of: vm.timezoneId) { newId in
                    if let id = newId, let selectedTimezone = vm.availableTimezones.first(where: { $0.id == id }) {
                        vm.timezone = selectedTimezone.identifier
                    }
                }
            }
        }
        .onAppear {
            print("🔎 [BasicDetailsView] onAppear email=\(vm.email) first=\(vm.firstName) middle=\(vm.middleName) last=\(vm.lastName)")
            Task {
                await vm.loadCountryCodes()
                await vm.loadTimezones()
            }
        }
    }
}


