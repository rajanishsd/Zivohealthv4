import SwiftUI
import Combine

struct HomeView: View {
    @StateObject private var healthScoreAPI = HealthScoreAPIService.shared
    @StateObject private var nutritionManager = NutritionManager.shared
    @StateObject private var nutritionGoalsManager = NutritionGoalsManager.shared
    @ObservedObject private var healthKitManager = BackendVitalsManager.shared
    @ObservedObject private var appointmentViewModel = AppointmentViewModel.shared
    @State private var userName: String = ""
    @State private var healthScore: Int? = nil
    @State private var healthScoreLabel: String = ""
    @State private var aiInsights: [AIInsight] = []
    @State private var currentInsightIndex: Int = 0
    @State private var streakDays: Int = 5
    @State private var cancellables = Set<AnyCancellable>()
    @State private var showAddMeal = false
    @State private var showLogMood = false
    @State private var showBiomarkers = false
    @State private var showNutrition = false
    @State private var showMedications = false
    @State private var showVitals = false
    @State private var showMentalHealth = false
    @State private var showNutritionPlan = false
    @State private var showNutritionGoalSetup = false
    @State private var showHealth360 = false
    @State private var showActivitySleep = false
    @StateObject private var mentalHealthService = MentalHealthService.shared

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Header with Health Score
                headerView
                
                // AI Nutritionist Card
                aiNutritionistCard
                
                // Quick Actions
                quickActionsSection
                
                // My Day Snapshot
                myDaySnapshot
                
                // AI Insights - Hidden
                // aiInsightsSection
                
                // Your Plan & Appointments
                planAndAppointmentsSection
                
