import Foundation

// MARK: - Date Extension for UTC handling
extension Date {
    func startOfDayUTC() -> Date {
        Calendar.current.startOfDay(for: self)
    }
}

// MARK: - Enums
enum NutritionDataSource: String, CaseIterable, Codable {
    case photoAnalysis = "photo_analysis"
    case manualEntry = "manual_entry"
    case barcodeScanning = "barcode_scan"
    case recipeImport = "recipe_import"
    case apiImport = "api_import"
    
    var displayName: String {
        switch self {
        case .photoAnalysis: return "Photo Analysis"
        case .manualEntry: return "Manual Entry"
        case .barcodeScanning: return "Barcode Scan"
        case .recipeImport: return "Recipe Import"
        case .apiImport: return "API Import"
        }
    }
}

enum MealType: String, CaseIterable, Codable {
    case breakfast = "breakfast"
    case lunch = "lunch"
    case dinner = "dinner"
    case snack = "snack"
    case other = "other"
    
    var displayName: String {
        switch self {
        case .breakfast: return "Breakfast"
        case .lunch: return "Lunch"
        case .dinner: return "Dinner"
        case .snack: return "Snack"
        case .other: return "Other"
        }
    }
    
    var emoji: String {
        switch self {
        case .breakfast: return "🍳"
        case .lunch: return "🥙"
        case .dinner: return "🍽️"
        case .snack: return "🍎"
        case .other: return "🍴"
        }
    }
}

enum DishType: String, CaseIterable, Codable {
    case vegetarian = "vegetarian"
    case vegan = "vegan"
    case chicken = "chicken"
    case beef = "beef"
    case fish = "fish"
    case shellfish = "shellfish"
    case pork = "pork"
    case mixed = "mixed"
    case other = "other"
    
    var displayName: String {
        switch self {
        case .vegetarian: return "Vegetarian"
        case .vegan: return "Vegan"
        case .chicken: return "Chicken"
        case .beef: return "Beef"
        case .fish: return "Fish"
        case .shellfish: return "Shellfish"
        case .pork: return "Pork"
        case .mixed: return "Mixed"
        case .other: return "Other"
        }
    }
    
    var emoji: String {
        switch self {
        case .vegetarian: return "🥬"
        case .vegan: return "🌱"
        case .chicken: return "🐔"
        case .beef: return "🥩"
        case .fish: return "🐟"
        case .shellfish: return "🦐"
        case .pork: return "🐷"
        case .mixed: return "🍽️"
        case .other: return "🍴"
        }
    }
}

enum NutritionTimeGranularity: String, CaseIterable, Codable {
    case daily = "daily"
    case weekly = "weekly"
    case monthly = "monthly"
    
    var displayName: String {
        switch self {
        case .daily: return "Daily"
        case .weekly: return "Weekly"
        case .monthly: return "Monthly"
        }
    }
}

// MARK: - Data Models
struct NutritionDataCreate: Codable {
    let foodItemName: String
    let dishName: String?
    let dishType: DishType?
    let mealType: MealType
    let portionSize: Double
    let portionUnit: String
    let servingSize: String?
    let calories: Double
    let proteinG: Double?
    let fatG: Double?
    let carbsG: Double?
    let fiberG: Double?
    let sugarG: Double?
    let sodiumMg: Double?
    
    // Vitamins
    let vitaminA: Double?
    let vitaminC: Double?
    let vitaminD: Double?
    let vitaminE: Double?
    let vitaminK: Double?
    let thiamin: Double?
    let riboflavin: Double?
    let niacin: Double?
    let vitaminB6: Double?
    let folate: Double?
    let vitaminB12: Double?
    
    // Minerals
    let calcium: Double?
    let iron: Double?
    let magnesium: Double?
    let phosphorus: Double?
    let potassium: Double?
    let zinc: Double?
    let copper: Double?
    let manganese: Double?
    let selenium: Double?
    
