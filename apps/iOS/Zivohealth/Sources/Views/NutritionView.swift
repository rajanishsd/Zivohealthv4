import SwiftUI
import Charts
import PhotosUI
import Combine

@available(iOS 16.0, *)
struct NutritionView: View {
    @StateObject private var nutritionManager = NutritionManager.shared
    @StateObject private var nutritionGoalsManager = NutritionGoalsManager.shared
    @State private var showingAddMeal = false
    @State private var navigateToAddMeal = false
    @State private var selectedTab = 0
    @State private var selectedDate = Date()
    
    // Chart legend selection states
    @State private var showCalories = true
    @State private var showProtein = true
    @State private var showCarbs = true
    @State private var showFat = true
    @State private var showFiber = true
    
    // Vitamin chart selection states
    @State private var showVitaminA = true
    @State private var showVitaminC = true
    @State private var showVitaminD = true
    @State private var showVitaminE = false
    @State private var showVitaminK = false
    @State private var showVitaminB1 = false
    @State private var showVitaminB2 = false
    @State private var showVitaminB3 = false
    @State private var showVitaminB6 = false
    @State private var showVitaminB12 = false
    @State private var showFolate = false
    
    // Mineral chart selection states
    @State private var showCalcium = true
    @State private var showIron = true
    @State private var showMagnesium = true
    @State private var showPhosphorus = false
    @State private var showPotassium = false
    @State private var showZinc = false
    @State private var showCopper = false
    @State private var showManganese = false
    @State private var showSelenium = false
    
    // Image selection - iOS 16+ and fallback
    @State private var selectedPhoto: Any? // Will be PhotosPickerItem? on iOS 16+
    @State private var selectedImageData: Data?
    @State private var selectedImage: UIImage?
    
    // Detailed meal view
    @State private var showingMealDetail = false
    @State private var selectedMealForDetail: NutritionDataResponse?
    
    // Meal type detail view
    @State private var showingMealTypeDetail = false
    @State private var selectedMealTypeGroupForDetail: MealTypeGroup?
    
    // Goal setup view
    @State private var navigateToGoalSetup = false
    @State private var navigateToGoalDetail = false
    @State private var navigateToManagePlans = false
    @State private var navigateToMealsList = false
    
    var body: some View {
        GeometryReader { geometry in
            ScrollView {
                VStack(spacing: 0) {
                    // Scrollable header
                    NutritionHeaderView(topInset: geometry.safeAreaInsets.top)
                    
                    // Content
                    overviewContent
                }
            }
            .background(Color(.systemGroupedBackground))
            .ignoresSafeArea(.container, edges: .top)
            
            .sheet(isPresented: $showingMealDetail) {
                if let meal = selectedMealForDetail {
                    MealDetailView(meal: meal)
                }
            }
            .sheet(isPresented: $showingMealTypeDetail) {
                if let group = selectedMealTypeGroupForDetail {
                    NavigationView {
                        MealTypeSummaryView(group: group)
                    }
                }
            }
            // Navigation to Nutrition Goal Setup (push, not sheet)
            .background(
                NavigationLink(
                    destination: NutritionGoalSetupView(),
                    isActive: $navigateToGoalSetup,
                    label: { EmptyView() }
                )
                .hidden()
            )
            .background(
                NavigationLink(
                    destination: AddMealView(),
                    isActive: $navigateToAddMeal,
                    label: { EmptyView() }
                )
                .hidden()
            )
            .background(
                NavigationLink(
                    destination: MealsListView(nutritionManager: nutritionManager),
                    isActive: $navigateToMealsList,
                    label: { EmptyView() }
                )
                .hidden()
            )
            .onAppear {
                // Only load data if user is authenticated
                guard NetworkService.shared.isAuthenticated() else {
                    print("⚠️ [NutritionView] User not authenticated - skipping data load")
                    return
                }
                
                nutritionManager.loadTodaysData()
                nutritionGoalsManager.loadGoalsData()
                // Ensure progress fetch triggers on first render when goal already active
                if nutritionGoalsManager.activeGoalSummary?.hasActiveGoal == true {
                    nutritionGoalsManager.loadActiveGoalProgress()
                }
                // Load meals for today when view appears
                loadMealsForDate(selectedDate)
            }
        }
        .navigationBarHidden(true)
    }
    
