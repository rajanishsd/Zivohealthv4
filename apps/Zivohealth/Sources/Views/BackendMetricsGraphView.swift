import SwiftUI
import Charts
import Combine

struct BackendMetricsGraphView: View {
    let metricType: String
    @State private var selectedGranularity: TimeGranularity = .daily
    @State private var selectedDays: Int = 30
    
    private let healthKitManager = BackendVitalsManager.shared
    @State private var cancellables = Set<AnyCancellable>()
    
    // Get chart data from dashboard data
    private var chartData: ChartData? {
        guard let dashboard = healthKitManager.dashboardData else { return nil }
        
        // Find the metric in dashboard data
        let targetMetricType = convertToVitalMetricType(metricType)
        let metricSummary = dashboard.metrics.first { $0.metricType == targetMetricType }
        guard let summary = metricSummary else { return nil }
        
        // Filter data points based on selected time period and granularity
        let endDate = Date()
        let daysToFetch = selectedGranularity == .daily ? selectedDays :
                         selectedGranularity == .weekly ? max(selectedDays, 84) : // At least 12 weeks for weekly view
                         365 // Full year for monthly view
        
        let startDate: Date
        if selectedDays >= 3650 { // "All data" option
            startDate = Date.distantPast
        } else {
            startDate = Calendar.current.date(byAdding: .day, value: -daysToFetch, to: endDate) ?? endDate
        }
        
        // Convert dashboard data points to chart data points and filter by date range
        let allDataPoints: [(Date, ChartDataPoint)]
        
        if metricType == "Heart Rate" {
            // For heart rate, create both min and max data points
            allDataPoints = summary.dataPoints.flatMap { point -> [(Date, ChartDataPoint)] in
                guard let dateString = point.date else { return [] }
                let date = parseDate(dateString)
                guard date >= startDate && date <= endDate else { return [] }
                
                var points: [(Date, ChartDataPoint)] = []
                
                // Add min value if available
                if let minValue = point.minValue {
                    let minPoint = ChartDataPoint(
                        date: dateString,
                        value: minValue,
                        label: "Min: \(Int(minValue)) bpm"
                    )
                    points.append((date, minPoint))
                }
                
                // Add max value if available
                if let maxValue = point.maxValue {
                    let maxPoint = ChartDataPoint(
                        date: dateString,
                        value: maxValue,
                        label: "Max: \(Int(maxValue)) bpm"
                    )
                    points.append((date, maxPoint))
                }
                
                return points
            }
        } else {
            // For other metrics, use average or total value as before
            allDataPoints = summary.dataPoints.compactMap { point -> (Date, ChartDataPoint)? in
                guard let dateString = point.date,
                      let value = point.averageValue ?? point.totalValue else { return nil }
                let date = parseDate(dateString)
                guard date >= startDate && date <= endDate else { return nil }
                
                let chartPoint = ChartDataPoint(
                    date: dateString,
                    value: value,
                    label: point.notes
                )
                return (date, chartPoint)
            }
        }
        
        // Aggregate data based on selected granularity
        let aggregatedDataPoints: [ChartDataPoint]
        
        switch selectedGranularity {
        case .daily:
            // For daily, just sort by date
            aggregatedDataPoints = allDataPoints
                .sorted { $0.0 < $1.0 }
                .map { $0.1 }
                
        case .weekly:
            // Group by week and aggregate
            let calendar = Calendar.current
            let weeklyGroups = Dictionary(grouping: allDataPoints) { datePoint in
                calendar.dateInterval(of: .weekOfYear, for: datePoint.0)?.start ?? datePoint.0
            }
            
            if metricType == "Heart Rate" {
                aggregatedDataPoints = weeklyGroups.flatMap { weekStart, points -> [ChartDataPoint] in
                    let values = points.map { $0.1.value }
                    let minValue = values.min() ?? 0
                    let maxValue = values.max() ?? 0
                    let dateFormatter = DateFormatter()
                    dateFormatter.dateFormat = "yyyy-MM-dd"
                    
                    var weekPoints: [ChartDataPoint] = []
                    
                    // Add min and max for the week
                    weekPoints.append(ChartDataPoint(
                        date: dateFormatter.string(from: weekStart),
                        value: minValue,
                        label: "Weekly Min: \(Int(minValue)) bpm"
                    ))
                    
                    weekPoints.append(ChartDataPoint(
                        date: dateFormatter.string(from: weekStart),
                        value: maxValue,
                        label: "Weekly Max: \(Int(maxValue)) bpm"
                    ))
                    
                    return weekPoints
                }.sorted { parseDate($0.date) < parseDate($1.date) }
            } else {
                aggregatedDataPoints = weeklyGroups.compactMap { weekStart, points in
                    let totalValue = points.reduce(0) { $0 + $1.1.value }
                    let averageValue = totalValue / Double(points.count)
                    let dateFormatter = DateFormatter()
                    dateFormatter.dateFormat = "yyyy-MM-dd"
                    
                    return ChartDataPoint(
                        date: dateFormatter.string(from: weekStart),
                        value: averageValue,
                        label: "Week of \(dateFormatter.string(from: weekStart))"
                    )
                }.sorted { parseDate($0.date) < parseDate($1.date) }
            }
            
        case .monthly:
            // Group by month and aggregate
            let calendar = Calendar.current
            let monthlyGroups = Dictionary(grouping: allDataPoints) { datePoint in
                calendar.dateInterval(of: .month, for: datePoint.0)?.start ?? datePoint.0
            }
            
            if metricType == "Heart Rate" {
                aggregatedDataPoints = monthlyGroups.flatMap { monthStart, points -> [ChartDataPoint] in
                    let values = points.map { $0.1.value }
                    let minValue = values.min() ?? 0
                    let maxValue = values.max() ?? 0
                    let dateFormatter = DateFormatter()
                    dateFormatter.dateFormat = "yyyy-MM-dd"
                    
                    var monthPoints: [ChartDataPoint] = []
                    
                    // Add min and max for the month
                    monthPoints.append(ChartDataPoint(
                        date: dateFormatter.string(from: monthStart),
                        value: minValue,
                        label: "Monthly Min: \(Int(minValue)) bpm"
                    ))
                    
                    monthPoints.append(ChartDataPoint(
                        date: dateFormatter.string(from: monthStart),
                        value: maxValue,
                        label: "Monthly Max: \(Int(maxValue)) bpm"
                    ))
                    
                    return monthPoints
                }.sorted { parseDate($0.date) < parseDate($1.date) }
            } else {
                aggregatedDataPoints = monthlyGroups.compactMap { monthStart, points in
                    let totalValue = points.reduce(0) { $0 + $1.1.value }
                    let averageValue = totalValue / Double(points.count)
                    let dateFormatter = DateFormatter()
                    dateFormatter.dateFormat = "yyyy-MM-dd"
                    
                    let monthFormatter = DateFormatter()
                    let monthIndex = calendar.component(.month, from: monthStart) - 1
                    let monthName = monthFormatter.monthSymbols[monthIndex]
                    
                    return ChartDataPoint(
                        date: dateFormatter.string(from: monthStart),
                        value: averageValue,
                        label: "Month of \(monthName)"
                    )
                }.sorted { parseDate($0.date) < parseDate($1.date) }
            }
        }
        
        // Debug logging
        print("🔍 [BackendMetricsGraphView] Chart data for \(metricType):")
        print("   - Granularity: \(selectedGranularity)")
        print("   - Days: \(selectedDays)")
        print("   - Date range: \(startDate) to \(endDate)")
        print("   - Found \(aggregatedDataPoints.count) data points after aggregation")
        print("   - Unit: \(summary.unit)")
        if !aggregatedDataPoints.isEmpty {
            print("   - Chart date range: \(aggregatedDataPoints.first?.date ?? "nil") to \(aggregatedDataPoints.last?.date ?? "nil")")
            print("   - Value range: \(aggregatedDataPoints.map { $0.value }.min() ?? 0) to \(aggregatedDataPoints.map { $0.value }.max() ?? 0)")
        }
        
        // Calculate statistics
        let values = aggregatedDataPoints.compactMap { $0.value }.filter { $0 > 0 }
        
        return ChartData(
            metricType: convertToVitalMetricType(metricType),
            unit: summary.unit,
            granularity: selectedGranularity,
            dataPoints: aggregatedDataPoints,
            minValue: values.min(),
            maxValue: values.max(),
            averageValue: values.isEmpty ? nil : values.reduce(0, +) / Double(values.count),
            totalValue: values.isEmpty ? nil : values.reduce(0, +)
        )
    }
    
