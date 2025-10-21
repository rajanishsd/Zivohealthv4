import SwiftUI
import HealthKit
import Combine


struct Health360OverviewView: View {
    @ObservedObject var healthKitManager: BackendVitalsManager
    @State private var isNavigating = false // Track navigation state
    
    var body: some View {
        ScrollView {
                VStack(spacing: 20) {
                    // Health Score Header
                    NavigationLink(destination: HealthScoreDetailView().navigationTitle("Health Score")) {
                        HealthScoreHeaderView()
                    }
                    .buttonStyle(PlainButtonStyle())
                    
                    // Active Health Alerts (hidden)
                    // ActiveHealthAlertsView()
                    
                    // Main Health Categories - Vertical Layout
                    VStack(spacing: 16) {
                        // Vitals Card - navigates to detailed HealthMetricsView
                        NavigationLink(destination: 
                            HealthMetricsView()
                                .navigationBarTitleDisplayMode(.large)
                        ) {
                            VitalsCardContentView(healthKitManager: healthKitManager)
                        }
                        .buttonStyle(PlainButtonStyle())
                        .onTapGesture {
                            print("🚨🚨🚨 [Health360OverviewView] VITALS CARD TAPPED 🚨🚨🚨")
                        }
                        
                        // Nutrition Card - navigates to detailed NutritionView
                        if #available(iOS 16.0, *) {
                            NavigationLink(destination: 
                                NutritionView()
                                    .navigationTitle("Nutrition")
                                    .navigationBarTitleDisplayMode(.large)
                            ) {
                                NutritionCardView()
                            }
                            .buttonStyle(PlainButtonStyle())
                        } else {
                            // Fallback for iOS 15
                            Button(action: {
                                // Could show an alert or navigate to a simpler view
                            }) {
                                NutritionCardView()
                            }
                            .buttonStyle(PlainButtonStyle())
                        }
                        
                                        // Biomarkers Card - navigates to BiomarkersView
                NavigationLink(destination: BiomarkersView()) {
                    BiomarkersCardView()
                }
                        .buttonStyle(PlainButtonStyle())
                        
                        // Medications Card - navigates to MedicationsView
                        NavigationLink(destination: MedicationsView()) {
                            MedicationsCardView()
                        }
                        .buttonStyle(PlainButtonStyle())
                        
                        // Activity & Sleep Card - navigates to detailed ActivitySleepView
                        NavigationLink(destination: 
                            ActivitySleepView()
                                .navigationBarTitleDisplayMode(.large)
                        ) {
                            ActivitySleepCardView(healthKitManager: healthKitManager)
                        }
                        .buttonStyle(PlainButtonStyle())
                        
                        // Mental Health Card
                        NavigationLink(destination: MentalHealthView()) {
                            MentalWellbeingCardView()
                        }
                        .buttonStyle(PlainButtonStyle())
                    }
                    .padding(.horizontal)
                    
                    // AI Health Insights Section (hidden)
                    // AIHealthInsightsView()
                }
                .padding(.bottom, 100)
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("Health 360")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            // Only load data if user is authenticated
            guard NetworkService.shared.isAuthenticated() else {
                print("⚠️ [Health360OverviewView] User not authenticated - skipping data load")
                return
            }
            
            print("🏥 [Health360OverviewView] onAppear - Health360 view loaded")
            
            // Check and request authorization if needed
            if !healthKitManager.isAuthorized {
                print("🔐 [Health360OverviewView] Not authorized - requesting authorization")
                healthKitManager.requestAuthorization()
            } else {
                print("✅ [Health360OverviewView] Already authorized - refreshing dashboard and checking for new data")
                // Force refresh dashboard and trigger sync when already authorized
                healthKitManager.refreshDashboard()
                healthKitManager.checkForNewDataAndSync()
            }
        }
    }
}

