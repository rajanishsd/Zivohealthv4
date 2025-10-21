import Foundation
import Combine
import SwiftUI

// MARK: - Helper Structs
struct NutritionSummary {
    let calories: Double
    let protein: Double
    let carbs: Double
    let fat: Double
}

struct DailyNutritionSummary {
    let calories: Double
    let protein: Double
    let carbs: Double
    let fat: Double
    let meals: Int
}


class NutritionManager: ObservableObject {
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var nutritionData: [NutritionDataResponse] = []
    @Published var chartData: NutritionChartData?
    @Published var selectedGranularity: NutritionTimeGranularity = .daily
    
    private let nutritionAPIService = NutritionAPIService.shared
    private var cancellables = Set<AnyCancellable>()
    private var authStateSubscription: AnyCancellable?
    
    // DO NOT cache today's date; compute dynamically to avoid stale values after midnight
    private var today: Date { Date() }
    
    // MARK: - Computed Properties for Health360OverviewView
    var todaysMeals: [NutritionDataResponse] {
        let calendar = Calendar.current
        return nutritionData.filter { meal in
            // Parse the meal date string and compare with today
            let formatter = DateFormatter()
            formatter.dateFormat = "yyyy-MM-dd"
            guard let mealDate = formatter.date(from: meal.mealDate) else { return false }
            return calendar.isDate(mealDate, inSameDayAs: today)
        }
        .sorted { meal1, meal2 in
            // Sort by mealDateTime if available, otherwise by creation time
            if let time1 = meal1.mealDateTime, let time2 = meal2.mealDateTime {
                return time1 < time2
            } else if let time1 = meal1.mealDateTime {
                return true // meal1 has time, meal2 doesn't - prioritize meal1
            } else if let time2 = meal2.mealDateTime {
                return false // meal2 has time, meal1 doesn't - prioritize meal2
            } else {
                // Neither has mealDateTime, sort by id (assuming higher id = more recent)
                return meal1.id < meal2.id
            }
        }
    }
    
    var todaysCalories: Double {
        return todaysMeals.reduce(0) { $0 + $1.calories }
    }
    
    var todaysProtein: Double {
        return todaysMeals.reduce(0) { $0 + $1.proteinG }
    }
    
    var todaysCarbs: Double {
        return todaysMeals.reduce(0) { $0 + $1.carbsG }
    }
    
    var todaysFat: Double {
        return todaysMeals.reduce(0) { $0 + $1.fatG }
    }
    
    var todaysFiber: Double {
        return todaysMeals.reduce(0) { $0 + $1.fiberG }
    }
    
    var todaysSugar: Double {
        return todaysMeals.reduce(0) { $0 + $1.sugarG }
    }
    
    var todaysSodium: Double {
        return todaysMeals.reduce(0) { $0 + $1.sodiumMg }
    }
    
    var todaysMealCount: Int {
        return todaysMeals.count
    }
    
    // MARK: - Singleton
    static let shared = NutritionManager()
    
    init() {
        // Initialize if needed
        setupAuthObserver()
    }
    
    // MARK: - Auth State Observer
    /// Observe authentication state and clear data on logout
    private func setupAuthObserver() {
        authStateSubscription = NetworkService.shared.$isAuthenticatedState
            .sink { [weak self] isAuthenticated in
                if !isAuthenticated {
                    print("🔒 [NutritionManager] User logged out - clearing nutrition data")
                    self?.clearData()
                }
            }
    }
    
    /// Clear all cached data
    private func clearData() {
        DispatchQueue.main.async { [weak self] in
            self?.nutritionData = []
            self?.chartData = nil
            self?.errorMessage = nil
        }
    }
    