    // MARK: - Computed Properties for View Components
    
    private var chartTitleView: some View {
        HStack {
            Text(metricType)
                .font(.title2)
                .fontWeight(.semibold)
            Spacer()
        }
        .padding(.horizontal)
    }
    
    private var controlsView: some View {
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
                        Text("All data").tag(3650) // ~10 years
                    }
                    .pickerStyle(.segmented)
                }
            }
        }
        .padding(.horizontal)
    }
    
    @ViewBuilder
    private var chartContentView: some View {
        if let chartData = chartData, !chartData.dataPoints.isEmpty {
            chartDataView(chartData)
        } else if healthKitManager.dashboardData == nil {
            loadingView
        } else {
            noDataView
        }
    }
    
    private var loadingView: some View {
        VStack(spacing: 12) {
            Image(systemName: "chart.line.uptrend.xyaxis")
                .font(.title)
                .foregroundColor(.secondary)
            
            Text("Loading dashboard data...")
                .font(.headline)
                .foregroundColor(.secondary)
        }
        .padding()
    }
    
    private var noDataView: some View {
        VStack(spacing: 12) {
            Image(systemName: "chart.line.uptrend.xyaxis")
                .font(.title)
                .foregroundColor(.secondary)
            
            Text("No data available")
                .font(.headline)
                .foregroundColor(.secondary)
            
            Text("Start tracking \(metricType.lowercased()) to see your trends")
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
    }
    
    @ViewBuilder
    private func chartDataView(_ chartData: ChartData) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            chartStatsView(chartData)
            chartView(chartData)
        }
    }
    
    @ViewBuilder
    private func chartStatsView(_ chartData: ChartData) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("\(chartData.dataPoints.count) data points")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Spacer()
            }
            .padding(.horizontal)
            
            if metricType == "Workouts" {
                workoutStatsView(chartData)
            } else {
                generalStatsView(chartData)
            }
        }
    }
    
    @ViewBuilder
    private func workoutStatsView(_ chartData: ChartData) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Total Duration")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text("\(formatValue(chartData.totalValue ?? 0)) \(chartData.unit)")
                        .font(.caption)
                        .fontWeight(.medium)
                }
                
                Spacer()
                
                VStack(alignment: .center, spacing: 2) {
                    Text("Total Calories")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text("Available in charts")
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 2) {
                    Text("Total Distance")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text("Available in charts")
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(.secondary)
                }
            }
            
            // Workout breakdown is available in the detailed charts
        }
        .padding(.horizontal)
    }
    
    @ViewBuilder
    private func generalStatsView(_ chartData: ChartData) -> some View {
        HStack {
            if let average = chartData.averageValue {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Average")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text("\(formatValue(average)) \(chartData.unit)")
                        .font(.caption)
                        .fontWeight(.medium)
                }
            }
            
            Spacer()
            
            if let min = chartData.minValue, let max = chartData.maxValue {
                VStack(alignment: .center, spacing: 2) {
                    Text("Range")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text("\(formatValue(min)) - \(formatValue(max))")
                        .font(.caption)
                        .fontWeight(.medium)
                }
            }
            
            Spacer()
            
            if let latest = chartData.dataPoints.last {
                VStack(alignment: .trailing, spacing: 2) {
                    Text("Latest")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text("\(formatValue(latest.value)) \(chartData.unit)")
                        .font(.caption)
                        .fontWeight(.medium)
                }
            }
        }
        .padding(.horizontal)
    }
    
    @ViewBuilder
    private func chartView(_ chartData: ChartData) -> some View {
        if #available(iOS 16.0, *) {
            modernChartView(chartData)
        } else {
            fallbackChartView(chartData)
        }
    }
    
    @available(iOS 16.0, *)
    @ViewBuilder
    private func modernChartView(_ chartData: ChartData) -> some View {
        if metricType == "Workouts" {
            workoutChartsView(chartData)
        } else {
            Chart {
                if metricType == "Heart Rate" {
                    heartRateChartContent(chartData)
                } else {
                    lineChartContent(chartData)
                }
            }
            .frame(height: 300)
            .chartXAxis {
                AxisMarks(values: .automatic(desiredCount: 7)) { value in
                    AxisGridLine()
                    if selectedGranularity == .monthly {
                        AxisValueLabel(format: .dateTime.month(.abbreviated), collisionResolution: .greedy)
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    } else {
                        AxisValueLabel(format: .dateTime.month(.abbreviated).day(), collisionResolution: .greedy)
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .chartXScale(domain: .automatic(includesZero: false))
            .chartYAxis {
                AxisMarks(values: .automatic(desiredCount: 7)) { value in
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
            .padding(.horizontal, 8)
            .padding(.bottom, 30)
            .padding(.top, 10)
            .frame(maxWidth: .infinity, alignment: .center)
        }
    }
    
    @available(iOS 16.0, *)
    @ViewBuilder
    private func workoutChartsView(_ chartData: ChartData) -> some View {
        WorkoutChartsView(chartData: chartData, selectedGranularity: selectedGranularity)
    }
    
    @available(iOS 16.0, *)
    @ChartContentBuilder
    private func heartRateChartContent(_ chartData: ChartData) -> some ChartContent {
        let groupedData = Dictionary(grouping: chartData.dataPoints) { parseDate($0.date) }
        
        ForEach(Array(groupedData.keys.sorted()), id: \.self) { date in
            if let dayData = groupedData[date] {
                let values = dayData.map { $0.value }
                let minValue = values.min() ?? 0
                let maxValue = values.max() ?? 0
                
                RectangleMark(
                    x: .value("Date", date),
                    yStart: .value("Min", minValue),
                    yEnd: .value("Max", maxValue),
                    width: 8
                )
                .foregroundStyle(getColorForMetric(metricType))
            }
        }
    }
    
    @available(iOS 16.0, *)
    @ChartContentBuilder
    private func lineChartContent(_ chartData: ChartData) -> some ChartContent {
        ForEach(Array(chartData.dataPoints.enumerated()), id: \.offset) { index, dataPoint in
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
    
    @ViewBuilder
    private func fallbackChartView(_ chartData: ChartData) -> some View {
        VStack(spacing: 8) {
            Text("Chart view requires iOS 16+")
                .font(.caption)
                .foregroundColor(.secondary)
                .padding()
            
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    ForEach(Array(chartData.dataPoints.enumerated()), id: \.offset) { index, dataPoint in
                        VStack(spacing: 4) {
                            Text(formatValue(dataPoint.value))
                                .font(.caption)
                                .fontWeight(.medium)
                                .foregroundColor(getColorForMetric(metricType))
                            
                            Rectangle()
                                .fill(getColorForMetric(metricType))
                                .frame(width: 8, height: max(20, CGFloat(dataPoint.value / (chartData.maxValue ?? 1)) * 60))
                            
                            Text(parseDate(dataPoint.date).formatted(.dateTime.month(.abbreviated).day()))
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                .padding(.horizontal, 8)
            }
            .frame(height: 120)
        }
        .padding(.horizontal, 8)
        .frame(maxWidth: .infinity, alignment: .center)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            chartTitleView
            
            VStack(alignment: .leading, spacing: 16) {
                controlsView
                chartContentView
            }
            .padding()
            .background(Color(UIColor.systemBackground))
            .cornerRadius(12)
            .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
            .padding(.horizontal)
        }
        .padding(.top, 40)
    }
    
    private func convertToVitalMetricType(_ type: String) -> VitalMetricType {
        switch type {
        case "Heart Rate": return .heartRate
        case "Blood Pressure": return .bloodPressureSystolic
        case "Blood Sugar": return .bloodSugar
        case "Temperature": return .bodyTemperature
        case "Weight": return .bodyMass
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
    
    private func parseDate(_ dateString: String) -> Date {
        // Try ISO8601DateFormatter first
        let iso8601Formatter = ISO8601DateFormatter()
        if let date = iso8601Formatter.date(from: dateString) {
            return date
        }
        
        // Try other DateFormatter formats
        let formatters = [
            // Simple date format (YYYY-MM-DD)
            { () -> DateFormatter in
                let formatter = DateFormatter()
                formatter.dateFormat = "yyyy-MM-dd"
                return formatter
            }(),
            
            // ISO with timezone
            { () -> DateFormatter in
                let formatter = DateFormatter()
                formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss'Z'"
                formatter.timeZone = TimeZone(secondsFromGMT: 0)
                return formatter
            }(),
            
            // ISO with milliseconds
            { () -> DateFormatter in
                let formatter = DateFormatter()
                formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'"
                formatter.timeZone = TimeZone(secondsFromGMT: 0)
                return formatter
            }(),
            
            DateFormatter.iso8601
        ]
        
        for formatter in formatters {
            if let date = formatter.date(from: dateString) {
                return date
            }
        }
        
        print("⚠️ [BackendMetricsGraphView] Could not parse date: '\(dateString)'")
        return Date() // Return current date as fallback instead of nil
    }
    
    private func getDateFormat() -> Date.FormatStyle {
        switch selectedGranularity {
        case .daily:
            return .dateTime.month(.abbreviated).day()
        case .weekly:
            return .dateTime.month(.abbreviated).day()
        case .monthly:
            return .dateTime.month(.abbreviated)
        }
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
    
    private func getColorForMetric(_ metricType: String) -> Color {
        switch metricType {
        case "Blood Pressure": return .red
        case "Heart Rate": return .pink
        case "Blood Sugar": return .purple
        case "Temperature": return .orange
        case "Weight": return .blue
        case "Steps": return .green
        case "Stand Hours": return .teal
        case "Active Energy": return .orange
        case "Workouts": return .indigo
        case "Workout Duration": return .indigo
        case "Workout Calories": return .red
        case "Workout Distance": return .cyan
        case "Sleep": return .purple
        case "Flights Climbed": return .mint
        default: return .blue
        }
    }

}

// Extension for ISO8601 date formatting
extension DateFormatter {
    static let iso8601: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'"
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        return formatter
    }()
}

#Preview {
    BackendMetricsGraphView(metricType: "Heart Rate")
        .padding()
} 