                // Gamification Streak - Hidden
                // streakSection
            }
            .padding(.bottom, 100)
        }
        .background(Color(.systemGroupedBackground))
        .navigationBarHidden(true)
        .background(
            NavigationLink(
                destination: AddMealView(),
                isActive: $showAddMeal,
                label: { EmptyView() }
            )
            .hidden()
        )
        .background(
            Group {
                if #available(iOS 16.0, *) {
                    NavigationLink(
                        destination: NutritionView(),
                        isActive: $showNutrition,
                        label: { EmptyView() }
                    )
                    .hidden()
                } else {
                    EmptyView()
                }
            }
        )
        .background(
            NavigationLink(
                destination: MedicationsView(),
                isActive: $showMedications,
                label: { EmptyView() }
            )
            .hidden()
        )
        .background(
            NavigationLink(
                destination: HealthMetricsView(),
                isActive: $showVitals,
                label: { EmptyView() }
            )
            .hidden()
        )
        .background(
            NavigationLink(
                destination: MentalHealthView(),
                isActive: $showMentalHealth,
                label: { EmptyView() }
            )
            .hidden()
        )
        .background(
            NavigationLink(
                destination: Health360OverviewView(healthKitManager: healthKitManager),
                isActive: $showHealth360,
                label: { EmptyView() }
            )
            .hidden()
        )
        .background(
            NavigationLink(
                destination: ActivitySleepView(),
                isActive: $showActivitySleep,
                label: { EmptyView() }
            )
            .hidden()
        )
        .fullScreenCover(isPresented: $showLogMood) {
            MentalHealthLogMoodSheet()
        }
        .background(
            NavigationLink(
                destination: BiomarkersView(),
                isActive: $showBiomarkers,
                label: { EmptyView() }
            )
            .hidden()
        )
        .background(
            Group {
                if #available(iOS 16.0, *) {
                    NavigationLink(
                        destination: NutritionGoalDetailView(),
                        isActive: $showNutritionPlan,
                        label: { EmptyView() }
                    )
                    .hidden()
                } else {
                    EmptyView()
                }
            }
        )
        .background(
            Group {
                if #available(iOS 16.0, *) {
                    NavigationLink(
                        destination: NutritionGoalSetupView(),
                        isActive: $showNutritionGoalSetup,
                        label: { EmptyView() }
                    )
                    .hidden()
                } else {
                    EmptyView()
                }
            }
        )
        .task {
            // Only load data if user is authenticated
            guard NetworkService.shared.isAuthenticated() else {
                print("⚠️ [HomeView] User not authenticated - skipping data load")
                return
            }
            
            await loadUserData()
            loadHealthScore()
            loadAIInsights()
            nutritionManager.loadTodaysData()
            nutritionGoalsManager.loadGoalsData()
            appointmentViewModel.loadAppointments()
            
            // Load health kit data
            if healthKitManager.isAuthorized {
                healthKitManager.refreshDashboard()
            }
        }
    }
    
    // MARK: - Header View
    private var brandRedGradient: Gradient {
        Gradient(colors: [
            Color.zivoRed,                 // darker (left)
            Color.zivoRed.opacity(0.7)     // lighter (right)
        ])
    }
    
    private var headerView: some View {
        ZStack {
            LinearGradient(
                gradient: brandRedGradient,
                startPoint: .leading,
                endPoint: .trailing
            )
            .cornerRadius(20)
            
            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Hi \(userName.isEmpty ? "there" : userName)!")
                            .font(.title)
                            .fontWeight(.bold)
                            .foregroundColor(.white)
                        
                        Text("Here's your wellness summary for today")
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.9))
                    }
                    
                    Spacer()
                    
                    VStack(spacing: 4) {
                        if let score = healthScore {
                            Text("\(score)")
                                .font(.system(size: 40, weight: .bold))
                                .foregroundColor(.white)
                        } else {
                            Text("--")
                                .font(.system(size: 40, weight: .bold))
                                .foregroundColor(.white)
                        }
                        
                        Text(healthScoreLabel.isEmpty ? "Health Score" : healthScoreLabel)
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundColor(.white.opacity(0.9))
                    }
                    .padding(12)
                    .background(Color.white.opacity(0.2))
                    .cornerRadius(16)
                }
            }
            .padding(20)
        }
        .frame(height: 140)
        .cornerRadius(20)
        .padding(.horizontal, 16)
        .padding(.top, 8)
        .onTapGesture {
            showHealth360 = true
        }
    }
    
    // MARK: - AI Nutritionist Card
    private var aiNutritionistCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 12) {
                ZStack {
                    Circle()
                        .fill(Color.pink.opacity(0.2))
                        .frame(width: 60, height: 60)
                    
                    Image(systemName: "brain.head.profile")
                        .font(.system(size: 28))
                        .foregroundColor(.pink)
                }
                
                VStack(alignment: .leading, spacing: 4) {
                    Text("Talk to AI Nutritionist")
                        .font(.title3)
                        .fontWeight(.semibold)
                    
                    Text("Ask about today's meals or plan tomorrow")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
            }
            
            Button(action: {
                // Provide haptic + brief delay so press animation is perceptible
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.12) {
                    ChatViewModel.shared.createNewChat()
                    NotificationCenter.default.post(name: Notification.Name("SwitchToChatTab"), object: nil)
                }
            }) {
                HStack {
                    Spacer()
                    Text("Chat Now")
                        .font(.headline)
                        .foregroundColor(.white)
                    Image(systemName: "arrow.right")
                        .foregroundColor(.white)
                    Spacer()
                }
                .padding(.vertical, 14)
                .background(
                    LinearGradient(
                        gradient: brandRedGradient,
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .cornerRadius(12)
            }
            .buttonStyle(PressableScaleButtonStyle())
        }
        .padding(20)
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.05), radius: 8, x: 0, y: 4)
        .padding(.horizontal)
    }
    
    // MARK: - Quick Actions Section
    private var quickActionsSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Update Health Records for insights")
                .font(.title2)
                .fontWeight(.bold)
                .padding(.horizontal)
            
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    QuickActionIconButton(
                        icon: "fork.knife",
                        label: "Log Meal",
                        color: .pink,
                        action: {
                            if #available(iOS 16.0, *) {
                                showNutrition = true
                            } else {
                                showAddMeal = true
                            }
                        }
                    )
                    
                    QuickActionIconButton(
                        icon: "pills.fill",
                        label: "Prescription",
                        color: .purple,
                        action: {
                            showMedications = true
                        }
                    )
                    
                    QuickActionIconButton(
                        icon: "heart.fill",
                        label: "Vitals",
                        color: .red,
                        action: {
                            showVitals = true
                        }
                    )
                    
                QuickActionIconButton(
                    icon: "face.smiling",
                    label: "Feeling",
                    color: .orange,
                    action: {
                        showMentalHealth = true
                    }
                )
                    
                    QuickActionIconButton(
                        icon: "doc.text.fill",
                        label: "Biomarkers",
                        color: .teal,
                        action: {
                            showBiomarkers = true
                        }
                    )
                }
                .padding(.horizontal)
            }
        }
    }
    
    // MARK: - My Day Snapshot
    private var myDaySnapshot: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("My Day Snapshot")
                .font(.title2)
                .fontWeight(.bold)
                .padding(.horizontal)
            
            VStack(spacing: 16) {
                HStack(spacing: 16) {
                    // Calories
                    DayMetricCard(
                        icon: "flame.fill",
                        iconColor: .orange,
                        title: "Calories",
                        value: "\(Int(nutritionManager.todaysCalories))",
                        goal: calorieGoalString,
                        progress: calorieProgress
                    )
                    .onTapGesture {
                        showNutrition = true
                    }
                    
                    // Steps
                    DayMetricCard(
                        icon: "figure.walk",
                        iconColor: .pink,
                        title: "Steps",
                        value: getSteps(),
                        goal: "10,000",
                        progress: getStepsProgress()
                    )
                    .onTapGesture {
                        showActivitySleep = true
                    }
                }
                
                HStack(spacing: 16) {
                    // Heart Rate
                    DayMetricCard(
                        icon: "heart.fill",
                        iconColor: .red,
                        title: "Heart Rate",
                        value: getHeartRate(),
                        subtitle: getBloodPressure(),
                        progress: nil
                    )
                    .onTapGesture {
                        showVitals = true
                    }
                    
                    // Sleep
                    DayMetricCard(
                        icon: "moon.fill",
                        iconColor: .purple,
                        title: "Sleep",
                        value: getSleep(),
                        subtitle: "Good quality",
                        progress: nil
                    )
                    .onTapGesture {
                        showActivitySleep = true
                    }
                }
            }
            .padding(.horizontal)
        }
    }
    
    // MARK: - AI Insights Section
    private var aiInsightsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("AI Insights")
                .font(.title2)
                .fontWeight(.bold)
                .padding(.horizontal)
            
            if aiInsights.isEmpty {
                Text("Loading insights...")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .padding(.horizontal)
            } else {
                TabView(selection: $currentInsightIndex) {
                    ForEach(0..<aiInsights.count, id: \.self) { index in
                        AIInsightCard(insight: aiInsights[index])
                            .tag(index)
                    }
                }
                .frame(height: 100)
                .tabViewStyle(PageTabViewStyle(indexDisplayMode: .never))
                
                HStack {
                    Button(action: { withAnimation { currentInsightIndex = max(0, currentInsightIndex - 1) } }) {
                        Image(systemName: "chevron.left")
                            .foregroundColor(.secondary)
                    }
                    .disabled(currentInsightIndex == 0)
                    
                    Spacer()
                    
                    Text("\(currentInsightIndex + 1) / \(aiInsights.count)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Spacer()
                    
                    Button(action: { withAnimation { currentInsightIndex = min(aiInsights.count - 1, currentInsightIndex + 1) } }) {
                        Image(systemName: "chevron.right")
                            .foregroundColor(.secondary)
                    }
                    .disabled(currentInsightIndex == aiInsights.count - 1)
                }
                .padding(.horizontal, 40)
            }
        }
    }
    
    // MARK: - Plan & Appointments Section
    private var planAndAppointmentsSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Your Plan & Appointments")
                .font(.title2)
                .fontWeight(.bold)
                .padding(.horizontal)
            
            VStack(spacing: 16) {
                // First Row: Next Appointment and My Nutrition
                HStack(spacing: 16) {
                    // Next Appointment
                    if let nextAppt = nextAppointment {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Image(systemName: "calendar")
                                    .foregroundColor(.blue)
                                Text("Next")
                                    .font(.subheadline)
                                    .fontWeight(.medium)
                            }
                            
                            Text("Appointment")
                                .font(.headline)
                                .fontWeight(.semibold)
                            
                            Text("\(nextAppt.doctorName)")
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .lineLimit(1)
                            
                            Text(formatAppointmentDate(nextAppt.appointmentDate))
                                .font(.caption)
                                .foregroundColor(.secondary)
                            
                            Text(nextAppt.status.capitalized)
                                .font(.caption)
                                .foregroundColor(.blue)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(Color.blue.opacity(0.1))
                                .cornerRadius(8)
                        }
                        .padding()
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color(.systemBackground))
                        .cornerRadius(12)
                        .shadow(color: .black.opacity(0.05), radius: 4, x: 0, y: 2)
                    } else {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Image(systemName: "calendar")
                                    .foregroundColor(.gray)
                                Text("Next")
                                    .font(.subheadline)
                                    .fontWeight(.medium)
                                    .foregroundColor(.secondary)
                            }
                            
                            Text("Appointment")
                                .font(.headline)
                                .fontWeight(.semibold)
                            
                            Spacer()
                            
                            Text("No appointments scheduled")
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.leading)
                        }
                        .padding()
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color(.systemBackground))
                        .cornerRadius(12)
                        .shadow(color: .black.opacity(0.05), radius: 4, x: 0, y: 2)
                    }
                    
                    // Nutrition Plan
                    VStack(alignment: .leading, spacing: 8) {
                        Text("My Nutrition")
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundColor(.white)
                        
                        if let goalName = nutritionGoalsManager.activeGoalSummary?.goal?.goalName {
                            Text(goalName)
                                .font(.headline)
                                .fontWeight(.semibold)
                                .foregroundColor(.white)
                                .lineLimit(2)
                        } else {
                            Text("No Plan Active")
                                .font(.headline)
                                .fontWeight(.semibold)
                                .foregroundColor(.white.opacity(0.8))
                        }
                        
                        Spacer()
                        
                        Button(action: {
                            if #available(iOS 16.0, *) {
                                if nutritionGoalsManager.activeGoalSummary?.hasActiveGoal == true {
                                    nutritionGoalsManager.loadCurrentGoalDetail()
                                    showNutritionPlan = true
                                } else {
                                    showNutritionGoalSetup = true
                                }
                            }
                        }) {
                            Text(nutritionGoalsManager.activeGoalSummary?.hasActiveGoal == true ? "View Plan" : "Set Goal")
                                .font(.caption)
                                .fontWeight(.semibold)
                                .foregroundColor(Color.zivoRed)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(Color.white)
                                .cornerRadius(8)
                        }
                    }
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        LinearGradient(
                            gradient: brandRedGradient,
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .cornerRadius(12)
                    .shadow(color: .black.opacity(0.05), radius: 4, x: 0, y: 2)
                }
                
                // Second Row: Book Appointment Card
                Button(action: {
                    NotificationCenter.default.post(name: Notification.Name("SwitchToAppointmentsTab"), object: nil)
                }) {
                    HStack(spacing: 16) {
                        ZStack {
                            Circle()
                                .fill(Color.blue.opacity(0.2))
                                .frame(width: 60, height: 60)
                            
                            Image(systemName: "stethoscope")
                                .font(.system(size: 28))
                                .foregroundColor(.blue)
                        }
                        
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Book an Appointment")
                                .font(.headline)
                                .fontWeight(.semibold)
                                .foregroundColor(.primary)
                            
                            Text("Schedule a consultation with your doctor")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                        
                        Spacer()
                        
                        Image(systemName: "chevron.right")
                            .foregroundColor(.secondary)
                    }
                    .padding()
                    .background(Color(.systemBackground))
                    .cornerRadius(12)
                    .shadow(color: .black.opacity(0.05), radius: 4, x: 0, y: 2)
                }
                .buttonStyle(PlainButtonStyle())
            }
            .padding(.horizontal)
        }
    }
    
    // MARK: - Streak Section
    private var streakSection: some View {
        VStack(spacing: 12) {
            Image(systemName: "flame.fill")
                .font(.system(size: 40))
                .foregroundColor(.orange)
            
            Text("You've logged meals \(streakDays) days in a row — keep it up!")
                .font(.headline)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
            
            Button(action: {
                // Navigate to goal setting
            }) {
                Text("Set Next Goal")
                    .font(.headline)
                    .foregroundColor(.white)
                    .padding(.horizontal, 32)
                    .padding(.vertical, 14)
                    .background(
                        LinearGradient(
                            gradient: brandRedGradient,
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .cornerRadius(12)
            }
        }
        .padding(.vertical, 24)
        .padding(.horizontal)
        .background(Color.orange.opacity(0.05))
        .cornerRadius(16)
        .padding(.horizontal)
    }
    
    // MARK: - Helper Functions
    private func loadUserData() async {
        do {
            let profile = try await NetworkService.shared.fetchCombinedProfile()
            await MainActor.run {
                let first = profile.basic.first_name.trimmingCharacters(in: .whitespacesAndNewlines)
                if !first.isEmpty {
                    userName = first
                } else {
                    let full = profile.basic.full_name.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !full.isEmpty {
                        userName = full.split(separator: " ").map(String.init).first ?? ""
                    } else {
                        userName = ""
                    }
                }
            }
        } catch {
            // Fallback to any cached values we have
            await MainActor.run {
                if userName.isEmpty {
                    let full = NetworkService.shared.currentUserFullName ?? ""
                    userName = full.split(separator: " ").map(String.init).first ?? ""
                }
            }
        }
    }
    
    private func loadHealthScore() {
        healthScoreAPI.getToday()
            .receive(on: DispatchQueue.main)
            .sink(receiveCompletion: { _ in }, receiveValue: { json in
                if let score = json["overall"] as? Double {
                    healthScore = Int(score)
                    healthScoreLabel = getScoreLabel(Int(score))
                }
            })
            .store(in: &cancellables)
    }
    
    private func getScoreLabel(_ score: Int) -> String {
        switch score {
        case 90...100: return "Excellent"
        case 80..<90: return "Very Good"
        case 70..<80: return "Good"
        case 60..<70: return "Fair"
        default: return "Needs Work"
        }
    }
    
    private func loadAIInsights() {
        // Sample insights - replace with actual API call
        aiInsights = [
            AIInsight(icon: "fork.knife", emoji: "🔍", message: "Protein intake is low — add 20g more today", color: .orange),
            AIInsight(icon: "sun.max.fill", emoji: "☀️", message: "Your Vitamin D levels are low — schedule a check", color: .yellow)
        ]
    }
    
    // MARK: - Appointment Helpers
    private var nextAppointment: AppointmentWithDetails? {
        let upcoming = appointmentViewModel.upcomingAppointments()
        return upcoming.first // Returns the soonest upcoming appointment
    }
    
    private func formatAppointmentDate(_ date: Date) -> String {
        let calendar = Calendar.current
        let now = Date()
        
        // Check if appointment is today
        if calendar.isDateInToday(date) {
            let formatter = DateFormatter()
            formatter.timeStyle = .short
            return "Today at \(formatter.string(from: date))"
        }
        
        // Check if appointment is tomorrow
        if calendar.isDateInTomorrow(date) {
            let formatter = DateFormatter()
            formatter.timeStyle = .short
            return "Tomorrow at \(formatter.string(from: date))"
        }
        
        // Otherwise show full date
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
    
    // MARK: - Calorie Goal Helpers
    private var calorieGoal: Double {
        // Try to get the calorie goal from nutrition goals manager
        if let caloriesItem = nutritionGoalsManager.progressItems.first(where: { $0.nutrientKey == "calories" }),
           let targetMax = caloriesItem.targetMax {
            return targetMax
        }
        // Fallback to 2000 if no goal is set
        return 2000
    }
    
    private var calorieGoalString: String {
        return "\(Int(calorieGoal))"
    }
    
    private var calorieProgress: Double {
        return min(nutritionManager.todaysCalories / calorieGoal, 1.0)
    }
    
    private func getSteps() -> String {
        return VitalsDisplayHelper.getLatestSteps(from: healthKitManager.dashboardData)
    }
    
    private func getStepsProgress() -> Double {
        return VitalsDisplayHelper.getStepsProgress(from: healthKitManager.dashboardData)
    }
    
    private func getHeartRate() -> String {
        if let dashboardData = healthKitManager.dashboardData,
           let heartRateMetric = dashboardData.metrics.first(where: { $0.metricType == .heartRate }),
           let latestValue = heartRateMetric.latestValue {
            return "\(Int(latestValue)) bpm"
        }
        return "66 bpm"
    }
    
    private func getBloodPressure() -> String {
        if let dashboardData = healthKitManager.dashboardData {
            let systolicMetric = dashboardData.metrics.first(where: { $0.metricType == .bloodPressureSystolic })
            let diastolicMetric = dashboardData.metrics.first(where: { $0.metricType == .bloodPressureDiastolic })
            
            if let systolic = systolicMetric?.latestValue,
               let diastolic = diastolicMetric?.latestValue {
                return "\(Int(systolic))/\(Int(diastolic)) BP"
            }
        }
        return "120/85 BP"
    }
    
    private func getSleep() -> String {
        return VitalsDisplayHelper.getLatestSleep(from: healthKitManager.dashboardData)
    }
}

// MARK: - Supporting Views

// Subtle press animation for buttons
struct PressableScaleButtonStyle: ButtonStyle {
    var scaleAmount: CGFloat = 0.96
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? scaleAmount : 1.0)
            .opacity(configuration.isPressed ? 0.85 : 1.0)
            .animation(.spring(response: 0.2, dampingFraction: 0.6), value: configuration.isPressed)
    }
}