    let mealDate: String
    let mealTime: String
    let dataSource: NutritionDataSource
    let confidenceScore: Double?
    let imageUrl: String?
    let notes: String?
    
    enum CodingKeys: String, CodingKey {
        case foodItemName = "food_item_name"
        case dishName = "dish_name"
        case dishType = "dish_type"
        case mealType = "meal_type"
        case portionSize = "portion_size"
        case portionUnit = "portion_unit"
        case servingSize = "serving_size"
        case calories, proteinG = "protein_g", fatG = "fat_g", carbsG = "carbs_g"
        case fiberG = "fiber_g", sugarG = "sugar_g", sodiumMg = "sodium_mg"
        
        // Vitamins
        case vitaminA = "vitamin_a_mcg", vitaminC = "vitamin_c_mg", vitaminD = "vitamin_d_mcg"
        case vitaminE = "vitamin_e_mg", vitaminK = "vitamin_k_mcg"
        case thiamin = "vitamin_b1_mg", riboflavin = "vitamin_b2_mg", niacin = "vitamin_b3_mg"
        case vitaminB6 = "vitamin_b6_mg", folate = "folate_mcg", vitaminB12 = "vitamin_b12_mcg"
        
        // Minerals
        case calcium = "calcium_mg", iron = "iron_mg", magnesium = "magnesium_mg"
        case phosphorus = "phosphorus_mg", potassium = "potassium_mg", zinc = "zinc_mg"
        case copper = "copper_mg", manganese = "manganese_mg", selenium = "selenium_mcg"
        
        case mealDate = "meal_date", mealTime = "meal_time"
        case dataSource = "data_source", confidenceScore = "confidence_score"
        case imageUrl = "image_url", notes
    }
}

struct NutritionDataResponse: Codable, Identifiable {
    let id: Int
    let userId: Int
    let foodItemName: String
    let dishName: String?
    let dishType: DishType?
    let mealType: MealType
    let portionSize: Double
    let portionUnit: String
    let servingSize: String?
    let calories: Double
    let proteinG: Double
    let fatG: Double
    let carbsG: Double
    let fiberG: Double
    let sugarG: Double
    let sodiumMg: Double
    
    // Vitamins
    let vitaminA: Double?
    let vitaminC: Double?
    let vitaminD: Double?
    let vitaminE: Double?
    let vitaminK: Double?
    let thiamin: Double?
    let riboflavin: Double?
    let niacin: Double?
    let vitaminB6: Double?
    let folate: Double?
    let vitaminB12: Double?
    
    // Minerals
    let calcium: Double?
    let iron: Double?
    let magnesium: Double?
    let phosphorus: Double?
    let potassium: Double?
    let zinc: Double?
    let copper: Double?
    let manganese: Double?
    let selenium: Double?
    
    let mealDate: String
    let mealTime: String
    let dataSource: NutritionDataSource
    let confidenceScore: Double?
    let imageUrl: String?
    let notes: String?
    let aggregationStatus: String
    let aggregatedAt: String?
    let createdAt: String
    let updatedAt: String
    
    enum CodingKeys: String, CodingKey {
        case id, userId = "user_id", foodItemName = "food_item_name"
        case dishName = "dish_name", dishType = "dish_type"
        case mealType = "meal_type", portionSize = "portion_size", portionUnit = "portion_unit"
        case servingSize = "serving_size"
        case calories, proteinG = "protein_g", fatG = "fat_g", carbsG = "carbs_g"
        case fiberG = "fiber_g", sugarG = "sugar_g", sodiumMg = "sodium_mg"
        
        // Vitamins
        case vitaminA = "vitamin_a_mcg", vitaminC = "vitamin_c_mg", vitaminD = "vitamin_d_mcg"
        case vitaminE = "vitamin_e_mg", vitaminK = "vitamin_k_mcg"
        case thiamin = "vitamin_b1_mg", riboflavin = "vitamin_b2_mg", niacin = "vitamin_b3_mg"
        case vitaminB6 = "vitamin_b6_mg", folate = "folate_mcg", vitaminB12 = "vitamin_b12_mcg"
        
