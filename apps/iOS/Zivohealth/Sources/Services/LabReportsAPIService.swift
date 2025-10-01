import Foundation
import Combine
import SwiftUI

class LabReportsAPIService: ObservableObject {
    static let shared = LabReportsAPIService()
    
    @AppStorage("apiEndpoint") private var apiEndpoint = AppConfig.defaultAPIEndpoint
    
    private var baseURL: String {
        return "\(apiEndpoint)/api/v1/lab-reports"
    }
    
    var cancellables = Set<AnyCancellable>()
    
    private init() {}
    
    private func getAuthHeaders() -> [String: String] {
        return NetworkService.shared.authHeaders(requiresAuth: true, body: nil)
    }
    
    // MARK: - Demo Authentication
    private func authenticateWithDemoCredentials() async {
        print("🔐 [LabReportsAPIService] Attempting demo authentication...")
        do {
            // Use demo patient credentials
            try await NetworkService.shared.forceReauthentication()
            print("✅ [LabReportsAPIService] Demo authentication successful")
        } catch {
            print("❌ [LabReportsAPIService] Demo authentication failed: \(error)")
        }
    }
    
    func getLabCategories() -> AnyPublisher<LabCategoriesResponse, Error> {
        guard let url = URL(string: "\(baseURL)/categories") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: LabCategoriesResponse.self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    func getDiabetesPanelData() -> AnyPublisher<DiabetesPanelResponse, Error> {
        guard let url = URL(string: "\(baseURL)/diabetes-panel") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        print("🩺 [LabReportsAPIService] Fetching diabetes panel data from: \(url)")
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: DiabetesPanelResponse.self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    func getLiverFunctionTestsData() -> AnyPublisher<LiverFunctionTestsResponse, Error> {
        guard let url = URL(string: "\(baseURL)/liver-function-tests") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        print("🫀 [LabReportsAPIService] Fetching liver function tests data from: \(url)")
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: LiverFunctionTestsResponse.self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    func getKidneyFunctionTestsData() -> AnyPublisher<KidneyFunctionTestsResponse, Error> {
        guard let url = URL(string: "\(baseURL)/kidney-function-tests") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        print("🫘 [LabReportsAPIService] Fetching kidney function tests data from: \(url)")
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: KidneyFunctionTestsResponse.self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    func getAvailableCategories() -> AnyPublisher<AvailableCategoriesResponse, Error> {
        guard let url = URL(string: "\(baseURL)/available-categories") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        print("📋 [LabReportsAPIService] Fetching available categories from: \(url)")
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: AvailableCategoriesResponse.self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    func getCategoryTestsData(category: String) -> AnyPublisher<CategoryTestsResponse, Error> {
        guard let encodedCategory = category.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/category/\(encodedCategory)/tests") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        print("🧪 [LabReportsAPIService] Fetching category tests data for '\(category)' from: \(url)")
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: CategoryTestsResponse.self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    func getTestTrends(testName: String) -> AnyPublisher<TestTrendsResponse, Error> {
        guard let encodedTestName = testName.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/trends/\(encodedTestName)") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        print("📈 [LabReportsAPIService] Fetching trends data for '\(testName)' from: \(url)")
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: TestTrendsResponse.self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    func getCategoryDetails(category: String) -> AnyPublisher<LabCategoryDetail, Error> {
        guard let encodedCategory = category.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/category/\(encodedCategory)") else {
            return Fail(error: URLError(.badURL))
                .eraseToAnyPublisher()
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: LabCategoryDetail.self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    func getOthersAndUncategorizedTestsData() -> AnyPublisher<CategoryTestsResponse, Error> {
        // Get all available categories first, then filter out known ones
        return getAvailableCategories()
            .flatMap { [weak self] availableResponse -> AnyPublisher<CategoryTestsResponse, Error> in
                guard let self = self else {
                    return Fail(error: URLError(.unknown))
                        .eraseToAnyPublisher()
                }
                
                // Known categories that have dedicated cards
                let knownCategories = Set([
                    "Diabetes Panel",
                    "Thyroid Profile", 
                    "Lipid Profile",
                    "Complete Blood Count",
                    "Complete Blood Count (CBC)",
                    "Liver Function Tests (LFT)",
                    "Kidney Function Tests (KFT)",
                    "Electrolyte Panel",
                    "Infection Markers",
                    "Vitamin & Mineral Panel",
                    "Cardiac Markers",
                    "Urine Routine"
                ])
                
                // Find categories that are "Others" or not in known categories
                let othersCategories = availableResponse.categories.filter { category in
                    category.name == "Others" || !knownCategories.contains(category.name)
                }.map { $0.name }
                
                print("🔍 [LabReportsAPIService] Others categories found: \(othersCategories)")
                
                // If no others categories found, return empty response
                if othersCategories.isEmpty {
                    return Just(CategoryTestsResponse(tests: [], category: "Others", totalTests: 0))
                        .setFailureType(to: Error.self)
                        .eraseToAnyPublisher()
                }
                
                // Get tests for all others categories and combine them
                let publishers = othersCategories.map { categoryName in
                    self.getCategoryTestsData(category: categoryName)
                }
                
                return Publishers.MergeMany(publishers)
                    .collect()
                    .map { responses in
                        // Combine all test results
                        let allTests = responses.flatMap { $0.tests }
                        return CategoryTestsResponse(
                            tests: allTests,
                            category: "Others",
                            totalTests: allTests.count
                        )
                    }
                    .eraseToAnyPublisher()
            }
            .eraseToAnyPublisher()
    }
}