struct QuickActionIconButton: View {
    let icon: String
    let label: String
    let color: Color
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                ZStack {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color(.systemBackground))
                        .frame(width: 60, height: 60)
                        .shadow(color: .black.opacity(0.05), radius: 4, x: 0, y: 2)
                    
                    Image(systemName: icon)
                        .font(.system(size: 24))
                        .foregroundColor(color)
                }
                
                Text(label)
                    .font(.caption)
                    .foregroundColor(.primary)
            }
        }
    }
}

struct DayMetricCard: View {
    let icon: String
    let iconColor: Color
    let title: String
    let value: String
    var goal: String? = nil
    var subtitle: String? = nil
    var progress: Double? = nil
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(iconColor)
                    .font(.title3)
                
                Spacer()
            }
            
            Text(title)
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            if let goal = goal {
                Text("\(value) / \(goal)")
                    .font(.headline)
                    .fontWeight(.semibold)
            } else {
                Text(value)
                    .font(.headline)
                    .fontWeight(.semibold)
            }
            
            if let subtitle = subtitle {
                Text(subtitle)
                    .font(.caption)
                    .foregroundColor(.green)
            }
            
            if let progress = progress {
                GeometryReader { geometry in
                    ZStack(alignment: .leading) {
                        Rectangle()
                            .fill(Color.gray.opacity(0.2))
                            .frame(height: 4)
                            .cornerRadius(2)
                        
                        Rectangle()
                            .fill(iconColor)
                            .frame(width: geometry.size.width * progress, height: 4)
                            .cornerRadius(2)
                    }
                }
                .frame(height: 4)
            }
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 4, x: 0, y: 2)
    }
}

