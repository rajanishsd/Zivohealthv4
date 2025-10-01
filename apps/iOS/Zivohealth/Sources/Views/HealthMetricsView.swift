import SwiftUI
import HealthKit
import Charts
import Combine

struct HealthMetricsView: View {
    @State private var showingAddMetric = false
    @AppStorage("userMode") private var userMode: UserMode = .patient
    
    // Backend HealthKit manager to sync with backend API
    @StateObject private var healthKitManager = BackendVitalsManager.shared
    
    // Track if this is the first load to show appropriate loading state
    @State private var isFirstLoad = true
    
    // Break up the complex array expression
    private let basicMetrics = ["Blood Pressure", "Heart Rate", "Blood Sugar", "Temperature"]
    private let bodyMetrics = ["Weight", "Height", "BMI", "Oxygen Saturation"]
    private let activityMetrics = ["Steps", "Stand Hours", "Active Energy"]
    private let workoutMetrics = ["Workout Duration", "Workout Calories", "Workout Distance"]
    private let sleepMetrics = ["Sleep", "Flights Climbed"]
    
    private var metricTypes: [String] {
        basicMetrics + bodyMetrics + activityMetrics + workoutMetrics + sleepMetrics
    }

    var body: some View {
        ZStack {
            ScrollView {
                VStack(spacing: 0) {
                    // Personal health header
                    PersonalHealthHeaderView()
                    
                    if healthKitManager.isLoading && isFirstLoad {
                        // Loading state
                        VStack(spacing: 20) {
                            ProgressView()
                                .scaleEffect(1.2)
                            Text("Loading your health data...")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                        .frame(maxWidth: .infinity, minHeight: 200)
                        
                    } else if !healthKitManager.isAuthorized {
                        // Not authorized state - ONLY show connect button
                        VStack(spacing: 20) {
                            Image(systemName: "heart.circle")
                                .font(.system(size: 60))
                                .foregroundColor(.red)
                            
                            Text("Connect to Apple Health")
                                .font(.title2)
                                .fontWeight(.semibold)
                            
                            Text("Allow ZivoHealth to access your Apple Health data to track and analyze your health metrics.")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal)
                            
                            Button(action: {
                                print("🔍 [HealthMetricsView] Connect to Apple Health button tapped")
                                healthKitManager.requestAuthorization()
                            }) {
                                HStack {
                                    Image(systemName: "heart.fill")
                                    Text("Connect to Apple Health")
                                }
                                .font(.headline)
                                .foregroundColor(.white)
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.red)
                                .cornerRadius(12)
                            }
                            .padding(.horizontal)
                            
                            // Show error message if authorization failed
                            if let errorMessage = healthKitManager.errorMessage {
                                Text(errorMessage)
                                    .font(.caption)
                                    .foregroundColor(.red)
                                    .padding(.horizontal)
                                    .multilineTextAlignment(.center)
                            }
                        }
                        .frame(maxWidth: .infinity, minHeight: 300)
                        
                    } else {
                        // Authorized - show charts or empty state
                        if let dashboardData = healthKitManager.dashboardData, !dashboardData.metrics.isEmpty {
                        // Data available - show chart-based metrics view
                        LazyVStack(spacing: 0) {
                            ForEach(metricTypes, id: \.self) { metricType in
                                let vitalMetricType = convertToVitalMetricType(metricType)
                                let metricSummary = dashboardData.metrics.first { $0.metricType == vitalMetricType }
                                
                                if let summary = metricSummary, !summary.dataPoints.isEmpty {
                                    VStack(spacing: 0) {
                                        // Embedded chart view with time period controls
                                        VitalChartView(metricType: metricType, metricSummary: summary, showHeader: true, dashboardData: dashboardData)
                                            .padding()
                                            .background(Color(UIColor.systemBackground))
                                            .cornerRadius(12)
                                            .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
                                            .padding(.horizontal)
                                        
                                        Divider()
                                            .padding(.top, 16)
                                    }
                                }
                            }
                        }
                    } else {
                            // Authorized but no data - show empty charts
                        LazyVStack(spacing: 0) {
                            ForEach(metricTypes, id: \.self) { metricType in
                                VStack(spacing: 0) {
                                    // Empty chart card
                                    VStack(spacing: 16) {
                                        // Metric section header
                                        HStack {
                                            Image(systemName: getMetricIcon(for: metricType))
                                                .foregroundColor(getColorForMetric(metricType))
                                            Text(metricType)
                                                .font(.headline)
                                                .fontWeight(.semibold)
                                            Spacer()
                                            Text("No data")
                                                .font(.caption)
                                                .foregroundColor(.secondary)
                                        }
                                        
                                        // Empty chart placeholder
                                        VStack(spacing: 12) {
                                            Image(systemName: "chart.line.uptrend.xyaxis")
                                                .font(.title2)
                                                .foregroundColor(.secondary)
                                            Text("Pull down to refresh and sync data")
                                                .font(.subheadline)
                                                .foregroundColor(.secondary)
                                                .multilineTextAlignment(.center)
                                        }
                                        .frame(height: 120)
                                        .frame(maxWidth: .infinity)
                                    }
                                    .padding()
                                    .background(Color(UIColor.systemBackground))
                                    .cornerRadius(12)
                                    .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
                                    .padding(.horizontal)
                                    
                                    Divider()
                                        .padding(.top, 16)
                                }
                            }
                        }
                        }
                    }
                }
                .onAppear {
                    isFirstLoad = false
                    if healthKitManager.isAuthorized {
                    healthKitManager.checkAndRefreshIfNeeded()
                    }
                }
                .refreshable {
                    // Pull-to-refresh handles ALL sync operations
                    if healthKitManager.isAuthorized {
                        print("🔄 [HealthMetricsView] Pull-to-refresh triggered")
                        
                        do {
                            // First refresh dashboard data
                            try await healthKitManager.refreshDashboardAsync()
                            print("✅ [HealthMetricsView] Dashboard refresh completed")
                            
                            // Then check for new data and sync
                            healthKitManager.checkForNewDataAndSync()
                            print("✅ [HealthMetricsView] Data sync triggered")
                            
                        } catch {
                            print("❌ [HealthMetricsView] Pull-to-refresh error: \(error)")
                        }
                    } else {
                        print("⚠️ [HealthMetricsView] Pull-to-refresh attempted but not authorized")
                    }
                }
            }
            
            // Sync Progress Overlay - shows when syncing is in progress
            if healthKitManager.isSyncing {
                Color.black.opacity(0.3)
                    .ignoresSafeArea()
                    .overlay(
                        SyncProgressView(healthKitManager: healthKitManager)
                            .padding()
                    )
                    .transition(.opacity)
                    .animation(.easeInOut, value: healthKitManager.isSyncing)
            }
        }
        .background(Color(UIColor.secondarySystemBackground))
        .navigationTitle("Vitals")
        .navigationBarTitleDisplayMode(.large)
        // Remove all toolbar buttons - only pull-to-refresh now
    }
    
    private func getMetricIcon(for type: String) -> String {
        switch type {
        case "Blood Pressure": return "heart.fill"
        case "Heart Rate": return "waveform.path.ecg"
        case "Blood Sugar": return "drop.fill"
        case "Temperature": return "thermometer"
        case "Weight": return "scalemass"
        case "Height": return "ruler"
        case "BMI": return "person.fill"
        case "Oxygen Saturation": return "lungs.fill"
        case "Steps": return "figure.walk"
        case "Stand Hours": return "figure.stand"
        case "Active Energy": return "flame.fill"
        case "Workouts": return "dumbbell.fill"
        case "Sleep": return "bed.double.fill"
        case "Flights Climbed": return "figure.stairs"
        default: return "chart.line.uptrend.xyaxis"
        }
    }
    
    private func getColorForMetric(_ metricType: String) -> Color {
        switch metricType {
        case "Blood Pressure": return .red
        case "Heart Rate": return .pink
        case "Blood Sugar": return .purple
        case "Temperature": return .orange
        case "Weight": return .blue
        case "Height": return .cyan
        case "BMI": return .indigo
        case "Oxygen Saturation": return .mint
        case "Steps": return .green
        case "Stand Hours": return .teal
        case "Active Energy": return .orange
        case "Workouts": return .indigo
        case "Sleep": return .purple
        case "Flights Climbed": return .mint
        default: return .blue
        }
    }
    
    private func convertToVitalMetricType(_ type: String) -> VitalMetricType {
        switch type {
        case "Heart Rate": return .heartRate
        case "Blood Pressure": return .bloodPressureSystolic
        case "Blood Sugar": return .bloodSugar
        case "Temperature": return .bodyTemperature
        case "Weight": return .bodyMass
        case "Height": return .height
        case "BMI": return .bmi
        case "Oxygen Saturation": return .oxygenSaturation
        case "Steps": return .stepCount
        case "Stand Hours": return .standTime
        case "Active Energy": return .activeEnergy
        case "Workouts": return .workouts
        case "Workout Duration": return .workoutDuration
        case "Workout Calories": return .workoutCalories
        case "Workout Distance": return .workoutDistance
        case "Sleep": return .sleep
        case "Flights Climbed": return .flightsClimbed
        default: return .heartRate
        }
    }
}