    // MARK: - Computed Properties
    
    // Get daily calorie goal
    private var dailyCalorieGoal: Double {
        if let caloriesItem = nutritionGoalsManager.progressItems.first(where: { $0.nutrientKey == "calories" }),
           let targetMax = caloriesItem.targetMax {
            return targetMax
        }
        return 2000 // Fallback default
    }
    
    // Get color for calories based on target
    private func getCaloriesColor(current: Double, target: Double) -> Color {
        let percentage = current / target
        
        if percentage <= 1.1 {
            // On target or slightly over (within 10%)
            return .green
        } else if percentage <= 1.25 {
            // Moderately over (10-25% over)
            return .orange
        } else {
            // Significantly over (more than 25% over)
            return .red
        }
    }
    
    // Filter meals for the selected date
    private var filteredMealsForSelectedDate: [NutritionDataResponse] {
        let calendar = Calendar.current
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        
        return nutritionManager.nutritionData.filter { meal in
            guard let mealDate = formatter.date(from: meal.mealDate) else { return false }
            return calendar.isDate(mealDate, inSameDayAs: selectedDate)
        }
    }
    
    private var overviewContent: some View {
        LazyVStack(spacing: 16) {
            // Today's summary card
            todaysSummaryCard
                .cardStyle()
            
            // Log meal button (prominent)
            logMealCard
            
            // Nutrition goals card
            nutritionGoalsCard
                .cardStyle()
            
            // Charts container
            NutritionChartsContainer(nutritionManager: nutritionManager)
            
            // Recent meals preview card
            recentMealsPreview
                .cardStyle()
            
            Spacer(minLength: 100)
        }
        .padding(.horizontal)
        .padding(.top, 8)
    }
    
