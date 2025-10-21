import Foundation
import Combine
import SwiftUI

final class MentalHealthAPIService: ObservableObject, @unchecked Sendable {
    static let shared = MentalHealthAPIService()
    @AppStorage("apiEndpoint") private var apiEndpoint = AppConfig.defaultAPIEndpoint
    private init() {}

    private var baseURL: String { return "\(apiEndpoint)/api/v1/mental-health" }

    // MARK: - Authentication Guards
    /// Check if user is authenticated before making API calls
    private func ensureAuthenticated() throws {
        guard NetworkService.shared.isAuthenticated() else {
            print("⚠️ [MentalHealthAPIService] User not authenticated - skipping API call")
            throw URLError(.userAuthenticationRequired)
        }
    }

    private func authHeaders() -> [String: String] {
        NetworkService.shared.authHeaders(requiresAuth: true, body: nil)
    }

    // MARK: - DTOs
    struct DictionariesResponse: Decodable {
        struct Pleasantness: Decodable { let score: Int; let label: String }
        struct EntryType: Decodable { let code: String; let label: String }
        let version: Int
        let mentalhealth_feelings: [String]
        let mentalhealth_impact: [String]
        let mentalhealth_pleasantness: [Pleasantness]? // optional until backend always returns
        let mentalhealth_entry_types: [EntryType]? // optional for forward-compat
    }

    struct EntryCreatePayload: Encodable {
        let recorded_at: String
        let entry_type: String
        let pleasantness_score: Int
        let pleasantness_label: String
        let feelings: [String]
        let impacts: [String]
        let notes: String?
    }

    struct EntryResponse: Decodable {
        let id: Int
        let user_id: Int
        let recorded_at: String
        let entry_type: String
        let pleasantness_score: Int
        let pleasantness_label: String
        let feelings: [String]
        let impacts: [String]
        let notes: String?
    }

    struct RollupPoint: Decodable { let date: String; let score: Int; let label: String; let feelings: [String]; let impacts: [String] }
    struct NameCount: Decodable { let name: String; let count: Int }
    struct RollupResponse: Decodable { let data_points: [RollupPoint]; let range: String; let feelings_counts: [NameCount]?; let impacts_counts: [NameCount]? }

    // MARK: - Vitals Charts DTOs
    struct VitalsChartPoint: Decodable { let date: String; let value: Double?; let min_value: Double?; let max_value: Double? }
    struct VitalsChart: Decodable { let metric_type: String; let unit: String; let data_points: [VitalsChartPoint] }
    struct VitalsChartsResponse: Decodable { let charts: [VitalsChart] }

    // MARK: - API Calls
    func fetchDictionaries() -> AnyPublisher<DictionariesResponse, Error> {
        // Guard: Check authentication first
        do {
            try ensureAuthenticated()
        } catch {
            return Fail(error: error).eraseToAnyPublisher()
        }
        
        guard let url = URL(string: "\(baseURL)/dictionaries") else {
            return Fail(error: URLError(.badURL)).eraseToAnyPublisher()
        }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = authHeaders()
        return URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: DictionariesResponse.self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }

    func createEntry(_ payload: EntryCreatePayload) -> AnyPublisher<EntryResponse, Error> {
        // Guard: Check authentication first
        do {
            try ensureAuthenticated()
        } catch {
            return Fail(error: error).eraseToAnyPublisher()
        }
        
        guard let url = URL(string: "\(baseURL)/entries") else {
            return Fail(error: URLError(.badURL)).eraseToAnyPublisher()
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.allHTTPHeaderFields = authHeaders()
        do { request.httpBody = try JSONEncoder().encode(payload) } catch { return Fail(error: error).eraseToAnyPublisher() }
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        return URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: EntryResponse.self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }

    func getRollup(range: String) -> AnyPublisher<RollupResponse, Error> {
        // Guard: Check authentication first
        do {
            try ensureAuthenticated()
        } catch {
            return Fail(error: error).eraseToAnyPublisher()
        }
        
        var components = URLComponents(string: "\(baseURL)/rollup")!
        components.queryItems = [URLQueryItem(name: "range", value: range)]
        guard let url = components.url else { return Fail(error: URLError(.badURL)).eraseToAnyPublisher() }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = authHeaders()
        return URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: RollupResponse.self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }

    func fetchVitalsCharts(metricTypes: [String], days: Int, granularity: String = "daily") -> AnyPublisher<VitalsChartsResponse, Error> {
        // Guard: Check authentication first
        do {
            try ensureAuthenticated()
        } catch {
            return Fail(error: error).eraseToAnyPublisher()
        }
        
        print("🚨🚨🚨 [MentalHealthAPIService] fetchVitalsCharts called with: \(metricTypes), days: \(days), granularity: \(granularity) 🚨🚨🚨")
        
        var components = URLComponents(string: "\(apiEndpoint)/api/v1/vitals/charts")!
        var items: [URLQueryItem] = [
            URLQueryItem(name: "granularity", value: granularity),
            URLQueryItem(name: "days", value: String(days))
        ]
        for mt in metricTypes { items.append(URLQueryItem(name: "metric_types", value: mt)) }
        components.queryItems = items
        guard let url = components.url else { 
            print("❌ [MentalHealthAPIService] Failed to create URL")
            return Fail(error: URLError(.badURL)).eraseToAnyPublisher() 
        }
        
        print("🌐 [MentalHealthAPIService] Making API request to: \(url.absoluteString)")
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = authHeaders()
        return URLSession.shared.dataTaskPublisher(for: request)
            .map { data, response in
                print("🔄 [MentalHealthAPIService] Received response with \(data.count) bytes")
                if let httpResponse = response as? HTTPURLResponse {
                    print("🔄 [MentalHealthAPIService] HTTP status: \(httpResponse.statusCode)")
                }
                return data
            }
            .decode(type: VitalsChartsResponse.self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
}


