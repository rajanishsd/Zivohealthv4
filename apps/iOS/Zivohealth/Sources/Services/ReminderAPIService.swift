import Foundation

struct ReminderDeviceRegistration: Codable {
    let user_id: String
    let platform: String
    let fcm_token: String
}

final class ReminderAPIService {
    static let shared = ReminderAPIService()
    private init() {}

    // Configure these via AppConfig if available
    private var baseURL: String {
        switch AppConfig.Environment.current {
        case .local:
            return "http://192.168.0.105:8085/api/v1/reminders"
        case .staging:
            return "https://staging-api.zivohealth.ai/api/v1/reminders"
        case .production:
            return "https://api.zivohealth.ai/api/v1/reminders"
        }
    }

    func registerDevice(userId: String, fcmToken: String, apiKey: String, completion: ((Error?) -> Void)? = nil) {
        let payload = ReminderDeviceRegistration(user_id: userId, platform: "ios", fcm_token: fcmToken)
        guard let url = URL(string: baseURL + "/devices") else {
            completion?(NSError(domain: "ReminderAPI", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid URL"]))
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(apiKey, forHTTPHeaderField: "x-api-key")
        request.httpBody = try? JSONEncoder().encode(payload)

        URLSession.shared.dataTask(with: request) { _, _, error in
            completion?(error)
        }.resume()
    }
}