    private var todaysSummaryCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Card Header
            HStack {
                Image(systemName: "calendar.circle.fill")
                    .foregroundColor(.red)
                    .font(.title2)
            Text("Today's Summary")
                    .font(.title3)
                    .fontWeight(.semibold)
                Spacer()
                Text(Date().formatted(date: .abbreviated, time: .omitted))
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            // Calories row
            HStack {
                VStack(alignment: .leading) {
                    Text("Calories")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("\(Int(nutritionManager.todaysCalories))")
                        .font(.system(size: 44, weight: .bold))
                        .foregroundColor(getCaloriesColor(current: nutritionManager.todaysCalories, target: dailyCalorieGoal))
                }
                
                Spacer()
                
                VStack(alignment: .trailing) {
                    Text("Meals")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("\(nutritionManager.todaysMealCount)")
                        .font(.title3)
                        .fontWeight(.medium)
                }
            }
            
            Divider()
            
            // Macronutrients grid
            VStack(spacing: 8) {
                HStack(spacing: 0) {
                    // Protein
                    VStack(spacing: 2) {
                        Text("Protein")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text("\(Int(nutritionManager.todaysProtein))g")
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundColor(.red)
                    }
                    .frame(maxWidth: .infinity)
                    
                    // Carbs
                    VStack(spacing: 2) {
                        Text("Carbs")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text("\(Int(nutritionManager.todaysCarbs))g")
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundColor(.blue)
                    }
                    .frame(maxWidth: .infinity)
                    
                    // Fat
                    VStack(spacing: 2) {
                        Text("Fat")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text("\(Int(nutritionManager.todaysFat))g")
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundColor(.yellow)
                    }
                    .frame(maxWidth: .infinity)
                }
                
                HStack(spacing: 0) {
                    // Fiber
                    VStack(spacing: 2) {
                        Text("Fiber")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text("\(Int(nutritionManager.todaysFiber))g")
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundColor(.green)
                    }
                    .frame(maxWidth: .infinity)
                    
                    // Sugar
                    VStack(spacing: 2) {
                        Text("Sugar")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text("\(Int(nutritionManager.todaysSugar))g")
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundColor(.pink)
                    }
                    .frame(maxWidth: .infinity)
                    
                    // Sodium
                    VStack(spacing: 2) {
                        Text("Sodium")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text("\(Int(nutritionManager.todaysSodium))mg")
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundColor(.purple)
                    }
                    .frame(maxWidth: .infinity)
                }
            }
        }
        .padding()
    }
    
    private var logMealCard: some View {
        Button(action: { navigateToAddMeal = true }) {
            HStack(spacing: 8) {
                Image(systemName: "plus.circle.fill")
                    .font(.title3)
                Text("Log a Meal")
                    .font(.headline)
                    .fontWeight(.semibold)
            }
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(Color.green)
            .cornerRadius(12)
        }
        .buttonStyle(.plain)
        .padding(.horizontal)
    }
    
    private var nutritionGoalsCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Card Header
            HStack {
                Image(systemName: "target")
                    .foregroundColor(.green)
                    .font(.title2)
                
                if let summary = nutritionGoalsManager.activeGoalSummary, summary.hasActiveGoal {
                    // Show goal name if available; fallback to generic title
                    Text(summary.goal?.goalName ?? "Nutrition Goals")
                        .font(.title3)
                        .fontWeight(.semibold)
                } else {
                    Text("Nutrition Goals")
                        .font(.title3)
                        .fontWeight(.semibold)
                }
                
                Spacer()
                
                // Show different UI based on goal status
                if let summary = nutritionGoalsManager.activeGoalSummary, summary.hasActiveGoal {
                    // Goal exists - show options menu
                    Menu {
                        Button("View Plan Details") {
                            nutritionGoalsManager.loadCurrentGoalDetail()
                            navigateToGoalDetail = true
                        }
                        Button("Manage Plans") {
                            navigateToManagePlans = true
                        }
                        Button("Create New Plan") {
                            navigateToGoalSetup = true
                        }
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: "gearshape.fill")
                                .font(.caption)
                            Text("Options")
                                .font(.caption)
                                .fontWeight(.medium)
                        }
                        .foregroundColor(.blue)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.blue.opacity(0.1))
                        .cornerRadius(6)
                    }
                } else {
                    // No goal - show prominent button to create
                    Button(action: {
                        navigateToGoalSetup = true
                    }) {
                        HStack(spacing: 4) {
                            Image(systemName: "plus.circle.fill")
                                .font(.caption)
                            Text("Set Goal")
                                .font(.caption)
                                .fontWeight(.medium)
                        }
                        .foregroundColor(.white)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.blue)
                        .cornerRadius(6)
                    }
                    .buttonStyle(.plain)
                }
                
                if nutritionGoalsManager.isLoading {
                    ProgressView()
                        .scaleEffect(0.8)
                }
            }
            
            if let summary = nutritionGoalsManager.activeGoalSummary, summary.hasActiveGoal {
                // Show progress for active goal
                if nutritionGoalsManager.progressItems.isEmpty {
                    Text("Loading progress...")
                        .foregroundColor(.secondary)
                        .padding(.vertical)
                } else {
                    VStack(spacing: 12) {
                        ForEach(nutritionGoalsManager.progressItems.prefix(5)) { item in
                            nutritionGoalProgressRow(item: item)
                        }
                    }
                }
            } else {
                // Show "Set Goal" state
                VStack(spacing: 12) {
                    Image(systemName: "target")
                        .font(.title)
                        .foregroundColor(.gray)
                    
                    Text("No active nutrition goal")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    Text("Tap 'Set Goal' above to create your nutrition plan")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.vertical, 8)
            }
            
            if let errorMessage = nutritionGoalsManager.errorMessage {
                Text("Error: \(errorMessage)")
                    .font(.caption)
                    .foregroundColor(.red)
                    .padding(.top, 4)
            }
        }
        .padding()
        .contentShape(Rectangle())
        .onTapGesture {
            if nutritionGoalsManager.activeGoalSummary?.hasActiveGoal == true {
                nutritionGoalsManager.loadCurrentGoalDetail()
                navigateToGoalDetail = true
            } else {
                navigateToGoalSetup = true
            }
        }
        .background(
            NavigationLink(
                destination: NutritionGoalDetailView(),
                isActive: $navigateToGoalDetail,
                label: { EmptyView() }
            )
            .hidden()
        )
        .background(
            NavigationLink(
                destination: ManageNutritionPlansView(),
                isActive: $navigateToManagePlans,
                label: { EmptyView() }
            )
            .hidden()
        )
    }
    
    private func nutritionProgressRow(title: String, current: Double, goal: Double, unit: String, color: Color) -> some View {
        VStack(spacing: 4) {
            HStack {
                Text(title)
                    .font(.subheadline)
                    .fontWeight(.medium)
                Spacer()
                Text("\(Int(current))/\(Int(goal)) \(unit)")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    Rectangle()
                        .fill(Color.gray.opacity(0.2))
                        .frame(height: 6)
                        .cornerRadius(3)
                    
                    Rectangle()
                        .fill(color)
                        .frame(width: geometry.size.width * min(current / goal, 1.0), height: 6)
                        .cornerRadius(3)
                }
            }
            .frame(height: 6)
        }
    }
    
    private func nutritionGoalProgressRow(item: ProgressItem) -> some View {
        VStack(spacing: 4) {
            HStack {
                Text(item.displayName)
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                if item.priority == "primary" {
                    Image(systemName: "star.fill")
                        .font(.caption2)
                        .foregroundColor(.yellow)
                }
                
                Spacer()
                
                HStack(spacing: 4) {
                    if let current = item.currentValue {
                        Text("\(Int(current))")
                            .font(.subheadline)
                            .fontWeight(.medium)
                    } else {
                        Text("--")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                    
                    Text("/ \(item.targetDisplayText)")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
            }
            
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    Rectangle()
                        .fill(Color.gray.opacity(0.2))
                        .frame(height: 6)
                        .cornerRadius(3)
                    
                    Rectangle()
                        .fill(item.progressColor)
                        .frame(width: geometry.size.width * item.progressValue, height: 6)
                        .cornerRadius(3)
                }
            }
            .frame(height: 6)
            
            // Status indicator
            if let status = item.status {
                HStack {
                    Spacer()
                    Text(item.statusText)
                        .font(.caption2)
                        .foregroundColor(item.progressColor)
                        .fontWeight(.medium)
                }
            }
        }
    }
    
    private var recentMealsPreview: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Card Header
            HStack {
                Image(systemName: "fork.knife.circle.fill")
                    .foregroundColor(.purple)
                    .font(.title2)
                Text("Today's Meals by Type")
                    .font(.title3)
                    .fontWeight(.semibold)
                Spacer()
                Button("See All") {
                    navigateToMealsList = true
                }
                .font(.subheadline)
                .foregroundColor(.blue)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Color.blue.opacity(0.1))
                .cornerRadius(8)
            }
            
            if todaysMealTypeGroups.isEmpty {
                Text("No meals logged yet")
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding()
            } else {
                ForEach(todaysMealTypeGroups.prefix(2)) { group in
                    compactMealTypeCard(group)
                        .onTapGesture {
                            selectedMealTypeGroupForDetail = group
                            showingMealTypeDetail = true
                        }
                }
            }
        }
        .padding()
    }
    
    // Computed property for today's meal type groups
    private var todaysMealTypeGroups: [MealTypeGroup] {
        nutritionManager.todaysMeals.groupedByMealType()
    }
    
    // Compact meal type card for preview
    private func compactMealTypeCard(_ group: MealTypeGroup) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Text(group.mealType.emoji)
                    .font(.title2)
                Text(group.mealType.displayName)
                    .font(.headline)
                    .fontWeight(.semibold)
                Spacer()
                Text("\(group.mealCount) meal\(group.mealCount > 1 ? "s" : "")")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            // Calories and macros
            HStack {
                HStack(spacing: 4) {
                    Image(systemName: "flame.fill")
                        .font(.caption)
                        .foregroundColor(.orange)
                    Text("\(Int(group.totalCalories))")
                        .font(.subheadline)
                        .fontWeight(.bold)
                        .foregroundColor(.orange)
                }
                
                Spacer()
                
                nutritionBadge("P", value: Int(group.totalProtein), unit: "g", color: .red)
                nutritionBadge("C", value: Int(group.totalCarbs), unit: "g", color: .blue)
                nutritionBadge("F", value: Int(group.totalFat), unit: "g", color: .yellow)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
    }
    
    private func mealRow(_ meal: NutritionDataResponse) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    // Meal type and time
                    HStack(spacing: 8) {
                        Text(meal.mealType.emoji)
                            .font(.title3)
                        Text(meal.mealType.displayName)
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundColor(.secondary)
                        
                        Spacer()
                        
                        if let mealTime = meal.mealDateTime {
                            Text(mealTime, style: .time)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    
                    // Dish name
                    Text(meal.displayName)
                        .font(.headline)
                        .fontWeight(.semibold)
                        .lineLimit(2)
                    
                    // Calories
                    Text("\(Int(meal.calories)) calories")
                        .font(.subheadline)
                        .foregroundColor(.orange)
                        .fontWeight(.medium)
                }
                
                Spacer()
                
                // Tap indicator
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            // Macronutrients badges
            HStack {
                nutritionBadge("P", value: Int(meal.proteinG), unit: "g", color: .red)
                nutritionBadge("C", value: Int(meal.carbsG), unit: "g", color: .blue)
                nutritionBadge("F", value: Int(meal.fatG), unit: "g", color: .yellow)
                
                if meal.fiberG > 0 {
                    nutritionBadge("Fiber", value: Int(meal.fiberG), unit: "g", color: .green)
                }
                
                Spacer()
                
                // Image button
                Button(action: {
                    selectedMealForDetail = meal
                    showingMealDetail = true
                }) {
                    HStack(spacing: 4) {
                        if meal.dataSource == .photoAnalysis && meal.imageUrl != nil {
                            Image(systemName: "photo.fill")
                                .font(.caption)
                                .foregroundColor(.blue)
                            Text("View Image")
                                .font(.caption2)
                                .foregroundColor(.blue)
                        } else {
                            Image(systemName: "text.cursor")
                                .font(.caption)
                                .foregroundColor(.gray)
                            Text("Manual Entry")
                                .font(.caption2)
                                .foregroundColor(.gray)
                        }
                    }
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(
                        RoundedRectangle(cornerRadius: 6)
                            .fill(meal.dataSource == .photoAnalysis && meal.imageUrl != nil ? Color.blue.opacity(0.1) : Color.gray.opacity(0.1))
                    )
                }
                .buttonStyle(.plain)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
    }
    
    private func nutritionBadge(_ label: String, value: Int, unit: String, color: Color) -> some View {
        HStack(spacing: 2) {
            Text(label)
                .font(.caption2)
                .fontWeight(.medium)
                .foregroundColor(color)
            Text("\(value)\(unit)")
                .font(.caption2)
                .foregroundColor(.secondary)
        }
    }
    
    private func dataSourceBadge(_ source: NutritionDataSource) -> some View {
        HStack(spacing: 2) {
            Image(systemName: source == .photoAnalysis ? "camera.fill" : "keyboard.fill")
                .font(.caption2)
                .foregroundColor(.secondary)
            
            if source == .photoAnalysis {
                Text("AI Analyzed")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
        }
    }
    
    // MARK: - Private Methods
    private func loadMealsForDate(_ date: Date) {
        let startOfDay = Calendar.current.startOfDay(for: date)
        let endOfDay = Calendar.current.date(byAdding: .day, value: 1, to: startOfDay) ?? date
        
        nutritionManager.loadNutritionData(
            startDate: startOfDay,
            endDate: endOfDay,
            granularity: .daily
        )
    }
}

// Nutrition header
struct NutritionHeaderView: View {
    let topInset: CGFloat
    @Environment(\.dismiss) private var dismiss
    
    private var brandRedGradient: Gradient {
        Gradient(colors: [
            Color.zivoRed,                 // darker (left)
            Color.zivoRed.opacity(0.7)     // lighter (right)
        ])
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Top spacer for status bar
            Color.clear
                .frame(height: topInset)
            
            // Card content with back button
            ZStack(alignment: .topLeading) {
                LinearGradient(
                    gradient: brandRedGradient,
                    startPoint: .leading,
                    endPoint: .trailing
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)

                ZStack {
                    // Centered title and subtitle with offset to move down
                    VStack(spacing: 4) {
                        Text("Nutrition")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(.white)
                        
                        Text("Track your meals and nutrition goals")
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.9))
                    }
                    .offset(y: 15)
                    
                    // Back button on the left, vertically centered
                    HStack {
                        Button(action: {
                            dismiss()
                        }) {
                            Image(systemName: "arrow.backward")
                                .font(.system(size: 20, weight: .semibold))
                                .foregroundColor(.white)
                        }
                        .padding(.leading, 20)
                        
                        Spacer()
                    }
                    .offset(y: 10)
                    
                    // Fork and knife icon on the right, vertically centered
                    HStack {
                        Spacer()
                        
                        Image(systemName: "fork.knife")
                            .font(.system(size: 40))
                            .foregroundColor(.white.opacity(0.9))
                            .padding(.trailing, 20)
                    }
                }
                .padding(.vertical, 20)
            }
            .frame(height: 110)
            .cornerRadius(20)
            .padding(.horizontal, 16)
            .padding(.top, 0)
        }
        .frame(height: 110 + topInset + 0)
        .ignoresSafeArea(.container, edges: .top)
    }
}