// MARK: - Health Score Header
struct HealthScoreHeaderView: View {
    @StateObject private var api = HealthScoreAPIService.shared
    @State private var scoreText: String = "--"
    @State private var subtitle: String = "Overall Health Score"
    @State private var reasons: [String] = []
    @State private var cancellables = Set<AnyCancellable>()
    var body: some View {
        ZStack {
            // Gradient background
            LinearGradient(
                colors: [Color.blue, Color.green],
                startPoint: .leading,
                endPoint: .trailing
            )
            .cornerRadius(20)
            
            VStack(spacing: 16) {
                HStack {
                    Text("Your Health at a Glance")
                        .font(.title2)
                        .fontWeight(.semibold)
                        .foregroundColor(.white)
                    
                    Spacer()
                    
                    Image(systemName: "chart.line.uptrend.xyaxis")
                        .font(.title2)
                        .foregroundColor(.white)
                }
                
                VStack(spacing: 8) {
                    Text(scoreText)
                        .font(.system(size: 48, weight: .bold))
                        .foregroundColor(.white)
                    
                    Text(subtitle)
                        .font(.headline)
                        .foregroundColor(.white.opacity(0.9))
                    // CTA to navigate to details
                    HStack {
                        Spacer()
                        HStack(spacing: 6) {
                            Text("Know why")
                                .font(.subheadline)
                                .fontWeight(.semibold)
                            Image(systemName: "chevron.right")
                                .font(.subheadline)
                        }
                        .foregroundColor(.white)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(Color.white.opacity(0.15))
                        .cornerRadius(12)
                    }
                }
            }
            .padding(20)
        }
        .padding(.horizontal)
        .onAppear {
            // Only load data if user is authenticated
            guard NetworkService.shared.isAuthenticated() else {
                print("⚠️ [HealthScoreHeaderView] User not authenticated - skipping data load")
                return
            }
            
            api.getToday()
                .receive(on: DispatchQueue.main)
                .sink(receiveCompletion: { _ in }, receiveValue: { json in
                    if let s = json["overall"] as? Double {
                        scoreText = String(format: "%.0f", s)
                    }
                    if let detail = json["detail"] as? [String: Any],
                       let insights = detail["insights"] as? [String: Any],
                       let rs = insights["reasons"] as? [[String: Any]] {
                        reasons = rs.compactMap { $0["message"] as? String }
                    }
                })
                .store(in: &cancellables)
        }
    }
}

// MARK: - Active Health Alerts
struct ActiveHealthAlertsView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundColor(.orange)
                Text("Active Health Alerts")
                    .font(.headline)
                    .fontWeight(.semibold)
                Spacer()
            }
            
            HStack(spacing: 12) {
                // High Blood Pressure Alert
                HStack {
                    Image(systemName: "exclamationmark.circle.fill")
                        .foregroundColor(.red)
                    Text("High Blood Pressure")
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(.white)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Color.red)
                .cornerRadius(16)
                
                // Low Vitamin D Alert
                HStack {
                    Image(systemName: "exclamationmark.circle.fill")
                        .foregroundColor(.orange)
                    Text("Low Vitamin D")
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(.white)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Color.orange)
                .cornerRadius(16)
                
                Spacer()
            }
        }
        .padding()
        .background(Color.orange.opacity(0.1))
        .cornerRadius(12)
        .padding(.horizontal)
    }
}

// MARK: - Vitals Card (Removed - using NavigationLink directly)

