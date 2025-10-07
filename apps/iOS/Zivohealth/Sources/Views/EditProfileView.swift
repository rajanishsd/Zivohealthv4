import SwiftUI

struct EditProfileView: View {
    // Basic
    @State private var firstName: String = ""
    @State private var middleName: String = ""
    @State private var lastName: String = ""
    @State private var fullName: String = ""
    @State private var email: String = ""
    @State private var phoneNumber: String = ""
    @State private var dateOfBirth: Date = Date()
    @State private var gender: String = "male"
    @State private var heightCm: String = ""
    @State private var weightKg: String = ""
    @State private var bodyType: String = ""
    @State private var activityLevel: String = ""
    @State private var timezone: String = TimeZone.current.identifier
    @State private var timezoneId: Int? = nil
    @State private var availableTimezones: [Timezone] = []
    @State private var countryCodeId: Int? = nil
    @State private var availableCountryCodes: [CountryCode] = []
    @State private var phoneMinDigits: Int = 10
    @State private var phoneMaxDigits: Int = 15

    // Health
    @State private var conditionNames: Set<String> = []
    @State private var otherConditionText: String = ""
    @State private var allergies: Set<String> = []
    @State private var otherAllergyText: String = ""

    // Lifestyle
    @State private var smokes: Bool = false
    @State private var drinksAlcohol: Bool = false
    @State private var exercisesRegularly: Bool = false
    @State private var exerciseType: String = ""
    @State private var exerciseFrequencyPerWeek: Int = 0

    @Environment(\.dismiss) private var dismiss
    @State private var isSaving: Bool = false
    @State private var errorMessage: String?
    @State private var showSuccessAlert: Bool = false

    // Options aligned with onboarding
    private let bodyTypeOptions: [(label: String, value: String)] = [
        ("None", ""), ("Ectomorph", "ectomorph"), ("Mesomorph", "mesomorph"), ("Endomorph", "endomorph")
    ]
    private let activityLevelOptions: [(label: String, value: String)] = [
        ("None", ""), ("Sedentary", "sedentary"), ("Lightly Active", "lightly_active"), ("Moderately Active", "moderately_active"), ("Very Active", "very_active"), ("Super Active", "super_active")
    ]

    var body: some View {
        Form {
            Section(header: Text("Basic")) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("First name").font(.subheadline).foregroundColor(.secondary)
                    TextField("First name", text: $firstName)
                        .textInputAutocapitalization(.words)
                }
                VStack(alignment: .leading, spacing: 4) {
                    Text("Middle name").font(.subheadline).foregroundColor(.secondary)
                    TextField("Middle name", text: $middleName)
                        .textInputAutocapitalization(.words)
                }
                VStack(alignment: .leading, spacing: 4) {
                    Text("Last name").font(.subheadline).foregroundColor(.secondary)
                    TextField("Last name", text: $lastName)
                        .textInputAutocapitalization(.words)
                }
                VStack(alignment: .leading, spacing: 4) {
                    Text("Email").font(.subheadline).foregroundColor(.secondary)
                    TextField("Email", text: $email)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        .disabled(true)
                }
                VStack(alignment: .leading, spacing: 4) {
                    Text("Phone number").font(.subheadline).foregroundColor(.secondary)
                    HStack {
                        Picker("", selection: $countryCodeId) {
                            Text("Code").tag(nil as Int?)
                            ForEach(availableCountryCodes, id: \.id) { cc in
                                Text("\(cc.dialCode) \(cc.countryName)").tag(cc.id as Int?)
                            }
                        }
                        .labelsHidden()
                        .pickerStyle(.menu)
                        .onChange(of: countryCodeId) { newId in
                            if let id = newId, let selected = availableCountryCodes.first(where: { $0.id == id }) {
                                phoneMinDigits = selected.minDigits
                                phoneMaxDigits = selected.maxDigits
                            }
                        }
                        TextField("Phone number", text: $phoneNumber)
                            .keyboardType(.phonePad)
                    }
                }
                DatePicker("Date of birth", selection: $dateOfBirth, displayedComponents: .date)
                Picker("Gender", selection: $gender) {
                    Text("Male").tag("male")
                    Text("Female").tag("female")
                    Text("Other").tag("other")
                }
                .pickerStyle(.menu)

                VStack(alignment: .leading, spacing: 4) {
                    Text("Height (cm)").font(.subheadline).foregroundColor(.secondary)
                    TextField("Height (cm)", text: $heightCm)
                        .keyboardType(.numberPad)
                }
                VStack(alignment: .leading, spacing: 4) {
                    Text("Weight (kg)").font(.subheadline).foregroundColor(.secondary)
                    TextField("Weight (kg)", text: $weightKg)
                        .keyboardType(.numberPad)
                }

                Picker("Body Type", selection: $bodyType) {
                    ForEach(bodyTypeOptions, id: \.value) { opt in
                        Text(opt.label).tag(opt.value)
                    }
                }
                .pickerStyle(.menu)

                Picker("Activity Level", selection: $activityLevel) {
                    ForEach(activityLevelOptions, id: \.value) { opt in
                        Text(opt.label).tag(opt.value)
                    }
                }
                .pickerStyle(.menu)

                VStack(alignment: .leading, spacing: 4) {
                    Text("Timezone").font(.subheadline).foregroundColor(.secondary)
                    Picker("Timezone", selection: $timezoneId) {
                        Text("Select timezone").tag(nil as Int?)
                        ForEach(availableTimezones, id: \.id) { timezone in
                            Text("\(timezone.displayName)").tag(timezone.id as Int?)
                        }
                    }
                    .onChange(of: timezoneId) { newId in
                        if let id = newId, let selectedTimezone = availableTimezones.first(where: { $0.id == id }) {
                            timezone = selectedTimezone.identifier
                        }
                    }
                }
            }