// MARK: - Meals List View (Separate Page)
struct MealsListView: View {
    @ObservedObject var nutritionManager: NutritionManager
    @State private var selectedDate = Date()
    @State private var showingMealTypeSummary = false
    @State private var selectedMealTypeGroup: MealTypeGroup?
    @Environment(\.dismiss) private var dismiss
    
    // Filter meals for the selected date
    private var filteredMealsForSelectedDate: [NutritionDataResponse] {
        let calendar = Calendar.current
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        
        return nutritionManager.nutritionData.filter { meal in
            guard let mealDate = formatter.date(from: meal.mealDate) else { return false }
            return calendar.isDate(mealDate, inSameDayAs: selectedDate)
        }
    }
    
    // Group meals by meal type
    private var mealTypeGroups: [MealTypeGroup] {
        filteredMealsForSelectedDate.groupedByMealType()
    }
    
    var body: some View {
        GeometryReader { geometry in
            ScrollView {
                VStack(spacing: 0) {
                    // Scrollable header
                    MealsListHeaderView(topInset: geometry.safeAreaInsets.top)
                    
                    // Content
                    LazyVStack(spacing: 16) {
                        // Date picker header card
                        VStack(spacing: 12) {
                            HStack {
                                Text("Select Date")
                                    .font(.headline)
                                    .fontWeight(.semibold)
                                Spacer()
                            }
                            
                            DatePicker(
                                "Meal Date",
                                selection: $selectedDate,
                                in: ...Date(),
                                displayedComponents: .date
                            )
                            .datePickerStyle(.compact)
                            .onChange(of: selectedDate) { newDate in
                                loadMealsForDate(newDate)
                            }
                        }
                        .padding()
                        .background(Color(.systemBackground))
                        .cornerRadius(12)
                        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
                        .padding(.horizontal)
                        
                        // Meal type groups as page view (Level 1)
                        if mealTypeGroups.isEmpty {
                            VStack(spacing: 8) {
                                Image(systemName: "fork.knife")
                                    .font(.title2)
                                    .foregroundColor(.secondary)
                                Text("No meals found for \(selectedDate.formatted(date: .abbreviated, time: .omitted))")
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                                    .multilineTextAlignment(.center)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 40)
                        } else {
                            VStack(alignment: .leading, spacing: 12) {
                                HStack {
                                    Image(systemName: "square.grid.2x2.fill")
                                        .foregroundColor(.purple)
                                    Text("Meals by Type")
                                        .font(.headline)
                                        .fontWeight(.bold)
                                    Spacer()
                                }
                                .padding(.horizontal)
                                
                                // Vertical stacked meal type cards
                                VStack(spacing: 16) {
                                    ForEach(mealTypeGroups) { group in
                                        MealTypeCard(group: group) {
                                            selectedMealTypeGroup = group
                                            showingMealTypeSummary = true
                                        }
                                    }
                                }
                                .padding(.horizontal)
                            }
                        }
                    }
                    .padding(.top, 8)
                }
            }
            .background(Color(.systemGroupedBackground))
            .ignoresSafeArea(.container, edges: .top)
        }
        .navigationBarHidden(true)
        .sheet(isPresented: $showingMealTypeSummary) {
            if let group = selectedMealTypeGroup {
                NavigationView {
                    MealTypeSummaryView(group: group)
                }
            }
        }
        .onAppear {
            loadMealsForDate(selectedDate)
        }
    }
    