    // MARK: - Public Methods
    func loadTodaysData() {
        // Load today's nutrition data and chart data
        let startOfDay = Calendar.current.startOfDay(for: today)
        let endOfDay = Calendar.current.date(byAdding: .day, value: 1, to: startOfDay) ?? today
        
        // Load both nutrition data and chart data
        loadNutritionData(
            startDate: startOfDay,
            endDate: endOfDay,
            granularity: .daily
        )
        
        // Also load chart data for the past 3 days (including today)  
        let threeDaysAgo = Calendar.current.date(byAdding: .day, value: -3, to: today) ?? today
        let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: today) ?? today
        loadChartData(startDate: threeDaysAgo, endDate: tomorrow, granularity: .daily)
    }
    
    func loadNutritionData(
        startDate: Date? = nil,
        endDate: Date? = nil,
        mealType: MealType? = nil,
        source: NutritionDataSource? = nil,
        granularity: NutritionTimeGranularity = .daily,
        limit: Int = 100,
        offset: Int = 0
    ) {
        isLoading = true
        errorMessage = nil
        
        nutritionAPIService.getNutritionData(
            startDate: startDate,
            endDate: endDate,
            mealType: mealType,
            source: source,
            granularity: granularity,
            limit: limit,
            offset: offset
        )
        .sink(
            receiveCompletion: { [weak self] completion in
                DispatchQueue.main.async {
                    self?.isLoading = false
                    if case .failure(let error) = completion {
                        let errorMessage = self?.getErrorMessage(from: error) ?? error.localizedDescription
                        self?.errorMessage = errorMessage
                        print("❌ [NutritionManager] Failed to load nutrition data: \(errorMessage)")
                    }
                }
            },
            receiveValue: { [weak self] data in
                DispatchQueue.main.async {
                    self?.nutritionData = data
                    print("✅ [NutritionManager] Loaded \(data.count) nutrition records")
                }
            }
        )
        .store(in: &cancellables)
    }
    
    func loadChartData(
        startDate: Date,
        endDate: Date,
        granularity: NutritionTimeGranularity = .daily
    ) {
        isLoading = true
        errorMessage = nil
        
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        print("📊 [NutritionManager] Loading chart data from \(formatter.string(from: startDate)) to \(formatter.string(from: endDate))")
        
        nutritionAPIService.getNutritionChartData(
            startDate: startDate,
            endDate: endDate,
            granularity: granularity
        )
        .sink(
            receiveCompletion: { [weak self] completion in
                DispatchQueue.main.async {
                    self?.isLoading = false
                    if case .failure(let error) = completion {
                        let errorMessage = self?.getErrorMessage(from: error) ?? error.localizedDescription
                        self?.errorMessage = errorMessage
                        print("❌ [NutritionManager] Failed to load chart data: \(errorMessage)")
                    }
                }
            },
            receiveValue: { [weak self] data in
                DispatchQueue.main.async {
                    self?.chartData = data
                    print("✅ [NutritionManager] Loaded chart data with \(data.dataPoints.count) data points")
                    print("📊 [NutritionManager] Chart data points: \(data.dataPoints.map { "\($0.date): \($0.calories) cal" })")
                }
            }
        )
        .store(in: &cancellables)
    }
    
    func createNutritionData(_ data: NutritionDataCreate) {
        isLoading = true
        errorMessage = nil
        
        nutritionAPIService.createNutritionData(data)
            .sink(
                receiveCompletion: { [weak self] completion in
                    DispatchQueue.main.async {
                        self?.isLoading = false
                        if case .failure(let error) = completion {
                            self?.errorMessage = error.localizedDescription
                        }
                    }
                },
                receiveValue: { [weak self] response in
                    DispatchQueue.main.async {
                        self?.nutritionData.append(response)
                    }
                }
            )
            .store(in: &cancellables)
    }
    
    func deleteNutritionData(id: Int) {
        nutritionAPIService.deleteNutritionData(id: id)
            .sink(
                receiveCompletion: { [weak self] completion in
                    if case .failure(let error) = completion {
                        DispatchQueue.main.async {
                            self?.errorMessage = error.localizedDescription
                        }
                    }
                },
                receiveValue: { [weak self] _ in
                    DispatchQueue.main.async {
                        self?.nutritionData.removeAll { $0.id == id }
                    }
                }
            )
            .store(in: &cancellables)
    }
    
    // MARK: - Time Period Methods
    func loadDailyData() {
        selectedGranularity = NutritionTimeGranularity.daily
        // Load exactly 3 days: start from 3 days ago to get today, yesterday, and day before
        let threeDaysAgo = Calendar.current.date(byAdding: .day, value: -3, to: Date()) ?? Date()
        let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: today) ?? today
        loadChartData(startDate: threeDaysAgo, endDate: tomorrow, granularity: NutritionTimeGranularity.daily)
    }
    
    func loadWeeklyData() {
        selectedGranularity = NutritionTimeGranularity.weekly
        // Load exactly 3 weeks: start from 3 weeks ago to get the last 3 complete weeks
        let threeWeeksAgo = Calendar.current.date(byAdding: .weekOfYear, value: -3, to: Date()) ?? Date()
        let today = Date()
        
        // Debug logging
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        print("📊 [NutritionManager] Loading weekly data from \(formatter.string(from: threeWeeksAgo)) to \(formatter.string(from: today))")
        
        loadChartData(startDate: threeWeeksAgo, endDate: today, granularity: NutritionTimeGranularity.weekly)
    }
    
    func loadMonthlyData() {
        selectedGranularity = NutritionTimeGranularity.monthly
        // Load exactly 3 months: start from 3 months ago to get this month, last month, and 2 months ago
        let threeMonthsAgo = Calendar.current.date(byAdding: .month, value: -3, to: Date()) ?? Date()
        let nextMonth = Calendar.current.date(byAdding: .month, value: 1, to: today) ?? today
        loadChartData(startDate: threeMonthsAgo, endDate: nextMonth, granularity: NutritionTimeGranularity.monthly)
    }
    
    // MARK: - Error Handling Helper
    private func getErrorMessage(from error: Error) -> String {
        if let urlError = error as? URLError {
            switch urlError.code {
            case .notConnectedToInternet:
                return "No internet connection available"
            case .timedOut:
                return "Request timed out. Please try again"
            case .cannotFindHost, .cannotConnectToHost:
                return "Cannot connect to server"
            case .userAuthenticationRequired:
                // Retry the request after a short delay
                DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
                    print("🔄 [NutritionManager] Retrying after authentication...")
                    self.loadTodaysData()
                }
                return "Authentication required. Retrying..."
            default:
                return "Network error: \(urlError.localizedDescription)"
            }
        } else if error.localizedDescription.contains("403") || error.localizedDescription.contains("Could not validate credentials") {
            // Retry the request after a short delay
            DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
                print("🔄 [NutritionManager] Retrying after authentication error...")
                self.loadTodaysData()
            }
            return "Authentication failed. Retrying..."
        } else if error.localizedDescription.contains("The data couldn't be read") {
            return "Server returned invalid data format. Please try again later"
        } else {
            return error.localizedDescription
        }
    }
}
