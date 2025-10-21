import Foundation
import Combine

// Note: Avoid defining AnyCodable here to prevent ambiguity with existing models.

final class HealthScoreAPIService: ObservableObject {
    static let shared = HealthScoreAPIService()
    private init() {}
    // Avoid AppStorage to keep service decoupled from SwiftUI property wrappers
    private var apiEndpoint: String { AppConfig.defaultAPIEndpoint }

    // MARK: - Authentication Guards
    /// Check if user is authenticated before making API calls
    private func ensureAuthenticated() throws {
        guard NetworkService.shared.isAuthenticated() else {
            print("⚠️ [HealthScoreAPIService] User not authenticated - skipping API call")
            throw URLError(.userAuthenticationRequired)
        }
    }

    func getToday() -> AnyPublisher<[String: Any], Error> {
        // Guard: Check authentication first
        do {
            try ensureAuthenticated()
        } catch {
            return Fail(error: error).eraseToAnyPublisher()
        }
        
        let url = URL(string: "\(apiEndpoint)/api/v1/health-score/today")!
        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        let headers = NetworkService.shared.authHeaders(requiresAuth: true, body: nil)
        headers.forEach { key, value in req.setValue(value, forHTTPHeaderField: key) }
        return URLSession.shared.dataTaskPublisher(for: req)
            .map(\.data)
            .tryMap { data in
                try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
            }
            .eraseToAnyPublisher()
    }

    func getRange(start: String, end: String) -> AnyPublisher<[[String: Any]], Error> {
        // Guard: Check authentication first
        do {
            try ensureAuthenticated()
        } catch {
            return Fail(error: error).eraseToAnyPublisher()
        }
        
        let url = URL(string: "\(apiEndpoint)/api/v1/health-score/range?start=\(start)&end=\(end)")!
        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        let headers = NetworkService.shared.authHeaders(requiresAuth: true, body: nil)
        headers.forEach { key, value in req.setValue(value, forHTTPHeaderField: key) }
        return URLSession.shared.dataTaskPublisher(for: req)
            .map(\.data)
            .tryMap { data in
                try JSONSerialization.jsonObject(with: data) as? [[String: Any]] ?? []
            }
            .eraseToAnyPublisher()
    }
}