        // Minerals
        case calcium = "calcium_mg", iron = "iron_mg", magnesium = "magnesium_mg"
        case phosphorus = "phosphorus_mg", potassium = "potassium_mg", zinc = "zinc_mg"
        case copper = "copper_mg", manganese = "manganese_mg", selenium = "selenium_mcg"
        
        case mealDate = "meal_date", mealTime = "meal_time"
        case dataSource = "data_source", confidenceScore = "confidence_score"
        case imageUrl = "image_url", notes, aggregationStatus = "aggregation_status"
        case aggregatedAt = "aggregated_at", createdAt = "created_at", updatedAt = "updated_at"
    }
    
    var mealDateTime: Date? {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return formatter.date(from: "\(mealDate) \(mealTime)")
    }
    
    var mealDateOnly: Date? {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: mealDate)
    }
    
    var displayName: String {
        return dishName ?? foodItemName
    }
}

struct NutritionChartDataPoint: Codable, Identifiable {
    let id = UUID()
    let date: String
    let calories: Double
    let proteinG: Double
    let fatG: Double
    let carbsG: Double
    let fiberG: Double
    let sugarG: Double
    let sodiumMg: Double
    let mealCount: Int
    
    // Vitamins
    let vitaminAMcg: Double
    let vitaminCMg: Double
    let vitaminDMcg: Double
    let vitaminEMg: Double
    let vitaminKMcg: Double
    let vitaminB1Mg: Double
    let vitaminB2Mg: Double
    let vitaminB3Mg: Double
    let vitaminB6Mg: Double
    let vitaminB12Mcg: Double
    let folateMcg: Double
    
    // Minerals
    let calciumMg: Double
    let ironMg: Double
    let magnesiumMg: Double
    let phosphorusMg: Double
    let potassiumMg: Double
    let zincMg: Double
    let copperMg: Double
    let manganeseMg: Double
    let seleniumMcg: Double
    
    enum CodingKeys: String, CodingKey {
        case date, calories, proteinG = "protein_g", fatG = "fat_g", carbsG = "carbs_g"
        case fiberG = "fiber_g", sugarG = "sugar_g", sodiumMg = "sodium_mg", mealCount = "meal_count"
        
        // Vitamins
        case vitaminAMcg = "vitamin_a_mcg", vitaminCMg = "vitamin_c_mg", vitaminDMcg = "vitamin_d_mcg"
        case vitaminEMg = "vitamin_e_mg", vitaminKMcg = "vitamin_k_mcg"
        case vitaminB1Mg = "vitamin_b1_mg", vitaminB2Mg = "vitamin_b2_mg", vitaminB3Mg = "vitamin_b3_mg"
        case vitaminB6Mg = "vitamin_b6_mg", vitaminB12Mcg = "vitamin_b12_mcg", folateMcg = "folate_mcg"
        
        // Minerals
        case calciumMg = "calcium_mg", ironMg = "iron_mg", magnesiumMg = "magnesium_mg"
        case phosphorusMg = "phosphorus_mg", potassiumMg = "potassium_mg", zincMg = "zinc_mg"
        case copperMg = "copper_mg", manganeseMg = "manganese_mg", seleniumMcg = "selenium_mcg"
    }

    var parsedDate: Date {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        let originalDate = formatter.date(from: date) ?? Date()
        return originalDate.startOfDayUTC()
    }
}

struct NutritionChartData: Codable {
    let dataPoints: [NutritionChartDataPoint]
    let granularity: NutritionTimeGranularity
    let startDate: String
    let endDate: String
    let totalDays: Int
    
    // Macronutrients
    let avgDailyCalories: Double
    let avgDailyProteinG: Double
    let avgDailyFatG: Double
    let avgDailyCarbsG: Double
    let avgDailyFiberG: Double
    let avgDailySugarG: Double
    let avgDailySodiumMg: Double
    