struct AIInsight: Identifiable {
    let id = UUID()
    let icon: String
    let emoji: String
    let message: String
    let color: Color
}

struct AIInsightCard: View {
    let insight: AIInsight
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "magnifyingglass")
                .font(.title2)
                .foregroundColor(.secondary)
            
            Text("\(insight.emoji) \(insight.message)")
                .font(.subheadline)
                .foregroundColor(.primary)
            
            Spacer()
            
            Button(action: {
                NotificationCenter.default.post(name: Notification.Name("SwitchToChatTab"), object: nil)
            }) {
                Text("Ask AI")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(.pink)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(Color.pink.opacity(0.1))
                    .cornerRadius(8)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 4, x: 0, y: 2)
        .padding(.horizontal)
    }
}

#Preview {
    HomeView()
}

// MARK: - Mental Health Log Mood Sheet

struct MentalHealthLogMoodSheet: View {
    @Environment(\.dismiss) private var dismiss
    @StateObject private var service = MentalHealthService.shared
    @State private var entryType: MentalHealthEntryType = .emotionNow
    @State private var pleasantness: Int = 1
    @State private var selectedFeelings = Set<String>()
    @State private var selectedImpacts = Set<String>()
    @State private var notes: String = ""
    @State private var step: Int = 0 // 0: Type, 1: Pleasantness, 2: Feelings, 3: Impacts

