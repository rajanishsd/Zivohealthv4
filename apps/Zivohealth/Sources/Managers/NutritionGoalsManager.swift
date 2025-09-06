import Foundation
import Combine
import SwiftUI

class NutritionGoalsManager: ObservableObject {
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var activeGoalSummary: ActiveGoalSummary?
    @Published var progressItems: [ProgressItem] = []
    @Published var objectives: [NutritionObjective] = []
    @Published var nutrientCatalog: [NutrientCatalog] = []
    
    @AppStorage("apiEndpoint") private var apiEndpoint = AppConfig.defaultAPIEndpoint
    
    private var baseURL: String {
        return "\(apiEndpoint)/api/v1/nutrition-goals"
    }
    
    private var cancellables = Set<AnyCancellable>()
    
    // MARK: - Singleton
    static let shared = NutritionGoalsManager()
    
    private init() {}
    
    // MARK: - Authentication Headers
    private func getAuthHeaders() -> [String: String] {
        return NetworkService.shared.authHeaders(requiresAuth: true, body: nil)
    }
    
    // MARK: - API Methods
    
    /// Load the current active goal summary
    func loadActiveGoalSummary() {
        guard let url = URL(string: "\(baseURL)/current") else {
            self.errorMessage = "Invalid URL"
            return
        }
        
        isLoading = true
        errorMessage = nil
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: ActiveGoalSummary.self, decoder: JSONDecoder.nutritionGoalsDecoder)
            .receive(on: DispatchQueue.main)
            .sink(
                receiveCompletion: { [weak self] completion in
                    self?.isLoading = false
                    switch completion {
                    case .failure(let error):
                        self?.errorMessage = "Failed to load goal summary: \(error.localizedDescription)"
                        print("❌ [NutritionGoalsManager] Failed to load goal summary: \(error)")
                    case .finished:
                        break
                    }
                },
                receiveValue: { [weak self] summary in
                    self?.activeGoalSummary = summary
                    print("✅ [NutritionGoalsManager] Loaded active goal summary: \(summary.hasActiveGoal)")
                }
            )
            .store(in: &cancellables)
    }
    
    /// Load progress for the active goal
    func loadActiveGoalProgress(timeframe: String = "daily", startDate: Date? = nil, endDate: Date? = nil) {
        var urlComponents = URLComponents(string: "\(baseURL)/progress/active")!
        
        var queryItems: [URLQueryItem] = [
            URLQueryItem(name: "timeframe", value: timeframe)
        ]
        
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        
        if let start = startDate {
            queryItems.append(URLQueryItem(name: "start_date", value: formatter.string(from: start)))
        } else {
            // Default to today
            queryItems.append(URLQueryItem(name: "start_date", value: formatter.string(from: Date())))
        }
        
        if let end = endDate {
            queryItems.append(URLQueryItem(name: "end_date", value: formatter.string(from: end)))
        } else {
            // Default to today
            queryItems.append(URLQueryItem(name: "end_date", value: formatter.string(from: Date())))
        }
        
        urlComponents.queryItems = queryItems
        
        guard let url = urlComponents.url else {
            self.errorMessage = "Invalid URL"
            return
        }
        
        isLoading = true
        errorMessage = nil
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: ProgressResponse.self, decoder: JSONDecoder.nutritionGoalsDecoder)
            .receive(on: DispatchQueue.main)
            .sink(
                receiveCompletion: { [weak self] completion in
                    self?.isLoading = false
                    switch completion {
                    case .failure(let error):
                        self?.errorMessage = "Failed to load progress: \(error.localizedDescription)"
                        print("❌ [NutritionGoalsManager] Failed to load progress: \(error)")
                    case .finished:
                        break
                    }
                },
                receiveValue: { [weak self] response in
                    self?.progressItems = response.items
                    print("✅ [NutritionGoalsManager] Loaded progress items: \(response.items.count)")
                }
            )
            .store(in: &cancellables)
    }
    
    /// Load available objectives
    func loadObjectives() {
        guard let url = URL(string: "\(baseURL)/objectives") else {
            self.errorMessage = "Invalid URL"
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: [NutritionObjective].self, decoder: JSONDecoder.nutritionGoalsDecoder)
            .receive(on: DispatchQueue.main)
            .sink(
                receiveCompletion: { [weak self] completion in
                    switch completion {
                    case .failure(let error):
                        self?.errorMessage = "Failed to load objectives: \(error.localizedDescription)"
                        print("❌ [NutritionGoalsManager] Failed to load objectives: \(error)")
                    case .finished:
                        break
                    }
                },
                receiveValue: { [weak self] objectives in
                    self?.objectives = objectives
                    print("✅ [NutritionGoalsManager] Loaded objectives: \(objectives.count)")
                }
            )
            .store(in: &cancellables)
    }
    
    /// Load nutrient catalog
    func loadNutrientCatalog(enabledOnly: Bool = true) {
        var urlComponents = URLComponents(string: "\(baseURL)/catalog")!
        urlComponents.queryItems = [
            URLQueryItem(name: "enabled", value: String(enabledOnly))
        ]
        
        guard let url = urlComponents.url else {
            self.errorMessage = "Invalid URL"
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: [NutrientCatalog].self, decoder: JSONDecoder.nutritionGoalsDecoder)
            .receive(on: DispatchQueue.main)
            .sink(
                receiveCompletion: { [weak self] completion in
                    switch completion {
                    case .failure(let error):
                        self?.errorMessage = "Failed to load nutrient catalog: \(error.localizedDescription)"
                        print("❌ [NutritionGoalsManager] Failed to load catalog: \(error)")
                    case .finished:
                        break
                    }
                },
                receiveValue: { [weak self] catalog in
                    self?.nutrientCatalog = catalog
                    print("✅ [NutritionGoalsManager] Loaded nutrient catalog: \(catalog.count) items")
                }
            )
            .store(in: &cancellables)
    }
    
    /// Load all data needed for the goals card
    func loadGoalsData() {
        loadActiveGoalSummary()
        
        // Only load progress if we have an active goal
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
            if self?.activeGoalSummary?.hasActiveGoal == true {
                self?.loadActiveGoalProgress()
            }
        }
    }
}

// MARK: - JSON Decoder Extension
extension JSONDecoder {
    static var nutritionGoalsDecoder: JSONDecoder {
        let decoder = JSONDecoder()
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'"
        formatter.timeZone = TimeZone(abbreviation: "UTC")
        decoder.dateDecodingStrategy = .formatted(formatter)
        return decoder
    }
}