    // Vitamins
    let avgDailyVitaminAMcg: Double
    let avgDailyVitaminCMg: Double
    let avgDailyVitaminDMcg: Double
    let avgDailyVitaminEMg: Double
    let avgDailyVitaminKMcg: Double
    let avgDailyVitaminB1Mg: Double
    let avgDailyVitaminB2Mg: Double
    let avgDailyVitaminB3Mg: Double
    let avgDailyVitaminB6Mg: Double
    let avgDailyVitaminB12Mcg: Double
    let avgDailyFolateMcg: Double
    
    // Minerals
    let avgDailyCalciumMg: Double
    let avgDailyIronMg: Double
    let avgDailyMagnesiumMg: Double
    let avgDailyPhosphorusMg: Double
    let avgDailyPotassiumMg: Double
    let avgDailyZincMg: Double
    let avgDailyCopperMg: Double
    let avgDailyManganeseMg: Double
    let avgDailySeleniumMcg: Double
    
    let totalMeals: Int
    
    enum CodingKeys: String, CodingKey {
        case dataPoints = "data_points", granularity, startDate = "start_date", endDate = "end_date"
        case totalDays = "total_days", totalMeals = "total_meals"
        
        // Macronutrients
        case avgDailyCalories = "avg_daily_calories"
        case avgDailyProteinG = "avg_daily_protein_g", avgDailyFatG = "avg_daily_fat_g"
        case avgDailyCarbsG = "avg_daily_carbs_g", avgDailyFiberG = "avg_daily_fiber_g"
        case avgDailySugarG = "avg_daily_sugar_g", avgDailySodiumMg = "avg_daily_sodium_mg"
        
        // Vitamins
        case avgDailyVitaminAMcg = "avg_daily_vitamin_a_mcg"
        case avgDailyVitaminCMg = "avg_daily_vitamin_c_mg"
        case avgDailyVitaminDMcg = "avg_daily_vitamin_d_mcg"
        case avgDailyVitaminEMg = "avg_daily_vitamin_e_mg"
        case avgDailyVitaminKMcg = "avg_daily_vitamin_k_mcg"
        case avgDailyVitaminB1Mg = "avg_daily_vitamin_b1_mg"
        case avgDailyVitaminB2Mg = "avg_daily_vitamin_b2_mg"
        case avgDailyVitaminB3Mg = "avg_daily_vitamin_b3_mg"
        case avgDailyVitaminB6Mg = "avg_daily_vitamin_b6_mg"
        case avgDailyVitaminB12Mcg = "avg_daily_vitamin_b12_mcg"
        case avgDailyFolateMcg = "avg_daily_folate_mcg"
        
        // Minerals
        case avgDailyCalciumMg = "avg_daily_calcium_mg"
        case avgDailyIronMg = "avg_daily_iron_mg"
        case avgDailyMagnesiumMg = "avg_daily_magnesium_mg"
        case avgDailyPhosphorusMg = "avg_daily_phosphorus_mg"
        case avgDailyPotassiumMg = "avg_daily_potassium_mg"
        case avgDailyZincMg = "avg_daily_zinc_mg"
        case avgDailyCopperMg = "avg_daily_copper_mg"
        case avgDailyManganeseMg = "avg_daily_manganese_mg"
        case avgDailySeleniumMcg = "avg_daily_selenium_mcg"
    }
}

// MARK: - Nutrition Analysis Response
struct NutritionAnalysisResponse: Codable {
    let success: Bool
    let message: String?
    let nutritionData: NutritionDataExtracted?
    let confidenceScore: Double?
    let imageUrl: String?
    
    enum CodingKeys: String, CodingKey {
        case success, message
        case nutritionData = "nutrition_data"
        case confidenceScore = "confidence_score"
        case imageUrl = "image_url"
    }
}