// MARK: - Vitals Card Content (for NavigationLink)
struct VitalsCardContentView: View {
    @ObservedObject var healthKitManager: BackendVitalsManager
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "heart.fill")
                    .foregroundColor(.red)
                Text("Vitals")
                    .font(.headline)
                    .fontWeight(.semibold)
                Spacer()
                Text(latestDataDate)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            VStack(spacing: 8) {
                // Heart Rate
                HStack {
                    Text("Heart Rate")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    Spacer()
                    Text(latestHeartRate)
                        .font(.subheadline)
                        .fontWeight(.medium)
                }
                
                // Blood Pressure
                HStack {
                    Text("Blood Pressure")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    Spacer()
                    Text(latestBloodPressure)
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(bloodPressureColor)
                }
                
                // Temperature
                HStack {
                    Text("Temperature")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    Spacer()
                    HStack {
                        Image(systemName: "thermometer")
                            .foregroundColor(.blue)
                            .font(.caption)
                        Text(latestTemperature)
                            .font(.subheadline)
                            .fontWeight(.medium)
                    }
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
    }
    
    // MARK: - Computed Properties
    private var latestHeartRate: String {
        if let dashboardData = healthKitManager.dashboardData,
           let heartRateMetric = dashboardData.metrics.first(where: { $0.metricType == .heartRate }),
           let latestValue = heartRateMetric.latestValue {
            return "\(Int(latestValue)) bpm"
        }
        return "--"
    }
    
    private var latestBloodPressure: String {
        if let dashboardData = healthKitManager.dashboardData {
            let systolicMetric = dashboardData.metrics.first(where: { $0.metricType == .bloodPressureSystolic })
            let diastolicMetric = dashboardData.metrics.first(where: { $0.metricType == .bloodPressureDiastolic })
            
            if let systolic = systolicMetric?.latestValue,
               let diastolic = diastolicMetric?.latestValue {
                return "\(Int(systolic))/\(Int(diastolic))"
            }
        }
        return "--/--"
    }
    
    private var latestTemperature: String {
        if let dashboardData = healthKitManager.dashboardData,
           let tempMetric = dashboardData.metrics.first(where: { $0.metricType == .bodyTemperature }) {
            let normalizedUnit = tempMetric.unit.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            let symbol: String
            if ["°f", "f", "degf", "fahrenheit"].contains(normalizedUnit) {
                symbol = "°F"
            } else if ["°c", "c", "degc", "celsius"].contains(normalizedUnit) {
                symbol = "°C"
            } else {
                symbol = tempMetric.unit
            }
            if let latestValue = tempMetric.latestValue {
                let valueString = String(format: "%.1f", latestValue)
                return "\(valueString)\(symbol)"
            } else {
                return "--\(symbol)"
            }
        }
        return "--"
    }
    
    private var latestDataDate: String {
        if let dashboardData = healthKitManager.dashboardData,
           let lastSync = dashboardData.lastSync {
            let formatter = DateFormatter()
            formatter.dateStyle = .short
            return formatter.string(from: lastSync)
        }
        return "No data"
    }
    
    private var bloodPressureColor: Color {
        if let dashboardData = healthKitManager.dashboardData,
           let systolicMetric = dashboardData.metrics.first(where: { $0.metricType == .bloodPressureSystolic }),
           let systolic = systolicMetric.latestValue {
            
            if systolic >= 140 {
                return .red
            } else if systolic >= 130 {
                return .orange
            } else {
                return .green
            }
        }
        return .primary
    }
}

// MARK: - Nutrition Card
struct NutritionCardView: View {
    @StateObject private var nutritionManager = NutritionManager.shared
    @StateObject private var nutritionGoalsManager = NutritionGoalsManager.shared
    
    private var dailyCalorieGoal: Double {
        // Try to get the calorie goal from nutrition goals manager
        if let caloriesItem = nutritionGoalsManager.progressItems.first(where: { $0.nutrientKey == "calories" }),
           let targetMax = caloriesItem.targetMax {
            return targetMax
        }
        // Fallback to 2000 if no goal is set
        return 2000
    }
    
    private var lastMealInfo: String {
        guard let lastMeal = nutritionManager.todaysMeals.last else {
            return "No meals today"
        }
        
        let dishName = lastMeal.dishName ?? lastMeal.foodItemName
        if let mealTime = lastMeal.mealDateTime {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
            return "\(dishName) at \(formatter.string(from: mealTime))"
        } else {
            return dishName
        }
    }
    
    private var calorieProgress: Double {
        min(nutritionManager.todaysCalories / dailyCalorieGoal, 1.0)
    }
    
    private var aiAnalyzedMeals: Int {
        nutritionManager.todaysMeals.filter { $0.dataSource == .photoAnalysis }.count
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "fork.knife")
                    .foregroundColor(.orange)
                    .font(.title3)
                Text("Nutrition")
                    .font(.headline)
                    .fontWeight(.semibold)
                Spacer()
                