    private var canSave: Bool {
        return !selectedFeelings.isEmpty && !selectedImpacts.isEmpty
    }
    
    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Progress bar
                ProgressView(value: Double(step + 1), total: 4)
                    .progressViewStyle(.linear)
                    .tint(.accentColor)
                    .padding(.horizontal)
                    .padding(.top, 8)
                
                // Step content
                Group {
                    switch step {
                    case 0:
                        Form {
                            Section(header: Text("Type")) {
                                Picker("Entry Type", selection: $entryType) {
                                    Text("How you feel right now").tag(MentalHealthEntryType.emotionNow)
                                    Text("How you felt today").tag(MentalHealthEntryType.moodToday)
                                }
                                .pickerStyle(.inline)
                            }
                        }
                    case 1:
                        Form {
                            Section(header: Text("Pleasantness")) {
                                Stepper(value: $pleasantness, in: -3...3) {
                                    Text("\(service.labelForScore(pleasantness)) (\(pleasantness))")
                                }
                            }
                        }
                    case 2:
                        // Full-page list for Feelings
                        MentalHealthMultiSelectList(all: service.mentalhealth_feelings, selected: $selectedFeelings)
                            .listStyle(.insetGrouped)
                    default:
                        // Full-page list for Impacts
                        MentalHealthMultiSelectList(all: service.mentalhealth_impact, selected: $selectedImpacts)
                            .listStyle(.insetGrouped)
                    }
                }
                