struct NutritionDataExtracted: Codable {
    let dishName: String?
    let dishType: String?
    let servingSize: String?
    let calories: Double?
    let proteinG: Double?
    let fatG: Double?
    let carbsG: Double?
    let fiberG: Double?
    let sugarG: Double?
    let sodiumMg: Double?
    
    // Vitamins
    let vitaminA: Double?
    let vitaminC: Double?
    let vitaminD: Double?
    let vitaminE: Double?
    let vitaminK: Double?
    let thiamin: Double?
    let riboflavin: Double?
    let niacin: Double?
    let vitaminB6: Double?
    let folate: Double?
    let vitaminB12: Double?
    
    // Minerals
    let calcium: Double?
    let iron: Double?
    let magnesium: Double?
    let phosphorus: Double?
    let potassium: Double?
    let zinc: Double?
    let copper: Double?
    let manganese: Double?
    let selenium: Double?
    
    enum CodingKeys: String, CodingKey {
        case dishName = "dish_name"
        case dishType = "dish_type"
        case servingSize = "serving_size"
        case calories, proteinG = "protein_g", fatG = "fat_g", carbsG = "carbs_g"
        case fiberG = "fiber_g", sugarG = "sugar_g", sodiumMg = "sodium_mg"
        
        // Vitamins
        case vitaminA = "vitamin_a_mcg", vitaminC = "vitamin_c_mg", vitaminD = "vitamin_d_mcg"
        case vitaminE = "vitamin_e_mg", vitaminK = "vitamin_k_mcg"
        case thiamin = "vitamin_b1_mg", riboflavin = "vitamin_b2_mg", niacin = "vitamin_b3_mg"
        case vitaminB6 = "vitamin_b6_mg", folate = "folate_mcg", vitaminB12 = "vitamin_b12_mcg"
        
        // Minerals
        case calcium = "calcium_mg", iron = "iron_mg", magnesium = "magnesium_mg"
        case phosphorus = "phosphorus_mg", potassium = "potassium_mg", zinc = "zinc_mg"
        case copper = "copper_mg", manganese = "manganese_mg", selenium = "selenium_mcg"
    }
}

// MARK: - Flattened Data Structure for Grouped Bar Charts
struct FlattenedNutritionDataPoint: Identifiable {
    let id = UUID()
    let parsedDate: Date
    let metricName: String
    let value: Double
    let metricType: NutritionMetricType
    let axisType: NutritionAxisType
}

enum NutritionMetricType {
    case nutrition
    case vitamin
    case mineral
}

enum NutritionAxisType {
    case calories  // Left Y-axis for calories (kcal)
    case grams     // Right Y-axis for grams (g)
}

