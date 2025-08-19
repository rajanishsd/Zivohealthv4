import SwiftUI
import Charts
import PhotosUI
import Combine

@available(iOS 16.0, *)
struct NutritionView: View {
    @StateObject private var nutritionManager = NutritionManager.shared
    @State private var showingAddMeal = false
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
    
    // Food image viewer
    @State private var showingImageViewer = false
    @State private var selectedMealForImage: NutritionDataResponse?
    
    // Detailed meal view
    @State private var showingMealDetail = false
    @State private var selectedMealForDetail: NutritionDataResponse?
    
    var body: some View {
            VStack(spacing: 0) {
                // Main Content
                TabView(selection: $selectedTab) {
                    // Overview Tab
                    overviewTab
                        .tabItem {
                            Image(systemName: "chart.bar.fill")
                            Text("Overview")
                        }
                        .tag(0)
                    
                    // Meals List Tab
                    mealsListTab
                        .tabItem {
                            Image(systemName: "list.bullet")
                            Text("Meals")
                        }
                        .tag(1)
                }
            .id("NutritionTabView")
            }
            .toolbar(content: {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: {
                        showingAddMeal = true
                    }) {
                        Image(systemName: "plus")
                    }
                }
            })
            .sheet(isPresented: $showingAddMeal) {
                AddMealView()
            }
            .sheet(isPresented: $showingImageViewer) {
                if let meal = selectedMealForImage {
                    FoodImageViewer(meal: meal)
                }
            }
            .sheet(isPresented: $showingMealDetail) {
                if let meal = selectedMealForDetail {
                    MealDetailView(meal: meal)
                }
            }
            .onAppear {
            nutritionManager.loadTodaysData()
            // Load meals for today when view appears
            loadMealsForDate(selectedDate)
        }
    }
    
    // MARK: - Computed Properties
    
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
    
    private var overviewTab: some View {
        ScrollView(.vertical, showsIndicators: false) {
            LazyVStack(spacing: 16) {
                // Today's summary card
                todaysSummaryCard
                    .cardStyle()
                
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
        .scrollContentBackground(.hidden)
        .background(Color(.systemGroupedBackground))
        .coordinateSpace(name: "NutritionOverview")
    }
    
    private var mealsListTab: some View {
        VStack(spacing: 0) {
            // Date picker header
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
            
            Divider()
            
            // Meals list
            List {
                ForEach(filteredMealsForSelectedDate, id: \.id) { meal in
                    mealRow(meal)
                        .id("meal-\(meal.id)")
                        .onTapGesture {
                            selectedMealForDetail = meal
                            showingMealDetail = true
                        }
                }
                
                if filteredMealsForSelectedDate.isEmpty {
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
                    .listRowBackground(Color.clear)
                    .listRowSeparator(.hidden)
                }
            }
            .listStyle(.insetGrouped)
            .id("NutritionMealsList")
            .coordinateSpace(name: "NutritionMeals")
        }
    }
    
    private var todaysSummaryCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Card Header
            HStack {
                Image(systemName: "calendar.circle.fill")
                    .foregroundColor(.orange)
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
                        .font(.title2)
                        .fontWeight(.semibold)
                        .foregroundColor(.orange)
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
    
    private var nutritionGoalsCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Card Header
            HStack {
                Image(systemName: "target")
                    .foregroundColor(.green)
                    .font(.title2)
            Text("Daily Goals Progress")
                    .font(.title3)
                    .fontWeight(.semibold)
                Spacer()
            }
            
            VStack(spacing: 12) {
                // Calories progress
                nutritionProgressRow(
                    title: "Calories",
                    current: nutritionManager.todaysCalories,
                    goal: 2000,
                    unit: "cal",
                    color: .orange
                )
                
                // Protein progress
                nutritionProgressRow(
                    title: "Protein",
                    current: nutritionManager.todaysProtein,
                    goal: 150,
                    unit: "g",
                    color: .red
                )
                
                // Carbs progress
                nutritionProgressRow(
                    title: "Carbs",
                    current: nutritionManager.todaysCarbs,
                    goal: 250,
                    unit: "g",
                    color: .blue
                )
                
                // Fat progress
                nutritionProgressRow(
                    title: "Fat",
                    current: nutritionManager.todaysFat,
                    goal: 65,
                    unit: "g",
                    color: .yellow
                )
                
                // Fiber progress
                nutritionProgressRow(
                    title: "Fiber",
                    current: nutritionManager.todaysFiber,
                    goal: 25,
                    unit: "g",
                    color: .green
                )
            }
        }
        .padding()
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
    
    private var recentMealsPreview: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Card Header
            HStack {
                Image(systemName: "fork.knife.circle.fill")
                    .foregroundColor(.purple)
                    .font(.title2)
                Text("Recent Meals")
                    .font(.title3)
                    .fontWeight(.semibold)
                Spacer()
                Button("See All") {
                    selectedTab = 1
                    selectedDate = Date()
                }
                .font(.subheadline)
                .foregroundColor(.blue)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Color.blue.opacity(0.1))
                .cornerRadius(8)
            }
            
            if nutritionManager.nutritionData.isEmpty {
                Text("No meals logged yet")
                        .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding()
            } else {
                ForEach(nutritionManager.nutritionData.prefix(3), id: \.id) { meal in
                    mealRow(meal)
                        .onTapGesture {
                            selectedMealForDetail = meal
                            showingMealDetail = true
                        }
                }
            }
        }
        .padding()
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
                    selectedMealForImage = meal
                    showingImageViewer = true
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

@available(iOS 16.0, *)
struct NutritionView_Previews: PreviewProvider {
    static var previews: some View {
        NutritionView()
    }
}
