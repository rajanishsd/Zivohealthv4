import Foundation
import SwiftUI

@MainActor
class OnboardingViewModel: ObservableObject {
    // Basic
    @Published var fullName: String = ""
    @Published var dateOfBirth: Date = Date()
    @Published var gender: String = "male"
    @Published var heightCm: String = ""
    @Published var weightKg: String = ""
    @Published var bodyType: String = ""
    @Published var activityLevel: String = ""
    @Published var timezone: String = TimeZone.current.identifier
    @Published var email: String = ""
    @Published var phoneNumber: String = ""

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

    func prefillFromGoogle() {
        if let gUser = GoogleSignInService.shared.currentUser?.profile {
            if email.isEmpty { email = gUser.email }
            if fullName.isEmpty { fullName = gUser.name ?? "" }
        }
    }
    
    func prefillFromRegistration(email: String, fullName: String) {
        if self.email.isEmpty { self.email = email }
        if self.fullName.isEmpty { self.fullName = fullName }
    }

    func isValidBasics() -> Bool {
        !email.isEmpty && !phoneNumber.isEmpty && !timezone.isEmpty
    }

    func buildPayload() -> [String: Any] {
        let dobStr = ISO8601DateFormatter.dateFormatterYYYYMMDD.string(from: dateOfBirth)
        let startStr = ISO8601DateFormatter.timeFormatter.string(from: windowStart)
        let endStr = ISO8601DateFormatter.timeFormatter.string(from: windowEnd)

        return [
            "basic": [
                "full_name": fullName.isEmpty ? nil : fullName,
                "date_of_birth": dobStr,
                "gender": gender,
                "height_cm": Int(heightCm),
                "weight_kg": Int(weightKg),
                "body_type": bodyType.isEmpty ? nil : bodyType,
                "activity_level": activityLevel.isEmpty ? nil : activityLevel,
                "timezone": timezone,
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