// MARK: - Extension to convert daily data to flattened structure
extension NutritionChartDataPoint {
    func toFlattenedNutritionData(enabledMetrics: Set<String>) -> [FlattenedNutritionDataPoint] {
        var flattenedData: [FlattenedNutritionDataPoint] = []
        
        // Nutrition metrics - using actual values with dual Y-axes
        if enabledMetrics.contains("Calories") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Calories",
                value: self.calories, // Actual calories (kcal)
                metricType: .nutrition,
                axisType: .calories // Left Y-axis for calories
            ))
        }
        if enabledMetrics.contains("Protein") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Protein",
                value: self.proteinG, // Actual protein (g)
                metricType: .nutrition,
                axisType: .grams // Right Y-axis for grams
            ))
        }
        if enabledMetrics.contains("Carbs") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Carbs",
                value: self.carbsG, // Actual carbs (g)
                metricType: .nutrition,
                axisType: .grams // Right Y-axis for grams
            ))
        }
        if enabledMetrics.contains("Fat") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Fat",
                value: self.fatG, // Actual fat (g)
                metricType: .nutrition,
                axisType: .grams // Right Y-axis for grams
            ))
        }
        if enabledMetrics.contains("Fiber") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Fiber",
                value: self.fiberG, // Actual fiber (g)
                metricType: .nutrition,
                axisType: .grams // Right Y-axis for grams
            ))
        }
        
        return flattenedData
    }
    
    func toFlattenedVitaminData(enabledMetrics: Set<String>) -> [FlattenedNutritionDataPoint] {
        var flattenedData: [FlattenedNutritionDataPoint] = []
        
        if enabledMetrics.contains("Vit A") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Vit A",
                value: self.vitaminAMcg,
                metricType: .vitamin,
                axisType: .grams
            ))
        }
        if enabledMetrics.contains("Vit C") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Vit C",
                value: self.vitaminCMg,
                metricType: .vitamin,
                axisType: .grams
            ))
        }
        if enabledMetrics.contains("Vit D") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Vit D",
                value: self.vitaminDMcg,
                metricType: .vitamin,
                axisType: .grams
            ))
        }
        if enabledMetrics.contains("Vit E") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Vit E",
                value: self.vitaminEMg,
                metricType: .vitamin,
                axisType: .grams
            ))
        }
        if enabledMetrics.contains("Vit K") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Vit K",
                value: self.vitaminKMcg,
                metricType: .vitamin,
                axisType: .grams
            ))
        }
        if enabledMetrics.contains("Vit B1") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Vit B1",
                value: self.vitaminB1Mg,
                metricType: .vitamin,
                axisType: .grams
            ))
        }
        if enabledMetrics.contains("Vit B2") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Vit B2",
                value: self.vitaminB2Mg,
                metricType: .vitamin,
                axisType: .grams
            ))
        }
        if enabledMetrics.contains("Vit B3") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Vit B3",
                value: self.vitaminB3Mg,
                metricType: .vitamin,
                axisType: .grams
            ))
        }
        if enabledMetrics.contains("Vit B6") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Vit B6",
                value: self.vitaminB6Mg,
                metricType: .vitamin,
                axisType: .grams
            ))
        }
        if enabledMetrics.contains("Vit B12") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Vit B12",
                value: self.vitaminB12Mcg,
                metricType: .vitamin,
                axisType: .grams
            ))
        }
        if enabledMetrics.contains("Folate") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Folate",
                value: self.folateMcg,
                metricType: .vitamin,
                axisType: .grams
            ))
        }
        
        return flattenedData
    }
    
    func toFlattenedMineralData(enabledMetrics: Set<String>) -> [FlattenedNutritionDataPoint] {
        var flattenedData: [FlattenedNutritionDataPoint] = []
        
        if enabledMetrics.contains("Calcium") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Calcium",
                value: self.calciumMg,
                metricType: .mineral,
                axisType: .grams
            ))
        }
        if enabledMetrics.contains("Iron") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Iron",
                value: self.ironMg,
                metricType: .mineral,
                axisType: .grams
            ))
        }
        if enabledMetrics.contains("Magnesium") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Magnesium",
                value: self.magnesiumMg,
                metricType: .mineral,
                axisType: .grams
            ))
        }
        if enabledMetrics.contains("Phosphorus") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Phosphorus",
                value: self.phosphorusMg,
                metricType: .mineral,
                axisType: .grams
            ))
        }
        if enabledMetrics.contains("Potassium") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Potassium",
                value: self.potassiumMg,
                metricType: .mineral,
                axisType: .grams
            ))
        }
        if enabledMetrics.contains("Zinc") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Zinc",
                value: self.zincMg,
                metricType: .mineral,
                axisType: .grams
            ))
        }
        if enabledMetrics.contains("Copper") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Copper",
                value: self.copperMg,
                metricType: .mineral,
                axisType: .grams
            ))
        }
        if enabledMetrics.contains("Manganese") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Manganese",
                value: self.manganeseMg,
                metricType: .mineral,
                axisType: .grams
            ))
        }
        if enabledMetrics.contains("Selenium") {
            flattenedData.append(FlattenedNutritionDataPoint(
                parsedDate: self.parsedDate,
                metricName: "Selenium",
                value: self.seleniumMcg,
                metricType: .mineral,
                axisType: .grams
            ))
        }
        
        return flattenedData
    }
}