    private func loadMealsForDate(_ date: Date) {
        let startOfDay = Calendar.current.startOfDay(for: date)
        let endOfDay = Calendar.current.date(byAdding: .day, value: 1, to: startOfDay) ?? date
        
        nutritionManager.loadNutritionData(
            startDate: startOfDay,
            endDate: endOfDay,
            granularity: .daily
        )
    }
}

// Meals List Header
struct MealsListHeaderView: View {
    let topInset: CGFloat
    @Environment(\.dismiss) private var dismiss
    
    private var brandRedGradient: Gradient {
        Gradient(colors: [
            Color.zivoRed,                 // darker (left)
            Color.zivoRed.opacity(0.7)     // lighter (right)
        ])
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Top spacer for status bar
            Color.clear
                .frame(height: topInset)
            
            // Card content with back button
            ZStack(alignment: .topLeading) {
                LinearGradient(
                    gradient: brandRedGradient,
                    startPoint: .leading,
                    endPoint: .trailing
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)

                ZStack {
                    // Centered title and subtitle with offset to move down
                    VStack(spacing: 4) {
                        Text("Meals")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(.white)
                        
                        Text("View all your logged meals")
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.9))
                    }
                    .offset(y: 15)
                    
                    // Back button on the left, vertically centered
                    HStack {
                        Button(action: {
                            dismiss()
                        }) {
                            Image(systemName: "arrow.backward")
                                .font(.system(size: 20, weight: .semibold))
                                .foregroundColor(.white)
                        }
                        .padding(.leading, 20)
                        
                        Spacer()
                    }
                    .offset(y: 10)
                    
                    // List icon on the right, vertically centered
                    HStack {
                        Spacer()
                        
                        Image(systemName: "list.bullet")
                            .font(.system(size: 40))
                            .foregroundColor(.white.opacity(0.9))
                            .padding(.trailing, 20)
                    }
                }
                .padding(.vertical, 20)
            }
            .frame(height: 110)
            .cornerRadius(20)
            .padding(.horizontal, 16)
            .padding(.top, 0)
        }
        .frame(height: 110 + topInset + 0)
        .ignoresSafeArea(.container, edges: .top)
    }
}

@available(iOS 16.0, *)
struct NutritionView_Previews: PreviewProvider {
    static var previews: some View {
        NutritionView()
    }
}
