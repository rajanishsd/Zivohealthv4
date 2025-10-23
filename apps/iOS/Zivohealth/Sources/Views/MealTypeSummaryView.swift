import SwiftUI

/// Level 2 View: Shows all meals within a meal type with aggregated summary
struct MealTypeSummaryView: View {
    let group: MealTypeGroup
    @State private var showingMealDetail = false
    @State private var selectedMeal: NutritionDataResponse?
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        GeometryReader { geometry in
            ScrollView {
                VStack(spacing: 0) {
                    // Header
                    headerView(topInset: geometry.safeAreaInsets.top)
                        .padding(.top, 20)
                    
                    // Content
                    VStack(spacing: 16) {
                        // Aggregated summary card
                        aggregatedSummaryCard
                            .padding(.horizontal)
                            .padding(.top, 16)
                        
                        // Individual meals section
                        if !group.meals.isEmpty {
                            VStack(alignment: .leading, spacing: 12) {
                                Text("Individual Meals (\(group.mealCount))")
                                    .font(.headline)
                                    .fontWeight(.bold)
                                    .padding(.horizontal)
                                
                                ForEach(group.meals, id: \.id) { meal in
                                    individualMealCard(meal)
                                        .padding(.horizontal)
                                        .onTapGesture {
                                            selectedMeal = meal
                                            showingMealDetail = true
                                        }
                                }
                            }
                            .padding(.top, 8)
                        }
                        
                        Spacer(minLength: 50)
                    }
                }
            }
            .background(Color(.systemGroupedBackground))
            .ignoresSafeArea(.container, edges: .top)
        }
        .navigationBarHidden(true)
        .sheet(isPresented: $showingMealDetail) {
            if let meal = selectedMeal {
                MealDetailView(meal: meal)
            }
        }
    }
    
    // MARK: - Header
    private func headerView(topInset: CGFloat) -> some View {
        // Card content with back button
        ZStack(alignment: .topLeading) {
            LinearGradient(
                gradient: Gradient(colors: [
                    Color.zivoRed,
                    Color.zivoRed.opacity(0.7)
                ]),
                startPoint: .leading,
                endPoint: .trailing
            )
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            
            ZStack {
                // Centered title and subtitle
                VStack(spacing: 2) {
                    HStack(spacing: 6) {
                        Text(group.mealType.emoji)
                            .font(.title3)
                        Text(group.mealType.displayName)
                            .font(.title3)
                            .fontWeight(.bold)
                            .foregroundColor(.white)
                    }
                    
                    Text("\(group.mealCount) meal\(group.mealCount > 1 ? "s" : "") • \(Int(group.totalCalories)) calories")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.9))
                }
                .offset(y: 8)
                
                // Back button
                HStack {
                    Button(action: {
                        dismiss()
                    }) {
                        Image(systemName: "arrow.backward")
                            .font(.system(size: 18, weight: .semibold))
                            .foregroundColor(.white)
                    }
                    .padding(.leading, 16)
                    
                    Spacer()
                }
                .offset(y: 5)
            }
            .padding(.vertical, 12)
        }
        .frame(height: 77)
        .cornerRadius(16)
        .padding(.horizontal, 16)
    }
    
    // MARK: - Aggregated Summary Card
    private var aggregatedSummaryCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Title
            HStack {
                Image(systemName: "chart.bar.fill")
                    .foregroundColor(.green)
                    .font(.title3)
                Text("Total Nutrition Summary")
                    .font(.headline)
                    .fontWeight(.bold)
            }
            
            Divider()
            
            // Macronutrients
            VStack(spacing: 12) {
                summaryRow("Calories", value: String(format: "%.0f", group.totalCalories), unit: "kcal", color: .orange, icon: "flame.fill")
                summaryRow("Protein", value: String(format: "%.1f", group.totalProtein), unit: "g", color: .red, icon: "p.circle.fill")
                summaryRow("Carbs", value: String(format: "%.1f", group.totalCarbs), unit: "g", color: .blue, icon: "c.circle.fill")
                summaryRow("Fat", value: String(format: "%.1f", group.totalFat), unit: "g", color: .yellow, icon: "f.circle.fill")
                summaryRow("Fiber", value: String(format: "%.1f", group.totalFiber), unit: "g", color: .green, icon: "leaf.fill")
                summaryRow("Sugar", value: String(format: "%.1f", group.totalSugar), unit: "g", color: .pink, icon: "cube.fill")
                summaryRow("Sodium", value: String(format: "%.0f", group.totalSodium), unit: "mg", color: .purple, icon: "drop.fill")
            }
            
            // Vitamins & Minerals (if available)
            if hasVitaminsOrMinerals {
                Divider()
                
                Text("Vitamins")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(.secondary)
                
                LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 2), spacing: 8) {
                    if group.totalVitaminA > 0 {
                        compactNutrientCard("Vitamin A", value: group.totalVitaminA, unit: "mcg", color: .orange)
                    }
                    if group.totalVitaminC > 0 {
                        compactNutrientCard("Vitamin C", value: group.totalVitaminC, unit: "mg", color: .yellow)
                    }
                    if group.totalVitaminD > 0 {
                        compactNutrientCard("Vitamin D", value: group.totalVitaminD, unit: "mcg", color: .blue)
                    }
                    if group.totalVitaminE > 0 {
                        compactNutrientCard("Vitamin E", value: group.totalVitaminE, unit: "mg", color: .green)
                    }
                    if group.totalVitaminK > 0 {
                        compactNutrientCard("Vitamin K", value: group.totalVitaminK, unit: "mcg", color: .purple)
                    }
                    if group.totalThiamin > 0 {
                        compactNutrientCard("B1 (Thiamin)", value: group.totalThiamin, unit: "mg", color: .red)
                    }
                    if group.totalRiboflavin > 0 {
                        compactNutrientCard("B2 (Riboflavin)", value: group.totalRiboflavin, unit: "mg", color: .pink)
                    }
                    if group.totalNiacin > 0 {
                        compactNutrientCard("B3 (Niacin)", value: group.totalNiacin, unit: "mg", color: .indigo)
                    }
                    if group.totalVitaminB6 > 0 {
                        compactNutrientCard("Vitamin B6", value: group.totalVitaminB6, unit: "mg", color: .teal)
                    }
                    if group.totalFolate > 0 {
                        compactNutrientCard("Folate", value: group.totalFolate, unit: "mcg", color: .mint)
                    }
                    if group.totalVitaminB12 > 0 {
                        compactNutrientCard("Vitamin B12", value: group.totalVitaminB12, unit: "mcg", color: .cyan)
                    }
                }
                
                Text("Minerals")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(.secondary)
                    .padding(.top, 8)
                
                LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 2), spacing: 8) {
                    if group.totalCalcium > 0 {
                        compactNutrientCard("Calcium", value: group.totalCalcium, unit: "mg", color: .blue)
                    }
                    if group.totalIron > 0 {
                        compactNutrientCard("Iron", value: group.totalIron, unit: "mg", color: .red)
                    }
                    if group.totalMagnesium > 0 {
                        compactNutrientCard("Magnesium", value: group.totalMagnesium, unit: "mg", color: .green)
                    }
                    if group.totalPhosphorus > 0 {
                        compactNutrientCard("Phosphorus", value: group.totalPhosphorus, unit: "mg", color: .orange)
                    }
                    if group.totalPotassium > 0 {
                        compactNutrientCard("Potassium", value: group.totalPotassium, unit: "mg", color: .purple)
                    }
                    if group.totalZinc > 0 {
                        compactNutrientCard("Zinc", value: group.totalZinc, unit: "mg", color: .yellow)
                    }
                    if group.totalCopper > 0 {
                        compactNutrientCard("Copper", value: group.totalCopper, unit: "mg", color: .pink)
                    }
                    if group.totalManganese > 0 {
                        compactNutrientCard("Manganese", value: group.totalManganese, unit: "mg", color: .brown)
                    }
                    if group.totalSelenium > 0 {
                        compactNutrientCard("Selenium", value: group.totalSelenium, unit: "mcg", color: .gray)
                    }
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
    }
    
    // MARK: - Individual Meal Card
    private func individualMealCard(_ meal: NutritionDataResponse) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    // Time
                    if let mealTime = meal.mealDateTime {
                        Text(mealTime, style: .time)
                            .font(.caption)
                            .foregroundColor(.secondary)
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
            HStack(spacing: 8) {
                nutritionBadge("P", value: Int(meal.proteinG), unit: "g", color: .red)
                nutritionBadge("C", value: Int(meal.carbsG), unit: "g", color: .blue)
                nutritionBadge("F", value: Int(meal.fatG), unit: "g", color: .yellow)
                
                if meal.fiberG > 0 {
                    nutritionBadge("Fiber", value: Int(meal.fiberG), unit: "g", color: .green)
                }
                
                Spacer()
                
                // Image indicator
                if meal.dataSource == .photoAnalysis && meal.imageUrl != nil {
                    Image(systemName: "photo.fill")
                        .font(.caption)
                        .foregroundColor(.blue)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
    }
    
    // MARK: - Helper Views
    private func summaryRow(_ label: String, value: String, unit: String, color: Color, icon: String) -> some View {
        HStack {
            Image(systemName: icon)
                .foregroundColor(color)
                .font(.body)
                .frame(width: 24)
            
            Text(label)
                .font(.subheadline)
                .foregroundColor(.primary)
            
            Spacer()
            
            Text(value)
                .font(.subheadline)
                .fontWeight(.bold)
                .foregroundColor(color)
            Text(unit)
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }
    
    private func compactNutrientCard(_ name: String, value: Double, unit: String, color: Color) -> some View {
        HStack(spacing: 4) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            
            Text(name)
                .font(.caption2)
                .fontWeight(.medium)
            
            Spacer()
            
            Text(String(format: "%.1f", value))
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundColor(color)
            Text(unit)
                .font(.caption2)
                .foregroundColor(.secondary)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 6)
        .background(color.opacity(0.1))
        .cornerRadius(6)
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
    
    private var hasVitaminsOrMinerals: Bool {
        // Check all vitamins
        let hasVitamins = group.totalVitaminA > 0 || group.totalVitaminC > 0 || group.totalVitaminD > 0 ||
                         group.totalVitaminE > 0 || group.totalVitaminK > 0 || group.totalThiamin > 0 ||
                         group.totalRiboflavin > 0 || group.totalNiacin > 0 || group.totalVitaminB6 > 0 ||
                         group.totalFolate > 0 || group.totalVitaminB12 > 0
        
        // Check all minerals
        let hasMinerals = group.totalCalcium > 0 || group.totalIron > 0 || group.totalMagnesium > 0 ||
                         group.totalPhosphorus > 0 || group.totalPotassium > 0 || group.totalZinc > 0 ||
                         group.totalCopper > 0 || group.totalManganese > 0 || group.totalSelenium > 0
        
        return hasVitamins || hasMinerals
    }
}

