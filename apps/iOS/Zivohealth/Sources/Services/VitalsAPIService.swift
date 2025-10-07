import Foundation
import Combine
import SwiftUI

// MARK: - Data Models
enum VitalMetricType: String, CaseIterable, Codable {
    case heartRate = "Heart Rate"
    case bloodPressureSystolic = "Blood Pressure Systolic"
    case bloodPressureDiastolic = "Blood Pressure Diastolic"
    case bloodSugar = "Blood Sugar"
    case bodyTemperature = "Temperature"
    case bodyMass = "Weight"
    case height = "Height"
    case bmi = "BMI"
    case oxygenSaturation = "Oxygen Saturation"
    case stepCount = "Steps"
    case standTime = "Stand Hours"
    case activeEnergy = "Active Energy"
    case flightsClimbed = "Flights Climbed"
    case workouts = "Workouts"
    case workoutDuration = "Workout Duration"
    case workoutCalories = "Workout Calories"
    case workoutDistance = "Workout Distance"
    case sleep = "Sleep"
    case distanceWalking = "Distance Walking"
}

enum VitalDataSource: String, CaseIterable, Codable {
    case appleHealthKit = "apple_healthkit"
    case manualEntry = "manual_entry"
    case documentExtraction = "document_extraction"
    case deviceSync = "device_sync"
    case apiImport = "api_import"
}

enum TimeGranularity: String, CaseIterable, Codable {
    case daily = "daily"
    case weekly = "weekly"
    case monthly = "monthly"
}

struct VitalDataSubmission: Codable {
    let metricType: VitalMetricType
    let value: Double
    let unit: String
    let startDate: Date
    let endDate: Date
    let dataSource: VitalDataSource
    let notes: String?
    let sourceDevice: String?
    let confidenceScore: Double?
    
    enum CodingKeys: String, CodingKey {
        case metricType = "metric_type"
        case value
        case unit
        case startDate = "start_date"
        case endDate = "end_date"
        case dataSource = "data_source"
        case notes
        case sourceDevice = "source_device"
        case confidenceScore = "confidence_score"
    }
}

struct VitalBulkSubmission: Codable {
    let data: [VitalDataSubmission]
    let chunkInfo: ChunkInfo?
    
    enum CodingKeys: String, CodingKey {
        case data
        case chunkInfo = "chunk_info"
    }
}

struct ChunkInfo: Codable {
    let sessionId: String
    let chunkNumber: Int
    let totalChunks: Int
    let isFinalChunk: Bool
    
    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case chunkNumber = "chunk_number"
        case totalChunks = "total_chunks"
        case isFinalChunk = "is_final_chunk"
    }
}

struct ChartDataPoint: Codable {
    let date: String
    let value: Double
    let minValue: Double?
    let maxValue: Double?
    let label: String?
    let source: VitalDataSource?
    let workoutBreakdown: [String: Double]?
    
    enum CodingKeys: String, CodingKey {
        case date
        case value
        case minValue = "min_value"
        case maxValue = "max_value"
        case label
        case source
        case workoutBreakdown = "workout_breakdown"
    }
    
    init(date: String, value: Double, minValue: Double? = nil, maxValue: Double? = nil, label: String? = nil, source: VitalDataSource? = nil, workoutBreakdown: [String: Double]? = nil) {
        self.date = date
        self.value = value
        self.minValue = minValue
        self.maxValue = maxValue
        self.label = label
        self.source = source
        self.workoutBreakdown = workoutBreakdown
    }
}

struct ChartData: Codable {
    let metricType: VitalMetricType
    let unit: String
    let granularity: TimeGranularity
    let dataPoints: [ChartDataPoint]
    let minValue: Double?
    let maxValue: Double?
    let averageValue: Double?
    let totalValue: Double?
    
    enum CodingKeys: String, CodingKey {
        case metricType = "metric_type"
        case unit
        case granularity
        case dataPoints = "data_points"
        case minValue = "min_value"
        case maxValue = "max_value"
        case averageValue = "average_value"
        case totalValue = "total_value"
    }
}