// MARK: - VitalChartView
struct VitalChartView: View {
    let metricType: String
    let metricSummary: VitalMetricSummary
    let showHeader: Bool
    let dashboardData: VitalDashboard?
    @State private var selectedGranularity: TimeGranularity = .daily
    @State private var selectedDays: Int = 30
    @State private var chartData: ChartData?
    @State private var isLoading = false
    @State private var errorMessage: String?
    
    private let apiService = VitalsAPIService.shared
    @State private var cancellables = Set<AnyCancellable>()
    
    var body: some View {
        VStack(spacing: 16) {
            // Metric section header
            if showHeader {
                HStack {
                    Image(systemName: getMetricIcon(for: metricType))
                        .foregroundColor(getColorForMetric(metricType))
                    Text(metricType)
                        .font(.headline)
                        .fontWeight(.semibold)
                    Spacer()
                    if let chartData = chartData {
                        Text("\(chartData.dataPoints.count) data points")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    }
                }
            }
            
            // Controls section
            VStack(spacing: 12) {
                // Granularity Picker
                HStack {
                    Text("View:")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    Picker("Granularity", selection: $selectedGranularity) {
                        Text("Daily").tag(TimeGranularity.daily)
                        Text("Weekly").tag(TimeGranularity.weekly)
                        Text("Monthly").tag(TimeGranularity.monthly)
                    }
                    .pickerStyle(.segmented)
                }
                
                // Days Picker (only for daily view)
                if selectedGranularity == .daily {
                    HStack {
                        Text("Period:")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                        
                        Picker("Days", selection: $selectedDays) {
                            Text("7 days").tag(7)
                            Text("30 days").tag(30)
                            Text("90 days").tag(90)
                            Text("1 year").tag(365)
                        }
                        .pickerStyle(.segmented)
                    }
                } else {
                    // Fixed periods for weekly/monthly
                    HStack {
                        Text("Period:")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                        
                        if selectedGranularity == .weekly {
                            Picker("Period", selection: $selectedDays) {
                                Text("12 weeks").tag(84)
                                Text("26 weeks").tag(182)
                                Text("1 year").tag(365)
                            }
                            .pickerStyle(.segmented)
                        } else {
                            Picker("Period", selection: $selectedDays) {
                                Text("6 months").tag(180)
                                Text("1 year").tag(365)
                                Text("2 years").tag(730)
                            }
                            .pickerStyle(.segmented)
                        }
                    }
                }
            }
            .padding(.horizontal)
            
            // Chart section
            VStack(spacing: 8) {
                if isLoading {
                    ProgressView("Loading chart data...")
                        .frame(height: 200)
                } else if let errorMessage = errorMessage {
                    VStack(spacing: 8) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.title)
                            .foregroundColor(.orange)
                        Text(errorMessage)
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                        Button("Retry") {
                            fetchChartData()
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.small)
                    }
                    .frame(height: 200)
                } else if let chartData = chartData, !chartData.dataPoints.isEmpty {
                    chartContentView(chartData)
                } else {
                VStack(spacing: 12) {
                        Image(systemName: "chart.line.uptrend.xyaxis")
                            .font(.title)
                                    .foregroundColor(.secondary)
                        
                        Text("No data available")
                            .font(.headline)
                            .foregroundColor(.secondary)
                        
                        Text("No \(metricType.lowercased()) data found for the selected period.")
                                    .font(.caption)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .frame(height: 200)
                }
            }
        }
        .onChange(of: selectedGranularity) { _ in
            fetchChartData()
        }
        .onChange(of: selectedDays) { _ in
            fetchChartData()
        }
        .onAppear {
            fetchChartData()
        }
    }
    
    private func fetchChartData() {
        isLoading = true
        errorMessage = nil
        
        if metricType == "Blood Pressure" {
            fetchBloodPressureData()
        } else {
            let vitalMetricType = convertToVitalMetricType(metricType)
            fetchSingleMetricData(vitalMetricType)
        }
    }
    
    private func fetchBloodPressureData() {
        // Fetch both systolic and diastolic data in parallel
        let systolicPublisher = apiService.getChartData(
            for: .bloodPressureSystolic,
            granularity: selectedGranularity,
            days: selectedDays
        )
        
        let diastolicPublisher = apiService.getChartData(
            for: .bloodPressureDiastolic,
            granularity: selectedGranularity,
            days: selectedDays
        )
        
        Publishers.Zip(systolicPublisher, diastolicPublisher)
            .sink(
                receiveCompletion: { completion in
                    DispatchQueue.main.async {
                        self.isLoading = false
                        if case .failure(let error) = completion {
                            self.errorMessage = "Failed to load blood pressure data: \(error.localizedDescription)"
                            print("❌ [VitalChartView] Failed to fetch blood pressure data: \(error)")
                        }
                    }
                },
                receiveValue: { systolicData, diastolicData in
                    DispatchQueue.main.async {
                        // Combine systolic and diastolic data points
                        var combinedDataPoints: [ChartDataPoint] = []
                        
                        // Add systolic points with labels
                        for point in systolicData.dataPoints {
                            let systolicPoint = ChartDataPoint(
                                date: point.date,
                                value: point.value,
                                label: "Systolic: \(Int(point.value)) mmHg",
                                source: point.source,
                                workoutBreakdown: point.workoutBreakdown
                            )
                            combinedDataPoints.append(systolicPoint)
                        }
                        
                        // Add diastolic points with labels
                        for point in diastolicData.dataPoints {
                            let diastolicPoint = ChartDataPoint(
                                date: point.date,
                                value: point.value,
                                label: "Diastolic: \(Int(point.value)) mmHg",
                                source: point.source,
                                workoutBreakdown: point.workoutBreakdown
                            )
                            combinedDataPoints.append(diastolicPoint)
                        }
                        
                        // Create combined chart data
                        let allValues = combinedDataPoints.map { $0.value }
                        let combinedChartData = ChartData(
                            metricType: .bloodPressureSystolic,
                            unit: "mmHg",
                            granularity: self.selectedGranularity,
                            dataPoints: combinedDataPoints,
                            minValue: allValues.min(),
                            maxValue: allValues.max(),
                            averageValue: allValues.isEmpty ? nil : allValues.reduce(0, +) / Double(allValues.count),
                            totalValue: nil
                        )
                        
                        self.chartData = combinedChartData
                        self.errorMessage = nil
                    }
                }
            )
            .store(in: &cancellables)
    }
    
    private func fetchSingleMetricData(_ metricType: VitalMetricType) {
        apiService.getChartData(
            for: metricType,
            granularity: selectedGranularity,
            days: selectedDays
        )
        .sink(
            receiveCompletion: { completion in
                DispatchQueue.main.async {
                    self.isLoading = false
                    if case .failure(let error) = completion {
                        self.errorMessage = "Failed to load chart data: \(error.localizedDescription)"
                        print("❌ [VitalChartView] Failed to fetch chart data: \(error)")
                    }
                }
            },
            receiveValue: { data in
                DispatchQueue.main.async {
                    self.chartData = data
                    self.errorMessage = nil
                }
            }
        )
        .store(in: &cancellables)
    }
    
    @ViewBuilder
    private func chartContentView(_ chartData: ChartData) -> some View {
        if #available(iOS 16.0, *) {
            ModernVitalChartView(
                metricType: metricType,
                chartData: chartData,
                granularity: selectedGranularity
            )
        } else {
            FallbackVitalChartView(
                metricType: metricType,
                chartData: chartData,
                granularity: selectedGranularity
            )
        }
    }
    
    private func getMetricIcon(for type: String) -> String {
        switch type {
        case "Blood Pressure": return "heart.fill"
        case "Heart Rate": return "waveform.path.ecg"
        case "Blood Sugar": return "drop.fill"
        case "Temperature": return "thermometer"
        case "Weight": return "scalemass"
        case "Height": return "ruler"
        case "BMI": return "person.fill"
        case "Oxygen Saturation": return "lungs.fill"
        case "Steps": return "figure.walk"
        case "Stand Hours": return "figure.stand"
        case "Active Energy": return "flame.fill"
        case "Workouts": return "dumbbell.fill"
        case "Sleep": return "bed.double.fill"
        case "Flights Climbed": return "figure.stairs"
        default: return "chart.line.uptrend.xyaxis"
        }
    }
    
    private func getColorForMetric(_ metricType: String) -> Color {
        switch metricType {
        case "Blood Pressure": return .red
        case "Heart Rate": return .pink
        case "Blood Sugar": return .purple
        case "Temperature": return .orange
        case "Weight": return .blue
        case "Height": return .cyan
        case "BMI": return .indigo
        case "Oxygen Saturation": return .mint
        case "Steps": return .green
        case "Stand Hours": return .teal
        case "Active Energy": return .orange
        case "Workouts": return .indigo
        case "Sleep": return .purple
        case "Flights Climbed": return .mint
        default: return .blue
        }
    }
    
    private func convertToVitalMetricType(_ type: String) -> VitalMetricType {
        switch type {
        case "Heart Rate": return .heartRate
        case "Blood Pressure": return .bloodPressureSystolic
        case "Blood Sugar": return .bloodSugar
        case "Temperature": return .bodyTemperature
        case "Weight": return .bodyMass
        case "Height": return .height
        case "BMI": return .bmi
        case "Oxygen Saturation": return .oxygenSaturation
        case "Steps": return .stepCount
        case "Stand Hours": return .standTime
        case "Active Energy": return .activeEnergy
        case "Workouts": return .workouts
        case "Workout Duration": return .workoutDuration
        case "Workout Calories": return .workoutCalories
        case "Workout Distance": return .workoutDistance
        case "Sleep": return .sleep
        case "Flights Climbed": return .flightsClimbed
        default: return .heartRate
        }
    }
}

