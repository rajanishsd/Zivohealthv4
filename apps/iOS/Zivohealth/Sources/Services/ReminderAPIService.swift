import Foundation

struct ReminderDeviceRegistration: Codable {
    let user_id: String
    let platform: String
    let fcm_token: String
}

final class ReminderAPIService: @unchecked Sendable {
    static let shared = ReminderAPIService()
    private init() {}

    // MARK: - Authentication Guards
    /// Check if user is authenticated before making API calls
    private func ensureAuthenticated() throws {
        guard NetworkService.shared.isAuthenticated() else {
            print("⚠️ [ReminderAPIService] User not authenticated - skipping API call")
            throw URLError(.userAuthenticationRequired)
        }
    }

    // Configure these via AppConfig if available
    private var baseURL: String {
        var root = AppConfig.remindersBaseURL
        if root.hasSuffix("/") {
            root.removeLast()
        }
        return root + "/api/v1/reminders"
    }

    func registerDevice(userId: String, fcmToken: String, apiKey: String, completion: ((Error?) -> Void)? = nil) {
        // Guard: Check authentication first
        do {
            try ensureAuthenticated()
        } catch {
            completion?(error)
            return
        }
        
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

        #if DEBUG
        print("🌐 [ReminderAPI] Register device → POST \(url.absoluteString)")
        #endif

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion?(error)
                return
            }
            guard let http = response as? HTTPURLResponse else {
                completion?(NSError(domain: "ReminderAPI", code: -2, userInfo: [NSLocalizedDescriptionKey: "No HTTP response"]))
                return
            }
            if (200...299).contains(http.statusCode) {
                completion?(nil)
            } else {
                var message = HTTPURLResponse.localizedString(forStatusCode: http.statusCode)
                if let data = data, let body = String(data: data, encoding: .utf8), !body.isEmpty {
                    let snippet = body.count > 300 ? String(body.prefix(300)) + "…" : body
                    message = "\(message) (status=\(http.statusCode)) - \(snippet)"
                } else {
                    message = "\(message) (status=\(http.statusCode))"
                }
                completion?(NSError(domain: "ReminderAPI", code: http.statusCode, userInfo: [NSLocalizedDescriptionKey: message]))
            }
        }.resume()
    }
}


