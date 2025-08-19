import SwiftUI
import Charts

@available(iOS 16.0, *)
struct NutritionChartsContainer: View {
    @ObservedObject var nutritionManager: NutritionManager
    
    var body: some View {
        VStack(spacing: 16) {
            TimePeriodSelector(nutritionManager: nutritionManager)
            NutritionChart(nutritionManager: nutritionManager)
                .cardStyle()
            VitaminsChart(nutritionManager: nutritionManager)
                .cardStyle()
            MineralsChart(nutritionManager: nutritionManager)
                .cardStyle()
        }
    }
}

// MARK: - Individual Chart Views
@available(iOS 16.0, *)
private struct NutritionChart: View {
    @ObservedObject var nutritionManager: NutritionManager
    
    @State private var showCalories = true
    @State private var showProtein = true
    @State private var showCarbs = true
    @State private var showFat = true
    @State private var showFiber = true
    
    var body: some View {
        // Create enabled metrics set
        let enabledMetrics = Set([
            showCalories ? "Calories" : nil,
            showProtein ? "Protein" : nil,
            showCarbs ? "Carbs" : nil,
            showFat ? "Fat" : nil,
            showFiber ? "Fiber" : nil
        ].compactMap { $0 })
        
        chartView(
            title: "Nutrition Trends (Calories ÷10)",
            systemImage: "chart.line.uptrend.xyaxis",
            chartId: "NutritionChart",
            nutritionManager: nutritionManager,
            legendContent: { nutritionLegend },
            chartContent: { dataPoint in
                // Create individual BarMarks for each enabled metric
                if enabledMetrics.contains("Calories") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.calories / 10),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(nutritionColor(for: "Calories"))
                    .position(by: .value("Nutrient", "Calories"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Protein") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.proteinG),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(nutritionColor(for: "Protein"))
                    .position(by: .value("Nutrient", "Protein"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Carbs") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.carbsG),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(nutritionColor(for: "Carbs"))
                    .position(by: .value("Nutrient", "Carbs"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Fat") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.fatG),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(nutritionColor(for: "Fat"))
                    .position(by: .value("Nutrient", "Fat"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Fiber") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.fiberG),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(nutritionColor(for: "Fiber"))
                    .position(by: .value("Nutrient", "Fiber"))
                    .cornerRadius(4)
                }
            }
        )
        .onAppear {
            // Debug print for nutrition chart data
            if let chartData = nutritionManager.chartData {
                let rawDataPoints = chartData.dataPoints
                let sortedData = rawDataPoints
                    .sorted(by: { $0.parsedDate < $1.parsedDate })
                    .reduce(into: [NutritionChartDataPoint]()) { result, dataPoint in
                        if !result.contains(where: { $0.parsedDate == dataPoint.parsedDate }) {
                            result.append(dataPoint)
                        }
                    }
                
                print("🍎 NutritionChart Debug Info:")
                print("  - Chart Data Available: \(nutritionManager.chartData != nil)")
                print("  - Raw Data Points: \(rawDataPoints.count)")
                print("  - Sorted Data Points: \(sortedData.count)")
                print("  - Show Calories: \(showCalories)")
                print("  - Show Protein: \(showProtein)")
                print("  - Show Carbs: \(showCarbs)")
                print("  - Show Fat: \(showFat)")
                print("  - Show Fiber: \(showFiber)")
                
                for (index, dataPoint) in sortedData.enumerated() {
                    print("  [\(index)] Date: \(dataPoint.parsedDate), Calories: \(dataPoint.calories), Protein: \(dataPoint.proteinG)g, Carbs: \(dataPoint.carbsG)g, Fat: \(dataPoint.fatG)g, Fiber: \(dataPoint.fiberG)g")
                }
                
                // Test flattened data
                let flattenedData = sortedData.flatMap { dataPoint in
                    dataPoint.toFlattenedNutritionData(enabledMetrics: enabledMetrics)
                }
                
                print("  - Enabled Metrics: \(enabledMetrics)")
                print("  - Flattened Data Points: \(flattenedData.count)")
                for (index, item) in flattenedData.enumerated() {
                    let displayValue = item.axisType == .calories ? item.value / 10 : item.value
                    print("  Flattened[\(index)] Date: \(item.parsedDate), Metric: \(item.metricName), Value: \(item.value) → Display: \(displayValue), AxisType: \(item.axisType)")
                }
            }
        }
    }

    private var nutritionLegend: some View {
        VStack(spacing: 8) {
            HStack {
                Text("Calories (scaled ÷10 for comparison)")
                    .font(.caption2)
                    .foregroundColor(.orange)
                    .fontWeight(.medium)
                Spacer()
                Text("Nutrients (actual grams)")
                    .font(.caption2)
                    .foregroundColor(.blue)
                    .fontWeight(.medium)
            }
            
            LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 3), spacing: 12) {
                legendItem(name: "Calories (kcal÷10)", color: .orange, isVisible: $showCalories)
                legendItem(name: "Protein (g)", color: .red, isVisible: $showProtein)
                legendItem(name: "Carbs (g)", color: .blue, isVisible: $showCarbs)
                legendItem(name: "Fat (g)", color: .yellow, isVisible: $showFat)
                legendItem(name: "Fiber (g)", color: .green, isVisible: $showFiber)
            }
        }
    }
}

@available(iOS 16.0, *)
private struct VitaminsChart: View {
    @ObservedObject var nutritionManager: NutritionManager

    @State private var showVitaminA = true
    @State private var showVitaminC = true
    @State private var showVitaminD = true
    @State private var showVitaminE = false
    @State private var showVitaminK = false
    @State private var showVitaminB1 = false
    @State private var showVitaminB2 = false
    @State private var showVitaminB3 = false
    @State private var showVitaminB6 = false
    @State private var showVitaminB12 = true
    @State private var showFolate = false

    var body: some View {
        // Create enabled metrics set
        let enabledMetrics = Set([
            showVitaminA ? "Vit A" : nil,
            showVitaminC ? "Vit C" : nil,
            showVitaminD ? "Vit D" : nil,
            showVitaminE ? "Vit E" : nil,
            showVitaminK ? "Vit K" : nil,
            showVitaminB1 ? "Vit B1" : nil,
            showVitaminB2 ? "Vit B2" : nil,
            showVitaminB3 ? "Vit B3" : nil,
            showVitaminB6 ? "Vit B6" : nil,
            showVitaminB12 ? "Vit B12" : nil,
            showFolate ? "Folate" : nil
        ].compactMap { $0 })
        
        chartView(
            title: "Vitamins Trends",
            systemImage: "atom",
            chartId: "VitaminsChart",
            nutritionManager: nutritionManager,
            legendContent: { vitaminsLegend },
            chartContent: { dataPoint in
                // Create individual BarMarks for each enabled vitamin
                if enabledMetrics.contains("Vit A") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.vitaminAMcg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(vitaminColor(for: "Vit A"))
                    .position(by: .value("Vitamin", "Vit A"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Vit C") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.vitaminCMg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(vitaminColor(for: "Vit C"))
                    .position(by: .value("Vitamin", "Vit C"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Vit D") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.vitaminDMcg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(vitaminColor(for: "Vit D"))
                    .position(by: .value("Vitamin", "Vit D"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Vit E") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.vitaminEMg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(vitaminColor(for: "Vit E"))
                    .position(by: .value("Vitamin", "Vit E"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Vit K") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.vitaminKMcg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(vitaminColor(for: "Vit K"))
                    .position(by: .value("Vitamin", "Vit K"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Vit B1") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.vitaminB1Mg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(vitaminColor(for: "Vit B1"))
                    .position(by: .value("Vitamin", "Vit B1"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Vit B2") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.vitaminB2Mg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(vitaminColor(for: "Vit B2"))
                    .position(by: .value("Vitamin", "Vit B2"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Vit B3") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.vitaminB3Mg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(vitaminColor(for: "Vit B3"))
                    .position(by: .value("Vitamin", "Vit B3"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Vit B6") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.vitaminB6Mg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(vitaminColor(for: "Vit B6"))
                    .position(by: .value("Vitamin", "Vit B6"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Vit B12") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.vitaminB12Mcg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(vitaminColor(for: "Vit B12"))
                    .position(by: .value("Vitamin", "Vit B12"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Folate") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.folateMcg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(vitaminColor(for: "Folate"))
                    .position(by: .value("Vitamin", "Folate"))
                    .cornerRadius(4)
                }
            }
        )
        .onAppear {
            // Debug print for vitamins chart data
            if let chartData = nutritionManager.chartData {
                let rawDataPoints = chartData.dataPoints
                let sortedData = rawDataPoints
                    .sorted(by: { $0.parsedDate < $1.parsedDate })
                    .reduce(into: [NutritionChartDataPoint]()) { result, dataPoint in
                        if !result.contains(where: { $0.parsedDate == dataPoint.parsedDate }) {
                            result.append(dataPoint)
                        }
                    }
                
                print("🍊 VitaminsChart Data Points (\(sortedData.count) points):")
                for (index, dataPoint) in sortedData.enumerated() {
                    print("  [\(index)] Date: \(dataPoint.parsedDate), Vitamin A: \(dataPoint.vitaminAMcg)mcg, Vitamin C: \(dataPoint.vitaminCMg)mg, Vitamin D: \(dataPoint.vitaminDMcg)mcg, Vitamin E: \(dataPoint.vitaminEMg)mg, Vitamin K: \(dataPoint.vitaminKMcg)mcg")
                }
                
                // Test flattened vitamin data
                let flattenedData = sortedData.flatMap { dataPoint in
                    dataPoint.toFlattenedVitaminData(enabledMetrics: enabledMetrics)
                }
                
                print("  - Enabled Vitamin Metrics: \(enabledMetrics)")
                print("  - Flattened Vitamin Data Points: \(flattenedData.count)")
                for (index, item) in flattenedData.enumerated() {
                    print("  VitaminFlattened[\(index)] Date: \(item.parsedDate), Metric: \(item.metricName), Value: \(item.value)")
                }
            }
        }
    }

    private var vitaminsLegend: some View {
        LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 4), spacing: 10) {
            legendItem(name: "Vit A (mcg)", color: .purple, isVisible: $showVitaminA)
            legendItem(name: "Vit C (mg)", color: .pink, isVisible: $showVitaminC)
            legendItem(name: "Vit D (mcg)", color: .teal, isVisible: $showVitaminD)
            legendItem(name: "Vit E (mg)", color: .indigo, isVisible: $showVitaminE)
            legendItem(name: "Vit K (mcg)", color: .mint, isVisible: $showVitaminK)
            legendItem(name: "Vit B1 (mg)", color: .cyan, isVisible: $showVitaminB1)
            legendItem(name: "Vit B2 (mg)", color: .orange, isVisible: $showVitaminB2)
            legendItem(name: "Vit B3 (mg)", color: .yellow, isVisible: $showVitaminB3)
            legendItem(name: "Vit B6 (mg)", color: .red, isVisible: $showVitaminB6)
            legendItem(name: "Vit B12 (mcg)", color: .blue, isVisible: $showVitaminB12)
            legendItem(name: "Folate (mcg)", color: .green, isVisible: $showFolate)
        }
    }
}

@available(iOS 16.0, *)
private struct MineralsChart: View {
    @ObservedObject var nutritionManager: NutritionManager

    @State private var showCalcium = true
    @State private var showIron = true
    @State private var showMagnesium = true
    @State private var showPhosphorus = true
    @State private var showPotassium = false
    @State private var showZinc = false
    @State private var showCopper = false
    @State private var showManganese = false
    @State private var showSelenium = false

    var body: some View {
        // Create enabled metrics set
        let enabledMetrics = Set([
            showCalcium ? "Calcium" : nil,
            showIron ? "Iron" : nil,
            showMagnesium ? "Magnesium" : nil,
            showPhosphorus ? "Phosphorus" : nil,
            showPotassium ? "Potassium" : nil,
            showZinc ? "Zinc" : nil,
            showCopper ? "Copper" : nil,
            showManganese ? "Manganese" : nil,
            showSelenium ? "Selenium" : nil
        ].compactMap { $0 })
        
        chartView(
            title: "Minerals Trends",
            systemImage: "circle.grid.3x3.fill",
            chartId: "MineralsChart",
            nutritionManager: nutritionManager,
            legendContent: { mineralsLegend },
            chartContent: { dataPoint in
                // Create individual BarMarks for each enabled mineral
                if enabledMetrics.contains("Calcium") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.calciumMg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(mineralColor(for: "Calcium"))
                    .position(by: .value("Mineral", "Calcium"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Iron") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.ironMg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(mineralColor(for: "Iron"))
                    .position(by: .value("Mineral", "Iron"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Magnesium") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.magnesiumMg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(mineralColor(for: "Magnesium"))
                    .position(by: .value("Mineral", "Magnesium"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Phosphorus") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.phosphorusMg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(mineralColor(for: "Phosphorus"))
                    .position(by: .value("Mineral", "Phosphorus"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Potassium") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.potassiumMg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(mineralColor(for: "Potassium"))
                    .position(by: .value("Mineral", "Potassium"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Zinc") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.zincMg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(mineralColor(for: "Zinc"))
                    .position(by: .value("Mineral", "Zinc"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Copper") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.copperMg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(mineralColor(for: "Copper"))
                    .position(by: .value("Mineral", "Copper"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Manganese") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.manganeseMg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(mineralColor(for: "Manganese"))
                    .position(by: .value("Mineral", "Manganese"))
                    .cornerRadius(4)
                }
                
                if enabledMetrics.contains("Selenium") {
                    BarMark(
                        x: .value("Date", dataPoint.parsedDate, unit: nutritionManager.selectedGranularity.chartUnit),
                        y: .value("Value", dataPoint.seleniumMcg),
                        width: .ratio(0.7)
                    )
                    .foregroundStyle(mineralColor(for: "Selenium"))
                    .position(by: .value("Mineral", "Selenium"))
                    .cornerRadius(4)
                }
            }
        )
        .onAppear {
            // Debug print for minerals chart data
            if let chartData = nutritionManager.chartData {
                let rawDataPoints = chartData.dataPoints
                let sortedData = rawDataPoints
                    .sorted(by: { $0.parsedDate < $1.parsedDate })
                    .reduce(into: [NutritionChartDataPoint]()) { result, dataPoint in
                        if !result.contains(where: { $0.parsedDate == dataPoint.parsedDate }) {
                            result.append(dataPoint)
                        }
                    }
                
                print("🍌 MineralsChart Data Points (\(sortedData.count) points):")
                for (index, dataPoint) in sortedData.enumerated() {
                    print("  [\(index)] Date: \(dataPoint.parsedDate), Calcium: \(dataPoint.calciumMg)mg, Iron: \(dataPoint.ironMg)mg, Magnesium: \(dataPoint.magnesiumMg)mg, Phosphorus: \(dataPoint.phosphorusMg)mg, Potassium: \(dataPoint.potassiumMg)mg, Zinc: \(dataPoint.zincMg)mg, Copper: \(dataPoint.copperMg)mg, Manganese: \(dataPoint.manganeseMg)mg, Selenium: \(dataPoint.seleniumMcg)mcg")
                }
                
                // Test flattened mineral data
                let flattenedData = sortedData.flatMap { dataPoint in
                    dataPoint.toFlattenedMineralData(enabledMetrics: enabledMetrics)
                }
                
                print("  - Enabled Mineral Metrics: \(enabledMetrics)")
                print("  - Flattened Mineral Data Points: \(flattenedData.count)")
                for (index, item) in flattenedData.enumerated() {
                    print("  MineralFlattened[\(index)] Date: \(item.parsedDate), Metric: \(item.metricName), Value: \(item.value)")
                }
            }
        }
    }
    
    private var mineralsLegend: some View {
        LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 3), spacing: 10) {
            legendItem(name: "Calcium (mg)", color: .gray, isVisible: $showCalcium)
            legendItem(name: "Iron (mg)", color: .red, isVisible: $showIron)
            legendItem(name: "Magnesium (mg)", color: .green, isVisible: $showMagnesium)
            legendItem(name: "Phosphorus (mg)", color: .blue, isVisible: $showPhosphorus)
            legendItem(name: "Potassium (mg)", color: .orange, isVisible: $showPotassium)
            legendItem(name: "Zinc (mg)", color: .purple, isVisible: $showZinc)
            legendItem(name: "Copper (mg)", color: .brown, isVisible: $showCopper)
            legendItem(name: "Manganese (mg)", color: .pink, isVisible: $showManganese)
            legendItem(name: "Selenium (mcg)", color: .teal, isVisible: $showSelenium)
        }
    }
}


// MARK: - Reusable Components
@available(iOS 16.0, *)
@ViewBuilder
private func chartView<Legend: View, Content: ChartContent>(
    title: String,
    systemImage: String,
    chartId: String,
    nutritionManager: NutritionManager,
    @ViewBuilder legendContent: () -> Legend,
    @ChartContentBuilder chartContent: @escaping (NutritionChartDataPoint) -> Content
) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
            Image(systemName: systemImage)
                .foregroundColor(systemImage == "atom" ? .purple : (systemImage == "circle.grid.3x3.fill" ? .gray : .accentColor))
                    .font(.title2)
            Text(title).font(.title3).fontWeight(.semibold)
                Spacer()
            }
            
            if let chartData = nutritionManager.chartData, !chartData.dataPoints.isEmpty {
                // Sort data chronologically and remove duplicates
                let rawDataPoints = nutritionManager.chartData?.dataPoints ?? []
                let sortedData = rawDataPoints
                    .sorted(by: { $0.parsedDate < $1.parsedDate })
                    .reduce(into: [NutritionChartDataPoint]()) { result, dataPoint in
                        // Remove duplicates by date
                        if !result.contains(where: { $0.parsedDate == dataPoint.parsedDate }) {
                            result.append(dataPoint)
                        }
                    }
                    .suffix(3) // Limit to only 3 most recent periods
                    .map { $0 }
                
                VStack(spacing: 16) {
                Chart {
                    ForEach(sortedData, id: \.parsedDate) { dataPoint in
                        chartContent(dataPoint)
                    }
                }
                    .frame(height: 240)
                    .id(chartId)
                    .chartLegend(.hidden)
                    .padding(.trailing, 24)
                    .chartXAxis {
                        // Use stride-based axis marks to prevent label repetition
                        AxisMarks(values: .stride(by: nutritionManager.selectedGranularity.stride)) { date in
                            AxisGridLine()
                            AxisValueLabel(format: nutritionManager.selectedGranularity.dateFormat, centered: true)
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .chartYAxis {
                        AxisMarks(values: .automatic(desiredCount: 5)) { value in
                            AxisGridLine()
                            AxisValueLabel {
                                if let doubleValue = value.as(Double.self) {
                                    Text("\(Int(doubleValue))")
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                    .chartForegroundStyleScale([
                        "Calories": .orange,
                        "Protein": .red,
                        "Carbs": .blue,
                        "Fat": .yellow,
                        "Fiber": .green
                    ])
                    // Let SwiftUI auto-calculate domain for consistent 3-period spacing
                
                legendContent()
            }
        } else {
            emptyStateView(title: "No \(title.components(separatedBy: " ").first ?? "Data") Data")
        }
    }
    .padding(.horizontal, 8)
    .padding(.vertical, 8)
}


private func chartXDomain(for chartData: NutritionChartData) -> ClosedRange<Date> {
    let dates = chartData.dataPoints.map { $0.parsedDate }.sorted()
    guard let minDate = dates.first, let maxDate = dates.last else {
        return Date()...Date()
    }
    
    // Optimized padding for 3-period consistency - use minimal padding to maximize bar visibility
    let timeInterval = maxDate.timeIntervalSince(minDate)
    
    if dates.count <= 1 {
        // For single point, minimal padding
        let paddingInterval = 86400 * 0.5 // 0.5 days
        return minDate.addingTimeInterval(-paddingInterval)...maxDate.addingTimeInterval(paddingInterval)
    } else {
        // For 2-3 data points, use minimal padding to maximize bar width
        let paddingInterval = max(86400 * 0.2, timeInterval * 0.1) // Very small padding
        let startDate = minDate.addingTimeInterval(-paddingInterval)
        let endDate = maxDate.addingTimeInterval(paddingInterval)
        return startDate...endDate
    }
}

private func legendItem(name: String, color: Color, isVisible: Binding<Bool>) -> some View {
    Button(action: { withAnimation { isVisible.wrappedValue.toggle() } }) {
        HStack(spacing: 6) {
            Circle()
                .fill(isVisible.wrappedValue ? color : color.opacity(0.3))
                .frame(width: 10, height: 10)
                .overlay(
                    Circle()
                        .stroke(color, lineWidth: isVisible.wrappedValue ? 0 : 1)
                )
            
            Text(name)
                .font(.caption2)
                .foregroundColor(isVisible.wrappedValue ? .primary : .secondary)
        }
    }
    .buttonStyle(.plain)
    .opacity(isVisible.wrappedValue ? 1.0 : 0.6)
}

private func emptyStateView(title: String) -> some View {
    VStack {
        Text(title)
            .font(.headline)
                    .foregroundColor(.secondary)
        Text("Log your meals to see your trends.")
            .font(.subheadline)
            .foregroundColor(.secondary.opacity(0.8))
    }
    .frame(height: 240)
}

private struct TimePeriodSelector: View {
    @ObservedObject var nutritionManager: NutritionManager
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "chart.bar.fill")
                    .foregroundColor(.accentColor)
                    .font(.title2)
                Text("Nutrition Trends")
                    .font(.title3)
                    .fontWeight(.semibold)
                Spacer()
            }
            
            Picker("Time Period", selection: $nutritionManager.selectedGranularity) {
                Text("Daily").tag(NutritionTimeGranularity.daily)
                Text("Weekly").tag(NutritionTimeGranularity.weekly)
                Text("Monthly").tag(NutritionTimeGranularity.monthly)
            }
            .pickerStyle(.segmented)
            .onChange(of: nutritionManager.selectedGranularity) { _ in
            switch nutritionManager.selectedGranularity {
            case .daily:
                    nutritionManager.loadDailyData()
            case .weekly:
                    nutritionManager.loadWeeklyData()
            case .monthly:
                    nutritionManager.loadMonthlyData()
                }
            }
        }
        .cardStyle()
    }
}

// MARK: - Extensions

extension View {
    func cardStyle() -> some View {
        self
            .padding()
            .background(Color(.systemBackground))
            .cornerRadius(12)
            .shadow(color: Color.black.opacity(0.05), radius: 2, x: 0, y: 1)
    }
}

extension NutritionTimeGranularity {
    var stride: Calendar.Component {
        switch self {
        case .daily: return .day
        case .weekly: return .weekOfYear
        case .monthly: return .month
        }
    }

    var dateFormat: Date.FormatStyle {
        switch self {
        case .daily: return .dateTime.month().day()
        case .weekly: return .dateTime.month().day()
        case .monthly: return .dateTime.month(.abbreviated)
        }
    }
    
    var chartUnit: Calendar.Component {
        switch self {
        case .daily: return .day
        case .weekly: return .weekOfYear
        case .monthly: return .month
        }
    }
}



// MARK: - Color Mapping Functions
private func nutritionColor(for metricName: String) -> Color {
    switch metricName {
    case "Calories": return .orange
    case "Protein": return .red
    case "Carbs": return .blue
    case "Fat": return .yellow
    case "Fiber": return .green
    default: return .gray
    }
}

private func vitaminColor(for metricName: String) -> Color {
    switch metricName {
    case "Vit A": return .purple
    case "Vit C": return .pink
    case "Vit D": return .teal
    case "Vit E": return .indigo
    case "Vit K": return .mint
    case "Vit B1": return .cyan
    case "Vit B2": return .orange
    case "Vit B3": return .yellow
    case "Vit B6": return .red
    case "Vit B12": return .blue
    case "Folate": return .green
    default: return .gray
    }
}

/// Calculates consistent fixed bar width for all granularities since we now limit to 3 periods
@available(iOS 16.0, *)
private func dynamicBarWidth(for granularity: NutritionTimeGranularity, totalSlots: Int) -> MarkDimension {
    // Use fixed width for consistent visibility across all time granularities
    return .fixed(60)
}

private func countDistinctDates(_ chartData: NutritionChartData?) -> Int {
    guard let chartData = chartData else { return 0 }
    return Set(chartData.dataPoints.map { $0.parsedDate }).count
}

@available(iOS 16.0, *)
private func barWidth(for granularity: NutritionTimeGranularity) -> MarkDimension {
    // Use fixed bar width across all granularities for consistent visibility
    return .fixed(60)
}

/// Determines consistent horizontal spacing for all granularities since we now limit to 3 periods
private func span(for granularity: NutritionTimeGranularity) -> Double {
    // Use maximum span across all granularities for best bar visibility
        return 1.0
}

private func mineralColor(for metricName: String) -> Color {
    switch metricName {
    case "Calcium": return .gray
    case "Iron": return .red
    case "Magnesium": return .green
    case "Phosphorus": return .blue
    case "Potassium": return .orange
    case "Zinc": return .purple
    case "Copper": return .brown
    case "Manganese": return .pink
    case "Selenium": return .teal
    default: return .gray
    }
} 