                // Meal count badge
                HStack(spacing: 4) {
                    if aiAnalyzedMeals > 0 {
                        Image(systemName: "camera.fill")
                            .font(.caption2)
                            .foregroundColor(.blue)
                    }
                    Text("\(nutritionManager.todaysMealCount) meals")
                    .font(.caption)
                    .foregroundColor(.secondary)
                }
            }
            
            // Last meal info
            if !nutritionManager.todaysMeals.isEmpty {
                Text("Last: \(lastMealInfo)")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
            }
            
            VStack(spacing: 8) {
                HStack {
                    Text("Daily Calories")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    Spacer()
                    Text("\(Int(nutritionManager.todaysCalories))/\(Int(dailyCalorieGoal))")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(calorieProgress > 0.9 ? .orange : .primary)
                }
                
                // Progress bar
                GeometryReader { geometry in
                    ZStack(alignment: .leading) {
                        Rectangle()
                            .fill(Color.gray.opacity(0.2))
                            .frame(height: 6)
                            .cornerRadius(3)
                        
                        Rectangle()
                            .fill(LinearGradient(
                                colors: calorieProgress > 0.9 ? 
                                    [.orange, .red] : [.green, .blue],
                                startPoint: .leading,
                                endPoint: .trailing
                            ))
                            .frame(width: geometry.size.width * calorieProgress, height: 6)
                            .cornerRadius(3)
                    }
                }
                .frame(height: 6)
                
                HStack(spacing: 0) {
                    macroNutrientView("Protein", value: nutritionManager.todaysProtein, unit: "g", 
                                    color: .red, target: 150)
                    
                    macroNutrientView("Carbs", value: nutritionManager.todaysCarbs, unit: "g", 
                                    color: .blue, target: 250)
                    
                    macroNutrientView("Fat", value: nutritionManager.todaysFat, unit: "g", 
                                    color: .yellow, target: 65)
                    
                    if nutritionManager.todaysFiber > 0 {
                        macroNutrientView("Fiber", value: nutritionManager.todaysFiber, unit: "g", 
                                        color: .green, target: 25)
                    }
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
        .onAppear {
            nutritionManager.loadTodaysData()
            nutritionGoalsManager.loadGoalsData()
        }
    }
    
    private func macroNutrientView(_ name: String, value: Double, unit: String, color: Color, target: Double) -> some View {
        VStack(spacing: 2) {
            Text(name)
                .font(.caption)
                .foregroundColor(.secondary)
            Text("\(Int(value))\(unit)")
                .font(.caption)
                .fontWeight(.medium)
                .foregroundColor(value >= target * 0.8 ? color : .secondary)
            
            // Mini progress indicator
            Rectangle()
                .fill(value >= target * 0.8 ? color : Color.gray.opacity(0.3))
                .frame(width: 20, height: 2)
                .cornerRadius(1)
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Biomarkers Card
struct BiomarkersCardView: View {
    @State private var categories: [SimpleBiomarkerCategory] = []
    @State private var isLoading = true
    
    // Calculate health score based on test results (same logic as HealthProgressCard)
    private var healthScore: Int {
        let totalTests = categories.reduce(0) { $0 + $1.totalTests }
        let greenTests = categories.reduce(0) { $0 + $1.greenCount }
        let amberTests = categories.reduce(0) { $0 + $1.amberCount }
        let redTests = categories.reduce(0) { $0 + $1.redCount }
        
        guard totalTests > 0 else { return 0 }
        
        // Scoring algorithm:
        // Green tests: 100% score
        // Amber tests: 60% score  
        // Red tests: 0% score
        let totalScore = (greenTests * 100) + (amberTests * 60) + (redTests * 0)
        let maxPossibleScore = totalTests * 100
        
        return Int(Double(totalScore) / Double(maxPossibleScore) * 100)
    }
    
    private var progressValue: Double {
        return Double(healthScore) / 100.0
    }
    
    private var statusText: String {
        switch healthScore {
        case 90...100:
            return "Excellent"
        case 80..<90:
            return "Very Good"
        case 70..<80:
            return "Good"
        case 60..<70:
            return "Fair"
        case 50..<60:
            return "Needs Work"
        default:
            return "Poor"
        }
    }
    
    private var progressColors: [Color] {
        switch healthScore {
        case 80...100:
            return [.green, .mint]
        case 60..<80:
            return [.green, .yellow, .orange]
        default:
            return [.orange, .red]
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                Image(systemName: "doc.text.fill")
                    .foregroundColor(.purple)
                Text("Biomarkers")
                    .font(.headline)
                    .fontWeight(.semibold)
                Spacer()
                if isLoading {
                    ProgressView()
                        .scaleEffect(0.6)
                } else {
                    Text("Latest Results")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            if isLoading {
                VStack(spacing: 12) {
                    ProgressView()
                        .scaleEffect(1.2)
                    Text("Loading biomarker data...")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 20)
            } else {
                HStack(spacing: 20) {
                    // Circular Progress (same as HealthProgressCard)
                    ZStack {
                        Circle()
                            .stroke(Color.gray.opacity(0.2), lineWidth: 8)
                            .frame(width: 80, height: 80)
                        
                        Circle()
                            .trim(from: 0, to: progressValue)
                            .stroke(
                                AngularGradient(
                                    colors: progressColors,
                                    center: .center
                                ),
                                style: StrokeStyle(lineWidth: 8, lineCap: .round)
                            )
                            .frame(width: 80, height: 80)
                            .rotationEffect(.degrees(-90))
                        
                        VStack(spacing: 2) {
                            Text("\(healthScore)")
                                .font(.title3)
                                .fontWeight(.bold)
                                .foregroundColor(.primary)
                            Text("/100")
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                    }
                    
                    // Stats Summary
                    VStack(alignment: .leading, spacing: 8) {
                        Text(statusText)
                            .font(.subheadline)
                            .fontWeight(.semibold)
                            .foregroundColor(.primary)
                        
                        Text("\(categories.reduce(0) { $0 + $1.totalTests }) Total Tests")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        
                        // Status dots in a compact layout
                        HStack(spacing: 12) {
                            HStack(spacing: 3) {
                                Circle()
                                    .fill(Color.green)
                                    .frame(width: 6, height: 6)
                                Text("\(categories.reduce(0) { $0 + $1.greenCount })")
                                    .font(.caption2)
                                    .fontWeight(.medium)
                                Text("Normal")
                                    .font(.caption2)
                                    .foregroundColor(.green)
                            }
                            
                            HStack(spacing: 3) {
                                Circle()
                                    .fill(Color.orange)
                                    .frame(width: 6, height: 6)
                                Text("\(categories.reduce(0) { $0 + $1.amberCount })")
                                    .font(.caption2)
                                    .fontWeight(.medium)
                                Text("Elevated")
                                    .font(.caption2)
                                    .foregroundColor(.orange)
                            }
                            
                            HStack(spacing: 3) {
                                Circle()
                                    .fill(Color.red)
                                    .frame(width: 6, height: 6)
                                Text("\(categories.reduce(0) { $0 + $1.redCount })")
                                    .font(.caption2)
                                    .fontWeight(.medium)
                                Text("Critical")
                                    .font(.caption2)
                                    .foregroundColor(.red)
                            }
                        }
                    }
                    
                    Spacer()
                }
                .padding(.vertical, 8)
            }
        }
        .padding(16)
        .frame(minHeight: 120) // Increased height
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
        .onAppear {
            if categories.isEmpty {
                loadBiomarkerData()
            }
        }
    }
    
    private func loadBiomarkerData() {
        // Use the same data loading logic as SimpleDynamicBiomarkersCard
        let biomarkersCard = SimpleDynamicBiomarkersCard()
        // We'll create a simple version that just loads the data we need
        loadCategoriesData()
    }
    
    private func loadCategoriesData() {
        print("🔄 [BiomarkersCardView] Loading biomarker summary data...")
        isLoading = true
        
        let categoryConfigs: [(String, String, Color)] = [
            ("Diabetes Panel", "drop.fill", .green),
            ("Thyroid Profile", "bolt.fill", .purple),
            ("Lipid Profile", "waveform.path.ecg", .red),
            ("Complete Blood Count (CBC)", "drop.circle.fill", .red),
            ("Liver Function Tests (LFT)", "leaf.fill", .brown),
            ("Kidney Function Tests (KFT)", "drop.triangle", .cyan),
            ("Electrolyte Panel", "atom", .blue),
            ("Infection Markers", "shield.fill", .orange),
            ("Vitamin & Mineral Panel", "pills", .green),
            ("Cardiac Markers", "heart.fill", .pink),
            ("Urine Routine", "drop.circle", .yellow),
            ("Others", "doc.text", .gray)
        ]
        
        // Initialize categories with loading state
        categories = categoryConfigs.map { (name, icon, color) in
            SimpleBiomarkerCategory(
                name: name,
                icon: icon,
                iconColor: color,
                greenCount: 0,
                amberCount: 0,
                redCount: 0,
                totalTests: 0,
                isLoading: true
            )
        }
        
        // Load data for each category
        loadNextCategory(index: 0)
    }
    
    private func loadNextCategory(index: Int) {
        guard index < categories.count else {
            isLoading = false
            print("✅ [BiomarkersCardView] All categories loaded")
            return
        }
        
        let categoryName = categories[index].name
        
        // Use special API method for Others category
        let publisher: AnyPublisher<CategoryTestsResponse, Error>
        if categoryName == "Others" {
            publisher = LabReportsAPIService.shared.getOthersAndUncategorizedTestsData()
        } else {
            publisher = LabReportsAPIService.shared.getCategoryTestsData(category: categoryName)
        }
        
        publisher
            .receive(on: DispatchQueue.main)
            .sink(
                receiveCompletion: { completion in
                    if case .failure(let error) = completion {
                        print("❌ [BiomarkersCardView] Error loading \(categoryName): \(error)")
                        // Update with empty data on error
                        self.categories[index] = SimpleBiomarkerCategory(
                            name: categoryName,
                            icon: self.categories[index].icon,
                            iconColor: self.categories[index].iconColor,
                            greenCount: 0,
                            amberCount: 0,
                            redCount: 0,
                            totalTests: 0,
                            isLoading: false
                        )
                    }
                    
                    // Load next category
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                        self.loadNextCategory(index: index + 1)
                    }
                },
                receiveValue: { response in
                    // Calculate status counts using same logic as SimpleDynamicBiomarkersCard
                    let greenCount = response.tests.filter { test in
                        let status = self.convertStatus(test.status)
                        return status == "normal"
                    }.count
                    
                    let amberCount = response.tests.filter { test in
                        let status = self.convertStatus(test.status)
                        return status == "elevated"
                    }.count
                    
                    let redCount = response.tests.filter { test in
                        let status = self.convertStatus(test.status)
                        return status == "critical"
                    }.count
                    
                    // Update category with real data
                    self.categories[index] = SimpleBiomarkerCategory(
                        name: categoryName,
                        icon: self.categories[index].icon,
                        iconColor: self.categories[index].iconColor,
                        greenCount: greenCount,
                        amberCount: amberCount,
                        redCount: redCount,
                        totalTests: response.tests.count,
                        isLoading: false
                    )
                }
            )
            .store(in: &cancellables)
    }
    
    @State private var cancellables = Set<AnyCancellable>()
    
    private func convertStatus(_ statusString: String) -> String {
        switch statusString.lowercased() {
        case "normal", "green":
            return "normal"
        case "elevated", "high", "amber", "orange":
            return "elevated"
        case "critical", "red":
            return "critical"
        default:
            return "normal"
        }
    }
    
}

// MARK: - Medications Card
struct MedicationsCardView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "pills.fill")
                    .foregroundColor(.blue)
                Text("Medications")
                    .font(.headline)
                    .fontWeight(.semibold)
                Spacer()
                HStack {
                    Text("2")
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(.green)
                    Text("Active")
                        .font(.caption)
                        .foregroundColor(.green)
                }
            }
            
            VStack(spacing: 8) {
                HStack {
                    Text("Metformin")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    Spacer()
                    Text("Active")
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(.green)
                }
                .padding(.vertical, 2)
                
                HStack {
                    Text("500mg, Twice daily")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Spacer()
                }
                
                HStack {
                    Text("Vitamin D3")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    Spacer()
                    Text("Active")
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(.green)
                }
                .padding(.vertical, 2)
                
                HStack {
                    Text("2000 IU, Daily")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Spacer()
                }
                
                Text("Next dose in 3 hours")
                    .font(.caption)
                    .foregroundColor(.blue)
                    .padding(.top, 4)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
    }
}

// MARK: - Activity & Sleep Card
struct ActivitySleepCardView: View {
    @ObservedObject var healthKitManager: BackendVitalsManager
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header Section
            HStack {
                Image(systemName: "figure.walk")
                    .foregroundColor(.green)
                Text("Activity & Sleep")
                    .font(.headline)
                    .fontWeight(.semibold)
                Spacer()
                Text(getLatestDataDate())
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            // Simple Summary Section
            VStack(spacing: 16) {
                // Steps Display
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Image(systemName: "figure.walk")
                            .foregroundColor(.green)
                            .font(.subheadline)
                        Text("Steps")
                            .font(.subheadline)
                            .fontWeight(.semibold)
                            .foregroundColor(.primary)
                        Spacer()
                        Text("\(getLatestSteps())/10,000")
                            .font(.subheadline)
                            .fontWeight(.medium)
                    }
                    
                    // Steps progress bar
                    GeometryReader { geometry in
                        ZStack(alignment: .leading) {
                            Rectangle()
                                .fill(Color.gray.opacity(0.2))
                                .frame(height: 4)
                                .cornerRadius(2)
                            
                            Rectangle()
                                .fill(Color.green)
                                .frame(width: geometry.size.width * getStepsProgress(), height: 4)
                                .cornerRadius(2)
                        }
                    }
                    .frame(height: 4)
                }
                
                Divider()
                    .padding(.vertical, 4)
                
                // Sleep Display
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Image(systemName: "bed.double.fill")
                            .foregroundColor(.purple)
                            .font(.subheadline)
                        Text("Sleep")
                            .font(.subheadline)
                            .fontWeight(.semibold)
                            .foregroundColor(.primary)
                        Spacer()
                        VStack(alignment: .trailing) {
                            Text(getLatestSleep())
                                .font(.subheadline)
                                .fontWeight(.medium)
                            Text("Good")
                                .font(.caption)
                                .foregroundColor(.green)
                        }
                    }
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
    }
    
    private func getLatestSteps() -> String {
        return VitalsDisplayHelper.getLatestSteps(from: healthKitManager.dashboardData)
    }
    
    private func getLatestSleep() -> String {
        return VitalsDisplayHelper.getLatestSleep(from: healthKitManager.dashboardData)
    }
    
    private func getStepsProgress() -> Double {
        return VitalsDisplayHelper.getStepsProgress(from: healthKitManager.dashboardData)
    }
    
    private func getLatestDataDate() -> String {
        var latestDate: Date?
        
        if let dashboardData = healthKitManager.dashboardData {
            // Check steps and sleep metrics for the most recent date
            let activityMetrics = dashboardData.metrics.filter { 
                $0.metricType == .stepCount || $0.metricType == .sleep 
            }
            
            for metric in activityMetrics {
                if let lastPoint = metric.dataPoints.last,
                   let dateString = lastPoint.date {
                    let date = parseDate(dateString)
                    if latestDate == nil || date > latestDate! {
                        latestDate = date
                    }
                }
            }
        }
        
        // Fallback to individual metrics
        if latestDate == nil {
            let allActivityMetrics = healthKitManager.getMetrics(for: "Steps") + 
                                   healthKitManager.getMetrics(for: "Sleep")
            
            latestDate = allActivityMetrics.map { $0.date }.max()
        }
        
        if let date = latestDate {
            let formatter = DateFormatter()
            if Calendar.current.isDateInToday(date) {
                return "Today"
            } else if Calendar.current.isDateInYesterday(date) {
                return "Yesterday"
            } else {
                formatter.dateFormat = "MMM d"
                return formatter.string(from: date)
            }
        }
        
        return "No data"
    }
    
    private func parseDate(_ dateString: String) -> Date {
        let iso8601Formatter = ISO8601DateFormatter()
        if let date = iso8601Formatter.date(from: dateString) {
            return date
        }
        
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: dateString) ?? Date()
    }
}