                // Navigation controls
                HStack {
                    Button("Back") {
                        if step > 0 { step -= 1 }
                    }
                    .disabled(step == 0)
                    Spacer()
                    if step < 3 {
                        Button("Next") {
                            if step == 2 {
                                // Require at least one feeling before proceeding
                                if selectedFeelings.isEmpty { return }
                            }
                            step += 1
                        }
                        .disabled(step == 2 && selectedFeelings.isEmpty)
                        .buttonStyle(.borderedProminent)
                    } else {
                        Button("Save") { save() }
                            .disabled(!canSave)
                            .buttonStyle(.borderedProminent)
                    }
                }
                .padding()
            }
            .navigationTitle("Log Mood")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } }
            }
        }
    }
    
    private func save() {
        let entry = MentalHealthEntry(
            id: UUID(),
            userId: "me",
            recordedAt: Date(),
            entryType: entryType,
            pleasantnessScore: pleasantness,
            pleasantnessLabel: service.labelForScore(pleasantness),
            feelings: Array(selectedFeelings),
            impacts: Array(selectedImpacts),
            notes: notes.isEmpty ? nil : notes
        )
        service.createEntryViaAPI(from: entry)
        service.saveEntry(entry)
        dismiss()
    }
}

struct MentalHealthMultiSelectList: View {
    let all: [String]
    @Binding var selected: Set<String>

    var body: some View {
        List {
            ForEach(all, id: \.self) { item in
                Button(action: { toggle(item) }) {
                    HStack {
                        Text(item)
                            .foregroundColor(.primary)
                        Spacer()
                        if selected.contains(item) {
                            Image(systemName: "checkmark")
                                .foregroundColor(.accentColor)
                        }
                    }
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func toggle(_ item: String) {
        if selected.contains(item) {
            selected.remove(item)
        } else {
            selected.insert(item)
        }
    }
}
