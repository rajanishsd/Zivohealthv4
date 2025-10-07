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
    @Published var currentGoalDetail: NutritionGoalDetail?
    @Published var inactiveGoals: [NutritionGoal] = []
    @Published var allGoals: [NutritionGoal] = []
    @Published var currentGoalReminders: NutritionGoalReminders?
    
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
            .tryMap { output -> Data in
                if let http = output.response as? HTTPURLResponse {
                    print("🌐 [NutritionGoalsManager] /current status: \(http.statusCode)")
                    print("📩 [NutritionGoalsManager] /current headers: \(http.allHeaderFields)")
                }
                if let body = String(data: output.data, encoding: .utf8) {
                    print("🧾 [NutritionGoalsManager] /current raw: \(body)")
                } else {
                    print("🧾 [NutritionGoalsManager] /current raw: <non-utf8 \(output.data.count) bytes>")
                }
                return output.data
            }
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
                    // Immediately load progress if there is an active goal
                    if summary.hasActiveGoal {
                        self?.loadActiveGoalProgress()
                    }
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
        
        let startStr = queryItems.first(where: { $0.name == "start_date" })?.value ?? ""
        let endStr = queryItems.first(where: { $0.name == "end_date" })?.value ?? ""
        print("🔄 [NutritionGoalsManager] Loading goal progress: timeframe=\(timeframe), start=\(startStr), end=\(endStr)")
        print("🌐 [NutritionGoalsManager] GET \(url.absoluteString)")

        isLoading = true
        errorMessage = nil
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = getAuthHeaders()
        
        URLSession.shared.dataTaskPublisher(for: request)
            .tryMap { output -> Data in
                if let http = output.response as? HTTPURLResponse {
                    print("🌐 [NutritionGoalsManager] /progress/active status: \(http.statusCode)")
                    print("📩 [NutritionGoalsManager] /progress/active headers: \(http.allHeaderFields)")
                }
                if let body = String(data: output.data, encoding: .utf8) {
                    print("🧾 [NutritionGoalsManager] /progress/active raw: \(body.prefix(2000))")
                } else {
                    print("🧾 [NutritionGoalsManager] /progress/active raw: <non-utf8 \(output.data.count) bytes>")
                }
                return output.data
            }
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
                    // Sample a few items for visibility
                    for item in response.items.prefix(5) {
                        print("🔎 [NutritionGoalsManager] item key=\(item.nutrientKey) current=\(item.currentValue?.description ?? "nil") min=\(item.targetMin?.description ?? "nil") max=\(item.targetMax?.description ?? "nil") status=\(item.status ?? "nil") percent=\(item.percentOfTarget?.description ?? "nil")")
                    }
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

    /// Load current active goal details including targets and meal plan
    func loadCurrentGoalDetail() {
        guard let url = URL(string: "\(baseURL)/current/detail") else {
            self.errorMessage = "Invalid URL"
            return
        }

        isLoading = true
        errorMessage = nil

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = getAuthHeaders()

        URLSession.shared.dataTaskPublisher(for: request)
            .tryMap { output -> Data in
                if let http = output.response as? HTTPURLResponse {
                    print("🌐 [NutritionGoalsManager] /current/detail status: \(http.statusCode)")
                }
                return output.data
            }
            .decode(type: NutritionGoalDetail.self, decoder: JSONDecoder.nutritionGoalsDecoder)
            .receive(on: DispatchQueue.main)
            .sink(
                receiveCompletion: { [weak self] completion in
                    self?.isLoading = false
                    if case .failure(let error) = completion {
                        self?.errorMessage = "Failed to load goal detail: \(error.localizedDescription)"
                        print("❌ [NutritionGoalsManager] Failed to load goal detail: \(error)")
                    }
                },
                receiveValue: { [weak self] detail in
                    self?.currentGoalDetail = detail
                    print("✅ [NutritionGoalsManager] Loaded goal detail with \(detail.targets.count) targets")
                    self?.loadCurrentGoalReminders()
                }
            )
            .store(in: &cancellables)
    }

    // MARK: - Reminders API
    func loadCurrentGoalReminders() {
        guard let url = URL(string: "\(baseURL)/current/reminders") else {
            self.errorMessage = "Invalid URL"
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = getAuthHeaders()

        URLSession.shared.dataTaskPublisher(for: request)
            .tryMap { output -> Data in
                if let http = output.response as? HTTPURLResponse {
                    print("🌐 [NutritionGoalsManager] /current/reminders status: \(http.statusCode)")
                }
                return output.data
            }
            .decode(type: NutritionGoalReminders.self, decoder: JSONDecoder.nutritionGoalsDecoder)
            .receive(on: DispatchQueue.main)
            .sink(
                receiveCompletion: { [weak self] completion in
                    if case .failure(let error) = completion {
                        print("❌ [NutritionGoalsManager] Failed to load reminders: \(error)")
                    }
                },
                receiveValue: { [weak self] reminders in
                    self?.currentGoalReminders = reminders
                    print("✅ [NutritionGoalsManager] Loaded reminders: \(reminders.items.count) items")
                }
            )
            .store(in: &cancellables)
    }

    /// Update a reminder's time and/or frequency for the current goal
    func updateCurrentGoalReminder(meal: String, timeLocal: String?, frequency: String?, completion: ((Bool) -> Void)? = nil) {
        var components = URLComponents(string: "\(baseURL)/current/reminders/\(meal)")!
        var q: [URLQueryItem] = []
        if let t = timeLocal, !t.isEmpty { q.append(URLQueryItem(name: "time_local", value: t)) }
        if let f = frequency, !f.isEmpty { q.append(URLQueryItem(name: "frequency", value: f)) }
        components.queryItems = q.isEmpty ? nil : q
        guard let url = components.url else {
            completion?(false); return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "PATCH"
        request.allHTTPHeaderFields = getAuthHeaders()

        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            DispatchQueue.main.async {
                if let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) {
                    // Refresh reminders after successful update
                    self?.loadCurrentGoalReminders()
                    completion?(true)
                } else {
                    completion?(false)
                }
            }
        }.resume()
    }

    /// Load inactive goals list for switching
    func loadInactiveGoals() {
        guard let url = URL(string: "\(baseURL)/goals?status=inactive") else {
            self.errorMessage = "Invalid URL"
            return
        }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = getAuthHeaders()
        URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: [NutritionGoal].self, decoder: JSONDecoder.nutritionGoalsDecoder)
            .receive(on: DispatchQueue.main)
            .sink(receiveCompletion: { [weak self] completion in
                if case .failure(let error) = completion {
                    self?.errorMessage = "Failed to load inactive goals: \(error.localizedDescription)"
                }
            }, receiveValue: { [weak self] goals in
                self?.inactiveGoals = goals
            })
            .store(in: &cancellables)
    }

    /// Load all goals (active and inactive)
    func loadAllGoals() {
        guard let url = URL(string: "\(baseURL)/goals") else {
            self.errorMessage = "Invalid URL"
            return
        }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.allHTTPHeaderFields = getAuthHeaders()
        URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: [NutritionGoal].self, decoder: JSONDecoder.nutritionGoalsDecoder)
            .receive(on: DispatchQueue.main)
            .sink(receiveCompletion: { [weak self] completion in
                if case .failure(let error) = completion {
                    self?.errorMessage = "Failed to load goals: \(error.localizedDescription)"
                }
            }, receiveValue: { [weak self] goals in
                self?.allGoals = goals
            })
            .store(in: &cancellables)
    }

    /// Activate a previous goal
    func activateGoal(goalId: Int, completion: @escaping (Bool) -> Void) {
        print("🌐 [NutritionGoalsManager] Activating goal \(goalId)")
        guard let url = URL(string: "\(baseURL)/goals/\(goalId)/activate") else { 
            print("🌐 [NutritionGoalsManager] ERROR: Invalid URL for goal \(goalId)")
            completion(false); return 
        }
        print("🌐 [NutritionGoalsManager] URL: \(url)")
        var request = URLRequest(url: url)
        request.httpMethod = "PATCH"
        request.allHTTPHeaderFields = getAuthHeaders()
        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                if let http = response as? HTTPURLResponse {
                    print("🌐 [NutritionGoalsManager] Response status: \(http.statusCode)")
                    if (200...299).contains(http.statusCode) {
                        print("🌐 [NutritionGoalsManager] Activation successful, reloading data")
                        self.loadActiveGoalSummary()
                        self.loadCurrentGoalDetail()
                        self.loadAllGoals()
                        self.loadInactiveGoals()
                        completion(true)
                    } else {
                        print("🌐 [NutritionGoalsManager] Activation failed with status: \(http.statusCode)")
                        self.errorMessage = "Activation failed with status: \(http.statusCode)"
                        completion(false)
                    }
                } else {
                    print("🌐 [NutritionGoalsManager] ERROR: \(error?.localizedDescription ?? "Unknown error")")
                    self.errorMessage = error?.localizedDescription
                    completion(false)
                }
            }
        }.resume()
    }

    /// Delete an inactive goal
    func deleteGoal(goalId: Int, completion: @escaping (Bool) -> Void) {
        print("🗑️ [NutritionGoalsManager] DELETING goal \(goalId)")
        guard let url = URL(string: "\(baseURL)/goals/\(goalId)") else { 
            print("🗑️ [NutritionGoalsManager] ERROR: Invalid URL for goal \(goalId)")
            completion(false); return 
        }
        print("🗑️ [NutritionGoalsManager] DELETE URL: \(url)")
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.allHTTPHeaderFields = getAuthHeaders()
        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                if let http = response as? HTTPURLResponse {
                    print("🗑️ [NutritionGoalsManager] DELETE Response status: \(http.statusCode)")
                    if http.statusCode == 200 {
                        self.loadInactiveGoals()
                        completion(true)
                    } else {
                        print("🗑️ [NutritionGoalsManager] DELETE failed with status: \(http.statusCode)")
                        self.errorMessage = error?.localizedDescription
                        completion(false)
                    }
                } else {
                    print("🗑️ [NutritionGoalsManager] DELETE ERROR: \(error?.localizedDescription ?? "Unknown error")")
                    self.errorMessage = error?.localizedDescription
                    completion(false)
                }
            }
        }.resume()
    }
}

// MARK: - JSON Decoder Extension
extension JSONDecoder {
    static var nutritionGoalsDecoder: JSONDecoder {
        let decoder = JSONDecoder()
        // Be flexible: accept date-only and timestamp variants
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let dateString = try container.decode(String.self)

            let formats = [
                "yyyy-MM-dd",
                "yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'",
                "yyyy-MM-dd'T'HH:mm:ss'Z'",
                "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'"
            ]

            for format in formats {
                let formatter = DateFormatter()
                formatter.dateFormat = format
                formatter.timeZone = TimeZone(abbreviation: "UTC")
                if let date = formatter.date(from: dateString) {
                    return date
                }
            }

            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unsupported date format: \(dateString)")
        }
        return decoder
    }
}
