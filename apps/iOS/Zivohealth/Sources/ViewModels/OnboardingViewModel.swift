import Foundation
import SwiftUI

@MainActor
class OnboardingViewModel: ObservableObject {
    // Basic
    @Published var fullName: String = ""
    @Published var firstName: String = ""
    @Published var middleName: String = ""
    @Published var lastName: String = ""
    @Published var dateOfBirth: Date = Date()
    @Published var gender: String = ""
    @Published var heightCm: String = ""
    @Published var weightKg: String = ""
    @Published var bodyType: String = ""
    @Published var activityLevel: String = ""
    @Published var timezone: String = TimeZone.current.identifier
    @Published var timezoneId: Int? = nil
    @Published var availableTimezones: [Timezone] = []
    @Published var email: String = ""
    @Published var phoneNumber: String = ""
    @Published var selectedCountryCodeId: Int? = nil
    @Published var availableCountryCodes: [CountryCode] = []
    @Published var phoneMinDigits: Int = 10
    @Published var phoneMaxDigits: Int = 15

    // Conditions
    @Published var selectedConditions: Set<String> = []
    @Published var otherConditionText: String = ""
    @Published var selectedAllergies: Set<String> = []
    @Published var otherAllergyText: String = ""

    // Lifestyle
    @Published var smokes: Bool = false
    @Published var drinksAlcohol: Bool = false
    @Published var exercisesRegularly: Bool = false
    @Published var exerciseType: String = ""
    @Published var exerciseFrequencyPerWeek: Int = 0

    // Notifications
    @Published var windowStart: Date = Calendar.current.date(bySettingHour: 7, minute: 0, second: 0, of: Date()) ?? Date()
    @Published var windowEnd: Date = Calendar.current.date(bySettingHour: 9, minute: 0, second: 0, of: Date()) ?? Date()
    @Published var emailEnabled: Bool = true
    @Published var smsEnabled: Bool = false
    @Published var pushEnabled: Bool = true

    // Consents
    @Published var consentDataStorage: Bool = false
    @Published var consentRecommendations: Bool = false
    @Published var consentTermsPrivacy: Bool = false