            Section(header: Text("Conditions")) {
                // Simple comma-separated entry for now; can be upgraded to chips
                TagsEditor(title: "Condition names", tags: Binding(get: { Array(conditionNames) }, set: { conditionNames = Set($0) }))
                TextField("Other condition text", text: $otherConditionText)
            }

            Section(header: Text("Allergies")) {
                TagsEditor(title: "Allergies", tags: Binding(get: { Array(allergies) }, set: { allergies = Set($0) }))
                TextField("Other allergy text", text: $otherAllergyText)
            }

            Section(header: Text("Lifestyle")) {
                Toggle("Smokes", isOn: $smokes)
                Toggle("Drinks alcohol", isOn: $drinksAlcohol)
                Toggle("Exercises regularly", isOn: $exercisesRegularly)
                VStack(alignment: .leading, spacing: 4) {
                    Text("Exercise type").font(.subheadline).foregroundColor(.secondary)
                    TextField("Exercise type", text: $exerciseType)
                }
                Stepper(value: $exerciseFrequencyPerWeek, in: 0...14) {
                    Text("Exercise frequency per week: \(exerciseFrequencyPerWeek)")
                }
            }
        }
        .navigationTitle("Edit Profile")
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                if isSaving {
                    ProgressView()
                } else {
                    Button("Save") { Task { await save() } }
                        .disabled(!isValid())
                }
            }
        }
        .alert("Error", isPresented: Binding(get: { errorMessage != nil }, set: { _ in errorMessage = nil })) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(errorMessage ?? "")
        }
        .alert("Saved", isPresented: $showSuccessAlert) {
            Button("OK") { dismiss() }
        } message: {
            Text("Your profile was updated successfully.")
        }
        .task { 
            await loadCountryCodes()
            await loadTimezones()
            await loadProfile() 
        }
    }

    private func isValid() -> Bool {
        !email.isEmpty && !phoneNumber.isEmpty && !timezone.isEmpty
    }

    private func prefillIfAvailable() {
        if let e = NetworkService.shared.currentUserEmail, !e.isEmpty { email = e }
        if let n = NetworkService.shared.currentUserFullName, !n.isEmpty { fullName = n }
    }
    
    private func loadTimezones() async {
        do {
            availableTimezones = try await NetworkService.shared.fetchTimezones()
        } catch {
            print("❌ [EditProfileView] Failed to load timezones: \(error)")
        }
    }

    private func loadCountryCodes() async {
        do {
            availableCountryCodes = try await NetworkService.shared.fetchCountryCodes()
            if countryCodeId == nil, let india = availableCountryCodes.first(where: { $0.iso2 == "IN" }) {
                countryCodeId = india.id
                phoneMinDigits = india.minDigits
                phoneMaxDigits = india.maxDigits
            }
        } catch {
            print("❌ [EditProfileView] Failed to load country codes: \(error)")
        }
    }

    private func loadProfile() async {
        do {
            let resp = try await NetworkService.shared.fetchCombinedProfile()
            let fullNameValue = resp.basic.full_name
            let firstNameValue = resp.basic.first_name
            let middleNameValue = resp.basic.middle_name ?? ""
            let lastNameValue = resp.basic.last_name ?? ""
            let emailValue = resp.basic.email
            let phoneValue = resp.basic.phone_number
            let tzValue = resp.basic.timezone
            let tzIdValue = resp.basic.timezone_id
            let genderValue = resp.basic.gender
            let heightValue = resp.basic.height_cm
            let weightValue = resp.basic.weight_kg
            let bodyTypeValue = resp.basic.body_type ?? ""
            let activityValue = resp.basic.activity_level ?? ""
            let dobValue: Date? = {
                return ISO8601DateFormatter.dateFormatterYYYYMMDD.date(from: resp.basic.date_of_birth)
            }()
            let conditionsSet = Set(resp.conditions.condition_names)
            let otherCond = resp.conditions.other_condition_text ?? ""
            let allergiesSet = Set(resp.conditions.allergies)
            let otherAllergy = resp.conditions.other_allergy_text ?? ""
            let smokesValue = resp.lifestyle.smokes
            let drinksValue = resp.lifestyle.drinks_alcohol
            let exercisesValue = resp.lifestyle.exercises_regularly
            let exerciseTypeValue = resp.lifestyle.exercise_type ?? ""
            let exerciseFreqValue = resp.lifestyle.exercise_frequency_per_week ?? 0

            await MainActor.run {
                fullName = fullNameValue
                firstName = firstNameValue
                middleName = middleNameValue
                lastName = lastNameValue
                email = emailValue
                phoneNumber = phoneValue
                timezone = tzValue ?? TimeZone.current.identifier
                timezoneId = tzIdValue
                gender = genderValue
                if let h = heightValue { heightCm = String(h) }
                if let w = weightValue { weightKg = String(w) }
                bodyType = bodyTypeValue
                activityLevel = activityValue
                if let d = dobValue { dateOfBirth = d }
                conditionNames = conditionsSet
                otherConditionText = otherCond
                allergies = allergiesSet
                otherAllergyText = otherAllergy
                smokes = smokesValue
                drinksAlcohol = drinksValue
                exercisesRegularly = exercisesValue
                exerciseType = exerciseTypeValue
                exerciseFrequencyPerWeek = exerciseFreqValue
            }
        } catch {
            await MainActor.run { prefillIfAvailable() }
        }
    }

    private func save() async {
        isSaving = true
        defer { isSaving = false }
        do {
            let startStr = ISO8601DateFormatter.timeFormatter.string(from: Calendar.current.date(bySettingHour: 7, minute: 0, second: 0, of: Date()) ?? Date())
            let endStr = ISO8601DateFormatter.timeFormatter.string(from: Calendar.current.date(bySettingHour: 21, minute: 0, second: 0, of: Date()) ?? Date())

            let dobStr = ISO8601DateFormatter.dateFormatterYYYYMMDD.string(from: dateOfBirth)
            let payload: [String: Any] = [
                "basic": [
                    "first_name": firstName.isEmpty ? nil : firstName,
                    "middle_name": middleName.isEmpty ? nil : middleName,
                    "last_name": lastName.isEmpty ? nil : lastName,
                    "full_name": fullName.isEmpty ? nil : fullName,
                    "date_of_birth": dobStr,
                    "gender": gender,
                    "height_cm": Int(heightCm),
                    "weight_kg": Int(weightKg),
                    "body_type": bodyType.isEmpty ? nil : bodyType,
                    "activity_level": activityLevel.isEmpty ? nil : activityLevel,
                    "timezone": timezone,
                    "timezone_id": timezoneId,
                    "email": email,
                    "phone_number": phoneNumber,
                ],
                "conditions": [
                    "condition_names": Array(conditionNames),
                    "other_condition_text": otherConditionText.isEmpty ? nil : otherConditionText,
                    "allergies": Array(allergies),
                    "other_allergy_text": otherAllergyText.isEmpty ? nil : otherAllergyText,
                ],
                "lifestyle": [
                    "smokes": smokes,
                    "drinks_alcohol": drinksAlcohol,
                    "exercises_regularly": exercisesRegularly,
                    "exercise_type": exerciseType.isEmpty ? nil : exerciseType,
                    "exercise_frequency_per_week": exerciseFrequencyPerWeek,
                ],
                // We intentionally don't expose consent editing, but backend requires them
                // so we resend the accepted consents as-is.
                "consents": [
                    ["consent_type": "data_storage", "consented": true, "version": "v1"],
                    ["consent_type": "recommendations", "consented": true, "version": "v1"],
                    ["consent_type": "terms_privacy", "consented": true, "version": "v1"]
                ],
                "notifications": [
                    "timezone": timezone,
                    "window_start_local": startStr,
                    "window_end_local": endStr,
                    "email_enabled": true,
                    "sms_enabled": false,
                    "push_enabled": true,
                ]
            ]

            try await NetworkService.shared.submitProfileEdit(payload: payload)
            await MainActor.run { showSuccessAlert = true }
        } catch {
            errorMessage = String(describing: error)
        }
    }
}

// Simple tags editor for entering comma-separated list and showing as chips
private struct TagsEditor: View {
    let title: String
    @Binding var tags: [String]
    @State private var input: String = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack {
                    ForEach(tags, id: \.self) { tag in
                        Text(tag)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 6)
                            .background(Color.gray.opacity(0.2))
                            .cornerRadius(12)
                    }
                }
            }
            TextField("Add comma-separated values", text: $input)
                .onSubmit {
                    commitInput()
                }
                .onChange(of: input) { _ in
                    // Split on commas
                    let parts = input.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
                    tags = parts
                }
        }
    }

    private func commitInput() {
        let parts = input.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
        tags = parts
    }
}

struct EditProfileView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView { EditProfileView() }
    }
}