// MARK: - Mental Health Card
struct MentalWellbeingCardView: View {
    @StateObject private var mhService = MentalHealthService.shared
    private let dateFormatter: DateFormatter = {
        let df = DateFormatter(); df.dateStyle = .medium; return df
    }()
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "brain.head.profile")
                    .foregroundColor(.purple)
                Text("Mental Health")
                    .font(.headline)
                    .fontWeight(.semibold)
                Spacer()
                Text(headerDateText)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            VStack(alignment: .leading, spacing: 8) {
                if let today = todayEntry {
                    HStack {
                        Text(mhService.labelForScore(today.pleasantnessScore))
                            .font(.title3)
                            .fontWeight(.semibold)
                        Spacer()
                        Text("Today")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    if let feelings = Optional(today.feelings), !feelings.isEmpty {
                        feelingsRow(feelings)
                    }
                } else if let last = lastPoint {
                    HStack {
                        Text(mhService.labelForScore(last.score))
                            .font(.title3)
                            .fontWeight(.semibold)
                        Spacer()
                        Text(dateFormatter.string(from: last.date))
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    if !last.feelings.isEmpty {
                        feelingsRow(last.feelings)
                    }
                } else {
                    Text("No mental health data yet")
                        .foregroundColor(.secondary)
                }
            }
        }
        .onAppear {
            if mhService.dailyPoints.isEmpty { mhService.loadRollup(rangeDays: 30) }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
    }
    
    private var todayEntry: MentalHealthEntry? {
        return mhService.latestEntryToday
    }
    private var lastPoint: MentalHealthDailyPoint? {
        if let today = mhService.dailyPoints.first(where: { Calendar.current.isDateInToday($0.date) }) { return today }
        return mhService.dailyPoints.sorted { $0.date > $1.date }.first
    }
    private var headerDateText: String {
        if todayEntry != nil { return "Today" }
        if let last = lastPoint { return dateFormatter.string(from: last.date) }
        return ""
    }

    // MARK: - Feelings UI
    @ViewBuilder
    private func feelingsRow(_ feelings: [String]) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Feelings")
                .font(.caption)
                .foregroundColor(.secondary)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(feelings, id: \.self) { tag in
                        tagChip(tag)
                    }
                }
            }
        }
        .padding(.top, 4)
    }

    private func tagChip(_ label: String) -> some View {
        let palette: [Color] = [.pink, .purple, .mint, .orange, .teal, .blue, .indigo, .yellow]
        let color = palette[abs(label.hashValue) % palette.count]
        return Text(label)
            .font(.caption)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(color.opacity(0.15))
            .foregroundColor(color)
            .cornerRadius(8)
    }
}