    @MainActor
    func prefillFromGoogle() {
        if let profile = GoogleSignInService.shared.currentUser?.profile {
            print("🔎 [OnboardingVM] Google profile present. Email=\(profile.email), name=\(profile.name ?? "<nil>") given=\(profile.givenName ?? "<nil>") family=\(profile.familyName ?? "<nil>")")
            // Always set email and fullName from Google
            email = profile.email
            fullName = profile.name ?? ""

            // Prefer structured given/family name if available
            let given = profile.givenName?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            let family = profile.familyName?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

            if !given.isEmpty { firstName = given }
            if !family.isEmpty { lastName = family }

            // Derive middle name from full name if needed
            if (middleName.isEmpty || middleName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty) || (firstName.isEmpty || lastName.isEmpty) {
                let rawName = profile.name ?? ""
                let nameString = rawName.trimmingCharacters(in: .whitespacesAndNewlines)
                if !nameString.isEmpty {
                    let parts = nameString.split(separator: " ").map(String.init)
                    if firstName.isEmpty, let first = parts.first { firstName = first }
                    if lastName.isEmpty, parts.count > 1 { lastName = parts.last ?? "" }
                    if parts.count > 2 {
                        middleName = parts[1..<(parts.count-1)].joined(separator: " ")
                    }
                }
            }

            // Final fallback: use backend stored full name if present
            if firstName.isEmpty || lastName.isEmpty {
                let backendFull = NetworkService.shared.currentUserFullName ?? ""
                if !backendFull.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    let parts = backendFull.split(separator: " ").map(String.init)
                    if firstName.isEmpty, let first = parts.first { firstName = first }
                    if lastName.isEmpty, parts.count > 1 { lastName = parts.last ?? "" }
                    if middleName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, parts.count > 2 {
                        middleName = parts[1..<(parts.count-1)].joined(separator: " ")
                    }
                }
            }

            print("✅ [OnboardingVM] Prefilled from Google: first=\(firstName), middle=\(middleName), last=\(lastName)")
        } else {
            print("ℹ️ [OnboardingVM] No Google profile found for prefilling")
        }
    }

    func prefillFromRegistration(email: String, fullName: String, firstName: String? = nil, middleName: String? = nil, lastName: String? = nil) {
        // Always set email and fullName from registration
        self.email = email
        self.fullName = fullName
        
        // Use provided split fields if available, otherwise parse from fullName
        if let firstName = firstName, !firstName.isEmpty {
            self.firstName = firstName
        } else if !fullName.isEmpty {
            let parts = fullName.split(separator: " ").map(String.init)
            if let first = parts.first { self.firstName = first }
        }
        
        if let middleName = middleName, !middleName.isEmpty {
            self.middleName = middleName
        } else if !fullName.isEmpty {
            let parts = fullName.split(separator: " ").map(String.init)
            if parts.count > 2 { self.middleName = parts[1..<(parts.count-1)].joined(separator: " ") }
        }
        
        if let lastName = lastName, !lastName.isEmpty {
            self.lastName = lastName
        } else if !fullName.isEmpty {
            let parts = fullName.split(separator: " ").map(String.init)
            if parts.count > 1 { self.lastName = parts.last ?? "" }
        }
    }

    func loadTimezones() async {
        do {
            availableTimezones = try await NetworkService.shared.fetchTimezones()
            // Set default timezone if not already set
            if timezoneId == nil {
                setDefaultTimezone()
            }
        } catch {
            print("❌ [OnboardingViewModel] Failed to load timezones: \(error)")
            // Fallback to system timezone
            setDefaultTimezone()
        }
    }
    
    private func setDefaultTimezone() {
        // Try to find current system timezone in the list
        if let currentTimezone = availableTimezones.first(where: { $0.identifier == TimeZone.current.identifier }) {
            timezoneId = currentTimezone.id
            timezone = currentTimezone.identifier
        } else {
            // Fallback to UTC if current timezone not found
            if let utcTimezone = availableTimezones.first(where: { $0.identifier == "UTC" }) {
                timezoneId = utcTimezone.id
                timezone = utcTimezone.identifier
            }
        }
    }

    // Email validation using a basic RFC 5322-like pattern
    var isValidEmail: Bool {
        let trimmed = email.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return false }
        let pattern = "^[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}$"
        let predicate = NSPredicate(format: "SELF MATCHES[c] %@", pattern)
        return predicate.evaluate(with: trimmed)
    }

    // Phone validation: allow +, digits, spaces, hyphens, parentheses; 6-32 chars and at least 10 digits
    var isValidPhoneNumber: Bool {
        let trimmed = phoneNumber.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return false }
        let allowedPattern = "^[+0-9 ()-]{6,32}$"
        let matchesAllowed = trimmed.range(of: allowedPattern, options: .regularExpression) != nil
        let digitCount = trimmed.filter { $0.isNumber }.count
        return matchesAllowed && digitCount >= phoneMinDigits && digitCount <= phoneMaxDigits
    }

    // Gender validation: must be one of male, female, other
    var isValidGender: Bool {
        let allowed = ["male", "female", "other"]
        return allowed.contains(gender)
    }

    // Height validation: integer between 30 and 300
    var isValidHeight: Bool {
        guard let h = Int(heightCm.trimmingCharacters(in: .whitespacesAndNewlines)) else { return false }
        return (30...300).contains(h)
    }

    // Weight validation: integer between 10 and 400
    var isValidWeight: Bool {
        guard let w = Int(weightKg.trimmingCharacters(in: .whitespacesAndNewlines)) else { return false }
        return (10...400).contains(w)
    }

    // Body type validation: must be selected from allowed list
    var isValidBodyType: Bool {
        let allowed = ["ectomorph", "mesomorph", "endomorph"]
        return allowed.contains(bodyType)
    }

    // Activity level validation: must be selected from allowed list
    var isValidActivityLevel: Bool {
        let allowed = ["sedentary", "lightly_active", "moderately_active", "very_active", "super_active"]
        return allowed.contains(activityLevel)
    }

    // Timezone validation: must be selected
    var isValidTimezone: Bool { timezoneId != nil && !timezone.isEmpty }

    func isValidBasics() -> Bool {
        // All required fields must be valid/non-empty to proceed
        return isValidEmail &&
        isValidPhoneNumber &&
        !firstName.isEmpty &&
        !lastName.isEmpty &&
        isValidGender &&
        isValidHeight &&
        isValidWeight &&
        isValidBodyType &&
        isValidActivityLevel &&
        isValidTimezone
    }

    // MARK: - Country Codes
    func loadCountryCodes() async {
        do {
            availableCountryCodes = try await NetworkService.shared.fetchCountryCodes()
            if selectedCountryCodeId == nil, let india = availableCountryCodes.first(where: { $0.iso2 == "IN" }) {
                selectedCountryCodeId = india.id
                phoneMinDigits = india.minDigits
                phoneMaxDigits = india.maxDigits
            }
        } catch {
            print("❌ [OnboardingViewModel] Failed to load country codes: \(error)")
        }
    }

    func buildPayload() -> [String: Any] {
        let dobStr = ISO8601DateFormatter.dateFormatterYYYYMMDD.string(from: dateOfBirth)
        let startStr = ISO8601DateFormatter.timeFormatter.string(from: windowStart)
        let endStr = ISO8601DateFormatter.timeFormatter.string(from: windowEnd)
        let composedFullName: String? = {
            let parts = [firstName.trimmingCharacters(in: .whitespaces), middleName.trimmingCharacters(in: .whitespaces), lastName.trimmingCharacters(in: .whitespaces)].filter { !$0.isEmpty }
            if !parts.isEmpty { return parts.joined(separator: " ") }
            return fullName.isEmpty ? nil : fullName
        }()

        return [
            "basic": [
                "first_name": firstName.isEmpty ? nil : firstName,
                "middle_name": middleName.isEmpty ? nil : middleName,
                "last_name": lastName.isEmpty ? nil : lastName,
                "full_name": composedFullName,
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
                "condition_names": Array(selectedConditions),
                "other_condition_text": otherConditionText.isEmpty ? nil : otherConditionText,
                "allergies": Array(selectedAllergies),
                "other_allergy_text": otherAllergyText.isEmpty ? nil : otherAllergyText,
            ],
            "lifestyle": [
                "smokes": smokes,
                "drinks_alcohol": drinksAlcohol,
                "exercises_regularly": exercisesRegularly,
                "exercise_type": exerciseType.isEmpty ? nil : exerciseType,
                "exercise_frequency_per_week": exerciseFrequencyPerWeek,
            ],
            "notifications": [
                "timezone": timezone,
                "window_start_local": startStr,
                "window_end_local": endStr,
                "email_enabled": emailEnabled,
                "sms_enabled": smsEnabled,
                "push_enabled": pushEnabled,
            ],
            "consents": [
                ["consent_type": "data_storage", "consented": consentDataStorage, "version": "v1"],
                ["consent_type": "recommendations", "consented": consentRecommendations, "version": "v1"],
                ["consent_type": "terms_privacy", "consented": consentTermsPrivacy, "version": "v1"],
            ],
        ]
    }
}

extension ISO8601DateFormatter {
    static let dateFormatterYYYYMMDD: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .iso8601)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    static let timeFormatter: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .iso8601)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "HH:mm:ss"
        return f
    }()
}