// MARK: - Modern Chart View (iOS 16+)
@available(iOS 16.0, *)
struct ModernVitalChartView: View {
    let metricType: String
    let chartData: ChartData
    let granularity: TimeGranularity
    
    var body: some View {
        Chart {
            if metricType == "Heart Rate" {
                // For heart rate, show daily min/max range as vertical bars
                ForEach(chartData.dataPoints, id: \.date) { dataPoint in
                    let parsedDate = parseDate(dataPoint.date)
                    let minValue = dataPoint.minValue ?? dataPoint.value
                    let maxValue = dataPoint.maxValue ?? dataPoint.value
                    
                    // Range bar from min to max heart rate
                    RectangleMark(
                        x: .value("Date", parsedDate),
                        yStart: .value("Min HR", minValue),
                        yEnd: .value("Max HR", maxValue),
                        width: 6
                    )
                    .foregroundStyle(getColorForMetric(metricType).opacity(0.8))
                    .cornerRadius(3)
                    
                    // Average point marker on the bar
                    PointMark(
                        x: .value("Date", parsedDate),
                        y: .value("Avg HR", dataPoint.value)
                    )
                    .foregroundStyle(.white)
                    .symbolSize(24)
                    .symbol(.circle)
                }
            } else if metricType == "Blood Pressure" {
                // For blood pressure, show systolic and diastolic as separate dot series
                let systolicPoints = chartData.dataPoints.filter { $0.label?.contains("Systolic") == true }
                let diastolicPoints = chartData.dataPoints.filter { $0.label?.contains("Diastolic") == true }
                
                // Systolic dots (red)
                ForEach(systolicPoints, id: \.date) { dataPoint in
                    PointMark(
                        x: .value("Date", parseDate(dataPoint.date)),
                        y: .value("mmHg", dataPoint.value)
                    )
                    .foregroundStyle(.red)
                    .symbolSize(80)
                    .symbol(.circle)
                }
                
                // Diastolic dots (blue)
                ForEach(diastolicPoints, id: \.date) { dataPoint in
                    PointMark(
                        x: .value("Date", parseDate(dataPoint.date)),
                        y: .value("mmHg", dataPoint.value)
                    )
                    .foregroundStyle(.blue)
                    .symbolSize(80)
                    .symbol(.circle)
                }
            } else {
                // For other metrics, use line chart
                ForEach(chartData.dataPoints, id: \.date) { dataPoint in
                    let parsedDate = parseDate(dataPoint.date)
                    
                    LineMark(
                        x: .value("Date", parsedDate),
                        y: .value(chartData.unit, dataPoint.value)
                    )
                    .foregroundStyle(getColorForMetric(metricType))
                    .lineStyle(StrokeStyle(lineWidth: 2))
                    .interpolationMethod(.catmullRom)
                    
                    PointMark(
                        x: .value("Date", parsedDate),
                        y: .value(chartData.unit, dataPoint.value)
                    )
                    .foregroundStyle(getColorForMetric(metricType))
                    .symbolSize(50)
                }
            }
        }
        .frame(height: 200)
        .frame(maxWidth: .infinity, alignment: .center)
        .chartXAxis {
            AxisMarks(values: .automatic(desiredCount: 7)) { value in
                AxisGridLine()
                AxisValueLabel(format: getDateFormat(), collisionResolution: .greedy)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
        .chartXScale(domain: .automatic(includesZero: false))
        .chartYAxis {
            AxisMarks(values: .automatic(desiredCount: 4)) { value in
                AxisGridLine()
                AxisValueLabel() { 
                    if let doubleValue = value.as(Double.self) {
                        Text(formatValue(doubleValue))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
        .chartPlotStyle { plotArea in
            plotArea.frame(maxWidth: .infinity)
        }
        .chartLegend(.visible)
        .padding(.horizontal, 8)
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
    
    private func formatValue(_ value: Double) -> String {
        if value >= 1000 {
            return String(format: "%.1fK", value / 1000)
        } else if value >= 100 {
            return String(format: "%.0f", value)
        } else if value >= 10 {
            return String(format: "%.1f", value)
        } else {
            return String(format: "%.2f", value)
        }
    }
    
    private func getDateFormat() -> Date.FormatStyle {
        switch granularity {
        case .daily:
            return .dateTime.month(.abbreviated).day()
        case .weekly:
            return .dateTime.month(.abbreviated).day()
        case .monthly:
            return .dateTime.month(.abbreviated)
        }
    }
    
    private func getColorForMetric(_ metricType: String) -> Color {
        switch metricType {
        case "Blood Pressure": return .red
        case "Heart Rate": return .pink
        case "Blood Sugar": return .purple
        case "Temperature": return .orange
        case "Weight": return .blue
        case "Height": return .cyan
        case "BMI": return .indigo
        case "Oxygen Saturation": return .mint
        case "Steps": return .green
        case "Stand Hours": return .teal
        case "Active Energy": return .orange
        case "Workouts": return .indigo
        case "Sleep": return .purple
        case "Flights Climbed": return .mint
        default: return .blue
        }
    }
}

// MARK: - Fallback Chart View (iOS < 16)
struct FallbackVitalChartView: View {
    let metricType: String
    let chartData: ChartData
    let granularity: TimeGranularity
    
    var body: some View {
        VStack(spacing: 8) {
            // Legend for blood pressure chart
            if metricType == "Blood Pressure" {
                HStack(spacing: 16) {
                    HStack(spacing: 4) {
                        Circle()
                            .fill(.red)
                            .frame(width: 8, height: 8)
                        Text("Systolic")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                    
                    HStack(spacing: 4) {
                        Circle()
                            .fill(.blue)
                            .frame(width: 8, height: 8)
                        Text("Diastolic")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                    
                    Spacer()
                }
                .padding(.horizontal, 8)
            }
            
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 12) {
                if metricType == "Heart Rate" {
                    // For heart rate, show daily min/max range as bars
                    ForEach(chartData.dataPoints, id: \.date) { dataPoint in
                        let minValue = dataPoint.minValue ?? dataPoint.value
                        let maxValue = dataPoint.maxValue ?? dataPoint.value
                            
                            VStack(spacing: 4) {
                            // Max value label
                                Text("\(Int(maxValue))")
                                    .font(.caption2)
                                    .fontWeight(.medium)
                                    .foregroundColor(getColorForMetric(metricType))
                                
                            // Range bar from min to max
                                VStack(spacing: 0) {
                                Rectangle()
                                        .fill(getColorForMetric(metricType))
                                    .frame(width: 8, height: max(10, CGFloat((maxValue - minValue) / (chartData.maxValue ?? 1)) * 80))
                                }
                                
                            // Min value label
                                Text("\(Int(minValue))")
                                    .font(.caption2)
                                    .fontWeight(.medium)
                                    .foregroundColor(getColorForMetric(metricType))
                            
                            // Average value with different styling
                            Text("avg: \(Int(dataPoint.value))")
                                .font(.caption2)
                                .fontWeight(.bold)
                                .foregroundColor(getColorForMetric(metricType))
                                .padding(.vertical, 2)
                                .padding(.horizontal, 4)
                                .background(getColorForMetric(metricType).opacity(0.1))
                                .cornerRadius(4)
                            
                            // Date label
                            Text(parseDate(dataPoint.date).formatted(getDateFormat()))
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                    }
                } else if metricType == "Blood Pressure" {
                    // For blood pressure, show systolic and diastolic as separate dots
                    let groupedData = Dictionary(grouping: chartData.dataPoints) { parseDate($0.date) }
                    
                    ForEach(Array(groupedData.keys.sorted()), id: \.self) { date in
                        if let dayData = groupedData[date] {
                                let systolicPoints = dayData.filter { $0.label?.contains("Systolic") == true }
                                let diastolicPoints = dayData.filter { $0.label?.contains("Diastolic") == true }
                                
                                VStack(spacing: 6) {
                                    // Systolic dot (red)
                                    if let systolicValue = systolicPoints.first?.value {
                                        VStack(spacing: 2) {
                                            Text("\(Int(systolicValue))")
                                    .font(.caption2)
                                    .fontWeight(.medium)
                                                .foregroundColor(.red)
                                            
                                            Circle()
                                                .fill(.red)
                                                .frame(width: 8, height: 8)
                                        }
                                    }
                                    
                                    // Diastolic dot (blue)
                                    if let diastolicValue = diastolicPoints.first?.value {
                                        VStack(spacing: 2) {
                                            Text("\(Int(diastolicValue))")
                                    .font(.caption2)
                                    .fontWeight(.medium)
                                                .foregroundColor(.blue)
                                            
                                            Circle()
                                                .fill(.blue)
                                                .frame(width: 8, height: 8)
                                        }
                                    }
                                
                                Text(date.formatted(getDateFormat()))
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                } else {
                    // For other metrics, use single value bars
                        ForEach(chartData.dataPoints, id: \.date) { dataPoint in
                        VStack(spacing: 4) {
                            Text(formatValue(dataPoint.value))
                                .font(.caption)
                                .fontWeight(.medium)
                                .foregroundColor(getColorForMetric(metricType))
                            
                            Rectangle()
                                .fill(getColorForMetric(metricType))
                                .frame(width: 8, height: max(8, CGFloat(dataPoint.value / (chartData.maxValue ?? 1)) * 60))
                            
                            Text(parseDate(dataPoint.date).formatted(getDateFormat()))
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                    }
                }
            }
            .padding(.horizontal, 8)
        }
        .frame(height: 120)
        }
        .frame(maxWidth: .infinity, alignment: .center)
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
    
    private func formatValue(_ value: Double) -> String {
        if value >= 1000 {
            return String(format: "%.1fK", value / 1000)
        } else if value >= 100 {
            return String(format: "%.0f", value)
        } else if value >= 10 {
            return String(format: "%.1f", value)
        } else {
            return String(format: "%.2f", value)
        }
    }
    
    private func getDateFormat() -> Date.FormatStyle {
        switch granularity {
        case .daily:
            return .dateTime.month(.abbreviated).day()
        case .weekly:
            return .dateTime.month(.abbreviated).day()
        case .monthly:
            return .dateTime.month(.abbreviated)
        }
    }
    
    private func getColorForMetric(_ metricType: String) -> Color {
        switch metricType {
        case "Blood Pressure": return .red
        case "Heart Rate": return .pink
        case "Blood Sugar": return .purple
        case "Temperature": return .orange
        case "Weight": return .blue
        case "Height": return .cyan
        case "BMI": return .indigo
        case "Oxygen Saturation": return .mint
        case "Steps": return .green
        case "Stand Hours": return .teal
        case "Active Energy": return .orange
        case "Workouts": return .indigo
        case "Sleep": return .purple
        case "Flights Climbed": return .mint
        default: return .blue
        }
    }
}

// Personal health header
struct PersonalHealthHeaderView: View {
    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Image(systemName: "heart.text.square")
                    .font(.title2)
                    .foregroundColor(.red)
                
                VStack(alignment: .leading, spacing: 1) {
                    Text("Vitals")
                        .font(.headline)
                        .fontWeight(.semibold)
                    
                    Text("Your health metrics from Apple Health app")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
            }
            .padding(.horizontal)
            
            Divider()
        }
        .background(Color(UIColor.systemBackground))
    }
}

#Preview {
    HealthMetricsView()
}