// MARK: - AI Health Insights
struct AIHealthInsightsView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "brain")
                    .foregroundColor(.blue)
                Text("AI Health Insights & Reports")
                    .font(.headline)
                    .fontWeight(.semibold)
                Spacer()
                Button("New") {
                    // Action for new insight
                }
                .font(.caption)
                .foregroundColor(.blue)
            }
            
            HStack(spacing: 12) {
                // Critical Alerts
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Image(systemName: "exclamationmark.circle.fill")
                            .foregroundColor(.red)
                        Text("Critical Alerts")
                            .font(.subheadline)
                            .fontWeight(.medium)
                    }
                    Text("2 items need attention")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding()
                .background(Color.red.opacity(0.1))
                .cornerRadius(8)
                
                Spacer()
                
                // Health Tips
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Image(systemName: "lightbulb.fill")
                            .foregroundColor(.blue)
                        Text("Health Tips")
                            .font(.subheadline)
                            .fontWeight(.medium)
                    }
                    Text("4 personalized recommendations")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding()
                .background(Color.blue.opacity(0.1))
                .cornerRadius(8)
            }
            
            VStack(alignment: .leading, spacing: 12) {
                Text("Recent Insights:")
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Circle()
                            .fill(Color.orange)
                            .frame(width: 6, height: 6)
                        Text("Your blood pressure has been trending higher this week. Consider reducing sodium intake.")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    
                    HStack {
                        Circle()
                            .fill(Color.green)
                            .frame(width: 6, height: 6)
                        Text("Great job maintaining consistent sleep schedule! Your recovery scores improved by 12%.")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    
                    HStack {
                        Circle()
                            .fill(Color.blue)
                            .frame(width: 6, height: 6)
                        Text("Based on your lab results, consider scheduling a follow-up for Vitamin D supplementation.")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }
        }
        .padding()
        .background(Color.blue.opacity(0.05))
        .cornerRadius(12)
        .padding(.horizontal)
    }
}

 