struct VitalMetricsChartsResponse: Codable {
    let userId: Int
    let charts: [ChartData]
    let dateRange: [String: String]
    
    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case charts
        case dateRange = "date_range"
    }
}

struct VitalAggregateData: Codable {
    let metricType: VitalMetricType
    let date: String?
    let weekStartDate: String?
    let year: Int?
    let month: Int?
    let totalValue: Double?
    let averageValue: Double?
    let minValue: Double?
    let maxValue: Double?
    let count: Int
    let durationMinutes: Double?
    let unit: String
    let notes: String?
    let workoutBreakdown: [String: Double]?
    
    enum CodingKeys: String, CodingKey {
        case metricType = "metric_type"
        case date
        case weekStartDate = "week_start_date"
        case year
        case month
        case totalValue = "total_value"
        case averageValue = "average_value"
        case minValue = "min_value"
        case maxValue = "max_value"
        case count
        case durationMinutes = "duration_minutes"
        case unit
        case notes
        case workoutBreakdown = "workout_breakdown"
    }
}

struct VitalMetricSummary: Codable {
    let metricType: VitalMetricType
    let unit: String
    let latestValue: Double?
    let latestDate: Date?
    let dataPoints: [VitalAggregateData]
    
    enum CodingKeys: String, CodingKey {
        case metricType = "metric_type"
        case unit
        case latestValue = "latest_value"
        case latestDate = "latest_date"
        case dataPoints = "data_points"
    }
}

struct VitalDashboard: Codable {
    let userId: Int
    let lastSync: Date?
    let metrics: [VitalMetricSummary]
    
    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case lastSync = "last_sync"
        case metrics
    }
}

struct VitalSubmissionResponse: Codable {
    let success: Bool
    let message: String
    let processedCount: Int
    let errors: [String]?
    
    enum CodingKeys: String, CodingKey {
        case success
        case message
        case processedCount = "processed_count"
        case errors
    }
}

struct VitalSyncStatus: Codable {
    let userId: Int
    let syncEnabled: String
    let lastSyncDate: Date?
    let lastSuccessfulSync: Date?
    let lastError: String?
    let errorCount: Int
    
    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case syncEnabled = "sync_enabled"
        case lastSyncDate = "last_sync_date"
        case lastSuccessfulSync = "last_successful_sync"
        case lastError = "last_error"
        case errorCount = "error_count"
    }
}

struct VitalDataCount: Codable {
    let userId: Int
    let totalCount: Int
    let countsByMetric: [String: Int]
    let dateRange: DateRange
    let latestDataTimestamp: Date?
    
    struct DateRange: Codable {
        let startDate: String
        let endDate: String
        let days: Int
        
        enum CodingKeys: String, CodingKey {
            case startDate = "start_date"
            case endDate = "end_date"
            case days
        }
    }
    
    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case totalCount = "total_count"
        case countsByMetric = "counts_by_metric"
        case dateRange = "date_range"
        case latestDataTimestamp = "latest_data_timestamp"
    }
}

// MARK: - API Service

final class VitalsAPIService: ObservableObject, @unchecked Sendable {
    static let shared = VitalsAPIService()
    
    @AppStorage("apiEndpoint") private var apiEndpoint = AppConfig.defaultAPIEndpoint
    private var baseURL: String {
        return "\(apiEndpoint)/api/v1/vitals"
    }
    private var cancellables = Set<AnyCancellable>()
    
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    private init() {}
    
