import Foundation
import Combine
import SwiftUI

class NutritionAPIService: ObservableObject {
    static let shared = NutritionAPIService()
    
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    @AppStorage("apiEndpoint") private var apiEndpoint = AppConfig.defaultAPIEndpoint
    
    private var baseURL: String {
        return "\(apiEndpoint)/api/v1/nutrition"
    }
    
    private var agentURL: String {
        return "\(apiEndpoint)/api/v1/agents"
    }
    
    private var cancellables = Set<AnyCancellable>()
    
    private init() {}
    
    // MARK: - Authentication Headers
    private func getAuthHeaders() -> [String: String] {
        return NetworkService.shared.authHeaders(requiresAuth: true, body: nil)
    }
    
    // MARK: - Demo Authentication
    private func authenticateWithDemoCredentials() async {
        print("🔐 [NutritionAPIService] Attempting demo authentication...")
        do {
            // Use demo patient credentials
            try await NetworkService.shared.forceReauthentication()
            print("✅ [NutritionAPIService] Demo authentication successful")
        } catch {
            print("❌ [NutritionAPIService] Demo authentication failed: \(error)")
        }
    }
    
    // MARK: - Analyze Food Image with Nutrition Agent
    func analyzeFoodImage(imageData: Data, mealType: MealType = .other) -> AnyPublisher<NutritionAnalysisResponse, Error> {
        guard let url = URL(string: "\(agentURL)/nutrition/analyze") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        // Create multipart form data
        let boundary = UUID().uuidString
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
        var headers = getAuthHeaders()
        headers["Content-Type"] = "multipart/form-data; boundary=\(boundary)"
        request.allHTTPHeaderFields = headers
        
        var formData = Data()
        
        // Add image file
        formData.append("--\(boundary)\r\n".data(using: .utf8)!)
        formData.append("Content-Disposition: form-data; name=\"file\"; filename=\"food_image.jpg\"\r\n".data(using: .utf8)!)
        formData.append("Content-Type: image/jpeg\r\n\r\n".data(using: .utf8)!)
        formData.append(imageData)
        formData.append("\r\n".data(using: .utf8)!)
        
        // Add meal type
        formData.append("--\(boundary)\r\n".data(using: .utf8)!)
        formData.append("Content-Disposition: form-data; name=\"meal_type\"\r\n\r\n".data(using: .utf8)!)
        formData.append(mealType.rawValue.data(using: .utf8)!)
        formData.append("\r\n".data(using: .utf8)!)
        
        // Add message
        formData.append("--\(boundary)\r\n".data(using: .utf8)!)
        formData.append("Content-Disposition: form-data; name=\"message\"\r\n\r\n".data(using: .utf8)!)
        formData.append("Please analyze this food image and extract nutritional information.".data(using: .utf8)!)
        formData.append("\r\n".data(using: .utf8)!)
        
        formData.append("--\(boundary)--\r\n".data(using: .utf8)!)
        
        request.httpBody = formData
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: NutritionAnalysisResponse.self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    // MARK: - Create Nutrition Data
    func createNutritionData(_ data: NutritionDataCreate) -> AnyPublisher<NutritionDataResponse, Error> {
        guard let url = URL(string: "\(baseURL)/data") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        do {
            request.httpBody = try JSONEncoder().encode(data)
        } catch {
            return Fail(error: error)
                .eraseToAnyPublisher()
        }
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: NutritionDataResponse.self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    // MARK: - Get Nutrition Data
    func getNutritionData(
        startDate: Date? = nil,
        endDate: Date? = nil,
        mealType: MealType? = nil,
        source: NutritionDataSource? = nil,
        granularity: NutritionTimeGranularity = .daily,
        limit: Int = 100,
        offset: Int = 0
    ) -> AnyPublisher<[NutritionDataResponse], Error> {
        
        var components = URLComponents(string: "\(baseURL)/data")!
        var queryItems: [URLQueryItem] = []
        
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"
        
        if let startDate = startDate {
            queryItems.append(URLQueryItem(name: "start_date", value: dateFormatter.string(from: startDate)))
        }
        if let endDate = endDate {
            queryItems.append(URLQueryItem(name: "end_date", value: dateFormatter.string(from: endDate)))
        }
        if let mealType = mealType {
            queryItems.append(URLQueryItem(name: "meal_type", value: mealType.rawValue))
        }
        if let source = source {
            queryItems.append(URLQueryItem(name: "data_source", value: source.rawValue))
        }
        
        queryItems.append(URLQueryItem(name: "granularity", value: granularity.rawValue))
        queryItems.append(URLQueryItem(name: "limit", value: String(limit)))
        queryItems.append(URLQueryItem(name: "offset", value: String(offset)))
        
        components.queryItems = queryItems
        
        guard let url = components.url else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .tryMap { data, response in
                if let httpResponse = response as? HTTPURLResponse {
                    print("🌐 [NutritionAPIService] getNutritionData response: \(httpResponse.statusCode)")
                    if httpResponse.statusCode == 403 {
                        print("🔐 [NutritionAPIService] Authentication failed, triggering re-authentication")
                        Task {
                            await self.authenticateWithDemoCredentials()
                        }
                        throw URLError(.userAuthenticationRequired)
                    }
                    if httpResponse.statusCode >= 400 {
                        let errorString = String(data: data, encoding: .utf8) ?? "Unknown error"
                        print("❌ [NutritionAPIService] HTTP \(httpResponse.statusCode): \(errorString)")
                        throw URLError(.badServerResponse)
                    }
                }
                return data
            }
            .decode(type: [NutritionDataResponse].self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    // MARK: - Get Chart Data
    func getNutritionChartData(
        startDate: Date,
        endDate: Date,
        granularity: NutritionTimeGranularity = .daily
    ) -> AnyPublisher<NutritionChartData, Error> {
        
        var components = URLComponents(string: "\(baseURL)/chart")!
        var queryItems: [URLQueryItem] = []
        
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"
        
        queryItems.append(URLQueryItem(name: "start_date", value: dateFormatter.string(from: startDate)))
        queryItems.append(URLQueryItem(name: "end_date", value: dateFormatter.string(from: endDate)))
        queryItems.append(URLQueryItem(name: "granularity", value: granularity.rawValue))
        
        components.queryItems = queryItems
        
        guard let url = components.url else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .tryMap { data, response in
                if let httpResponse = response as? HTTPURLResponse {
                    print("🌐 [NutritionAPIService] getNutritionChartData response: \(httpResponse.statusCode)")
                    if httpResponse.statusCode == 403 {
                        print("🔐 [NutritionAPIService] Authentication failed, triggering re-authentication")
                        Task {
                            await self.authenticateWithDemoCredentials()
                        }
                        throw URLError(.userAuthenticationRequired)
                    }
                    if httpResponse.statusCode >= 400 {
                        let errorString = String(data: data, encoding: .utf8) ?? "Unknown error"
                        print("❌ [NutritionAPIService] HTTP \(httpResponse.statusCode): \(errorString)")
                        throw URLError(.badServerResponse)
                    }
                }
                return data
            }
            .decode(type: NutritionChartData.self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    // MARK: - Delete Nutrition Data
    func deleteNutritionData(id: Int) -> AnyPublisher<Void, Error> {
        guard let url = URL(string: "\(baseURL)/data/\(id)") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map { _ in () }
            .mapError { $0 as Error }
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    // MARK: - Bulk Create Nutrition Data
    func bulkCreateNutritionData(_ nutritionDataList: [NutritionDataCreate]) -> AnyPublisher<Void, Error> {
        let publishers = nutritionDataList.map { nutritionData in
            createNutritionData(nutritionData)
                .map { _ in () }
                .eraseToAnyPublisher()
        }
        
        return Publishers.MergeMany(publishers)
            .collect()
            .map { _ in () }
            .eraseToAnyPublisher()
    }
}

// MARK: - Convenience Extensions
extension NutritionAPIService {
    func getTodaysNutrition() -> AnyPublisher<[NutritionDataResponse], Error> {
        let today = Date()
        return getNutritionData(
            startDate: Calendar.current.startOfDay(for: today),
            endDate: today,
            granularity: .daily
        )
    }
    
    func getFiveDayNutrition() -> AnyPublisher<NutritionChartData, Error> {
        let calendar = Calendar.current
        let today = Date()
        let fourDaysAgo = calendar.date(byAdding: .day, value: -4, to: today) ?? today
        
        return getNutritionChartData(
            startDate: fourDaysAgo,
            endDate: today,
            granularity: .daily
        )
    }
    
    func getMonthlyNutrition() -> AnyPublisher<NutritionChartData, Error> {
        let calendar = Calendar.current
        let today = Date()
        let monthAgo = calendar.date(byAdding: .month, value: -1, to: today) ?? today
        
        return getNutritionChartData(
            startDate: monthAgo,
            endDate: today,
            granularity: .weekly
        )
    }
}