    // MARK: - Date Encoder/Decoder
    private func createDateEncoder() -> JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }
    
    private func createDateDecoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let dateString = try container.decode(String.self)
            
            // Try multiple date formats
            let formatters = [
                // ISO8601 format with timezone
                { () -> DateFormatter in
                    let formatter = DateFormatter()
                    formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSZ"
                    formatter.locale = Locale(identifier: "en_US_POSIX")
                    return formatter
                }(),
                // ISO8601 format with 6 decimal places (microseconds): "2025-06-06T17:07:48.045356"
                { () -> DateFormatter in
                    let formatter = DateFormatter()
                    formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
                    formatter.locale = Locale(identifier: "en_US_POSIX")
                    return formatter
                }(),
                // ISO8601 format with 3 decimal places (milliseconds): "2025-06-06T17:07:48.045"
                { () -> DateFormatter in
                    let formatter = DateFormatter()
                    formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSS"
                    formatter.locale = Locale(identifier: "en_US_POSIX")
                    return formatter
                }(),
                // ISO8601 format without decimal places: "2025-06-06T10:18:18"
                { () -> DateFormatter in
                    let formatter = DateFormatter()
                    formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
                    formatter.locale = Locale(identifier: "en_US_POSIX")
                    return formatter
                }(),
                // Backend format with 3 decimal places: "2025-06-05 23:12:25.000"
                { () -> DateFormatter in
                    let formatter = DateFormatter()
                    formatter.dateFormat = "yyyy-MM-dd HH:mm:ss.SSS"
                    formatter.locale = Locale(identifier: "en_US_POSIX")
                    return formatter
                }(),
                // Backend format with 2 decimal places: "2025-06-05 23:12:25.00"
                { () -> DateFormatter in
                    let formatter = DateFormatter()
                    formatter.dateFormat = "yyyy-MM-dd HH:mm:ss.SS"
                    formatter.locale = Locale(identifier: "en_US_POSIX")
                    return formatter
                }(),
                // Backend format with 1 decimal place: "2025-06-05 23:12:25.0"
                { () -> DateFormatter in
                    let formatter = DateFormatter()
                    formatter.dateFormat = "yyyy-MM-dd HH:mm:ss.S"
                    formatter.locale = Locale(identifier: "en_US_POSIX")
                    return formatter
                }(),
                // Backend format without decimals: "2025-06-05 23:12:25"
                { () -> DateFormatter in
                    let formatter = DateFormatter()
                    formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
                    formatter.locale = Locale(identifier: "en_US_POSIX")
                    return formatter
                }(),
                // Simple date format: "2025-06-05"
                { () -> DateFormatter in
                    let formatter = DateFormatter()
                    formatter.dateFormat = "yyyy-MM-dd"
                    formatter.locale = Locale(identifier: "en_US_POSIX")
                    return formatter
                }()
            ]
            
            for formatter in formatters {
                if let date = formatter.date(from: dateString) {
                    return date
                }
            }
            
            throw DecodingError.dataCorrupted(
                DecodingError.Context(
                    codingPath: decoder.codingPath,
                    debugDescription: "Cannot decode date from: \(dateString)"
                )
            )
        }
        return decoder
    }
    
    // MARK: - Authentication Headers
    private func getAuthHeaders() -> [String: String] {
        // Always include API key, JWT, and HMAC via NetworkService
        let headers = NetworkService.shared.authHeaders(requiresAuth: true, body: nil)
        if let token = headers["Authorization"] { print("🔍 [VitalsAPIService] Using auth token header: \(token.prefix(16))...") }
        return headers
    }
    
    // MARK: - Demo Authentication
    private func authenticateWithDemoCredentials() async {
        print("🔐 [VitalsAPIService] Attempting demo authentication...")
        do {
            // Use demo patient credentials
            try await NetworkService.shared.forceReauthentication()
            print("✅ [VitalsAPIService] Demo authentication successful")
        } catch {
            print("❌ [VitalsAPIService] Demo authentication failed: \(error)")
        }
    }
    
    // MARK: - Data Submission
    func submitHealthData(_ data: VitalDataSubmission) -> AnyPublisher<VitalSubmissionResponse, Error> {
        guard let url = URL(string: "\(baseURL)/submit") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        do {
            request.httpBody = try createDateEncoder().encode(data)
        } catch {
            return Fail(error: error)
                .eraseToAnyPublisher()
        }
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: VitalSubmissionResponse.self, decoder: createDateDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    func submitBulkHealthData(_ data: [VitalDataSubmission]) -> AnyPublisher<VitalSubmissionResponse, Error> {
        return submitBulkHealthData(data, chunkInfo: nil)
    }
    
    func submitBulkHealthData(_ data: [VitalDataSubmission], chunkInfo: ChunkInfo?) -> AnyPublisher<VitalSubmissionResponse, Error> {
        guard let url = URL(string: "\(baseURL)/bulk-submit") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        let bulkData = VitalBulkSubmission(data: data, chunkInfo: chunkInfo)
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        do {
            request.httpBody = try createDateEncoder().encode(bulkData)
        } catch {
            return Fail(error: error)
                .eraseToAnyPublisher()
        }
        
        // Create URLSession with longer timeout for bulk uploads
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 120.0  // 2 minutes
        config.timeoutIntervalForResource = 300.0  // 5 minutes
        let session = URLSession(configuration: config)
        
        return session.dataTaskPublisher(for: request)
            .tryMap { data, response in
                // Check for HTTP errors first
                if let httpResponse = response as? HTTPURLResponse {
                    if httpResponse.statusCode == 401 {
                        throw URLError(.userAuthenticationRequired)
                    } else if httpResponse.statusCode >= 400 {
                        // Try to parse error response
                        if let errorData = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                           let message = errorData["message"] as? String {
                            throw NSError(domain: "APIError", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: message])
                        } else {
                            throw URLError(.badServerResponse)
                        }
                    }
                }
                return data
            }
            .decode(type: VitalSubmissionResponse.self, decoder: createDateDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    // MARK: - Data Retrieval
    func getDashboard() -> AnyPublisher<VitalDashboard, Error> {
        guard let url = URL(string: "\(baseURL)/dashboard") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.allHTTPHeaderFields = getAuthHeaders()
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .tryMap { data, response in
                // Check for HTTP errors first
                if let httpResponse = response as? HTTPURLResponse {
                    print("🔍 [VitalsAPIService] Dashboard response status: \(httpResponse.statusCode)")
                    if httpResponse.statusCode == 401 {
                        throw URLError(.userAuthenticationRequired)
                    } else if httpResponse.statusCode >= 400 {
                        // Try to parse error response
                        if let errorData = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                           let message = errorData["message"] as? String {
                            print("❌ [VitalsAPIService] Dashboard API error: \(message)")
                            throw NSError(domain: "APIError", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: message])
                        } else {
                            print("❌ [VitalsAPIService] Dashboard bad server response")
                            throw URLError(.badServerResponse)
                        }
                    }
                }
                
                // Log first few characters of response for debugging
                if let responseString = String(data: data, encoding: .utf8) {
                    let preview = String(responseString.prefix(200))
                    print("🔍 [VitalsAPIService] Dashboard response preview: \(preview)")
                }
                
                return data
            }
            .decode(type: VitalDashboard.self, decoder: createDateDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    func getChartData(
        for metricType: VitalMetricType,
        granularity: TimeGranularity = .daily,
        days: Int = 30
    ) -> AnyPublisher<ChartData, Error> {
        // Encode metric type for URL
        let encodedMetricType = metricType.rawValue.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? metricType.rawValue
        guard let url = URL(string: "\(baseURL)/charts?metric_types=\(encodedMetricType)&granularity=\(granularity.rawValue)&days=\(days)") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.allHTTPHeaderFields = getAuthHeaders()
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: VitalMetricsChartsResponse.self, decoder: createDateDecoder())
            .compactMap { response in
                // Find the chart for the requested metric type
                return response.charts.first { $0.metricType == metricType }
            }
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    func getSyncStatus() -> AnyPublisher<VitalSyncStatus, Error> {
        guard let url = URL(string: "\(baseURL)/sync-status/apple_healthkit") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.allHTTPHeaderFields = getAuthHeaders()
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .tryMap { data, response in
                // Check for HTTP errors first
                if let httpResponse = response as? HTTPURLResponse {
                    if httpResponse.statusCode == 401 {
                        throw URLError(.userAuthenticationRequired)
                    } else if httpResponse.statusCode >= 400 {
                        // Try to parse error response
                        if let errorData = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                           let message = errorData["message"] as? String {
                            throw NSError(domain: "APIError", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: message])
                        } else {
                            throw URLError(.badServerResponse)
                        }
                    }
                }
                return data
            }
            .decode(type: VitalSyncStatus.self, decoder: createDateDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    func getDataCount(days: Int = 30) -> AnyPublisher<VitalDataCount, Error> {
        guard let url = URL(string: "\(baseURL)/data-count?days=\(days)") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.allHTTPHeaderFields = getAuthHeaders()
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .tryMap { data, response in
                if let httpResponse = response as? HTTPURLResponse {
                    if httpResponse.statusCode == 401 {
                        throw URLError(.userAuthenticationRequired)
                    } else if httpResponse.statusCode >= 400 {
                        if let errorData = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                           let message = errorData["message"] as? String {
                            throw NSError(domain: "APIError", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: message])
                        } else {
                            throw URLError(.badServerResponse)
                        }
                    }
                }
                return data
            }
            .decode(type: VitalDataCount.self, decoder: createDateDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    // MARK: - Sync Control
    func enableSync() -> AnyPublisher<Void, Error> {
        guard let url = URL(string: "\(baseURL)/sync-status/apple_healthkit/enable") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map { _ in () }
            .mapError { $0 as Error }
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    func disableSync() -> AnyPublisher<Void, Error> {
        guard let url = URL(string: "\(baseURL)/sync-status/apple_healthkit/disable") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map { _ in () }
            .mapError { $0 as Error }
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    // MARK: - Aggregation
    func triggerAggregation() -> AnyPublisher<[String: Any], Error> {
        // Add today's date as the target date for aggregation
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"
        let todayString = dateFormatter.string(from: Date())
        
        guard let url = URL(string: "\(baseURL)/aggregate/\(todayString)") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .tryMap { data, response in
                if let httpResponse = response as? HTTPURLResponse {
                    print("🔍 [VitalsAPIService] Aggregation response status: \(httpResponse.statusCode)")
                    if httpResponse.statusCode == 401 {
                        throw URLError(.userAuthenticationRequired)
                    } else if httpResponse.statusCode >= 400 {
                        if let errorData = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                           let message = errorData["message"] as? String {
                            throw NSError(domain: "APIError", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: message])
                        } else {
                            throw URLError(.badServerResponse)
                        }
                    }
                }
                
                // Parse the JSON response
                if let jsonResponse = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    return jsonResponse
                } else {
                    return ["success": true, "message": "Aggregation triggered"]
                }
            }
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    // MARK: - Helper Methods
    func convertHealthMetricToSubmission(_ metric: HealthMetric) -> VitalDataSubmission? {
        let metricType: VitalMetricType
        
        switch metric.type {
        case "Blood Pressure":
            // For blood pressure, we need to handle systolic and diastolic separately
            // This is a simplified approach - you might want to parse the value differently
            metricType = .bloodPressureSystolic
        case "Heart Rate":
            metricType = .heartRate
        case "Blood Sugar":
            metricType = .bloodSugar
        case "Temperature":
            metricType = .bodyTemperature
        case "Weight":
            metricType = .bodyMass
        case "Height":
            metricType = .height
        case "BMI":
            metricType = .bmi
        case "Oxygen Saturation":
            metricType = .oxygenSaturation
        case "Steps":
            metricType = .stepCount
        case "Stand Hours":
            metricType = .standTime
        case "Active Energy":
            metricType = .activeEnergy
        case "Workouts":
            metricType = .workouts
        case "Sleep":
            metricType = .sleep
        case "Flights Climbed":
            metricType = .flightsClimbed
        default:
            return nil
        }
        
        return VitalDataSubmission(
            metricType: metricType,
            value: metric.value,
            unit: metric.unit,
            startDate: metric.date,
            endDate: metric.date,
            dataSource: .appleHealthKit,
            notes: metric.notes,
            sourceDevice: "iPhone",
            confidenceScore: nil
        )
    }
} 