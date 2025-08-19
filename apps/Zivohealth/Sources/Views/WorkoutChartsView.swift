import SwiftUI
import Charts

@available(iOS 16.0, *)
struct WorkoutChartsView: View {
    let chartData: ChartData
    let selectedGranularity: TimeGranularity
    
    var body: some View {
        TabView {
            // Duration Tab
            VStack(spacing: 0) {
                Chart {
                ForEach(Array(chartData.dataPoints.enumerated()), id: \.offset) { _, dataPoint in
                    let parsedDate = parseDate(dataPoint.date)
                    
                    BarMark(
                        x: .value("Date", parsedDate),
                        y: .value("Duration", dataPoint.value)
                    )
                    .foregroundStyle(.indigo)
                }
            }
            .frame(height: 220)
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
            .chartYAxis {
                AxisMarks(values: .automatic(desiredCount: 7)) { value in
                    AxisGridLine()
                    AxisValueLabel() { 
                        if let doubleValue = value.as(Double.self) {
                            Text("\(formatValue(doubleValue)) min")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
            }
            .tabItem {
                Image(systemName: "clock")
                Text("Duration")
            }
            
            // Calories Tab
            VStack(spacing: 0) {
                Chart {
                ForEach(Array(chartData.dataPoints.enumerated()), id: \.offset) { _, dataPoint in
                    let parsedDate = parseDate(dataPoint.date)
                    let calories = calculateCaloriesForDataPoint(dataPoint)
                    
                    BarMark(
                        x: .value("Date", parsedDate),
                        y: .value("Calories", calories)
                    )
                    .foregroundStyle(.orange)
                }
            }
            .frame(height: 220)
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
            .chartYAxis {
                AxisMarks(values: .automatic(desiredCount: 7)) { value in
                    AxisGridLine()
                    AxisValueLabel() { 
                        if let doubleValue = value.as(Double.self) {
                            Text("\(formatValue(doubleValue)) kcal")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
            }
            .tabItem {
                Image(systemName: "flame")
                Text("Calories")
            }
            
            // Distance Tab
            VStack(spacing: 0) {
                Chart {
                ForEach(Array(chartData.dataPoints.enumerated()), id: \.offset) { _, dataPoint in
                    let parsedDate = parseDate(dataPoint.date)
                    let distance = calculateDistanceForDataPoint(dataPoint)
                    
                    BarMark(
                        x: .value("Date", parsedDate),
                        y: .value("Distance", distance)
                    )
                    .foregroundStyle(.green)
                }
            }
            .frame(height: 220)
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
            .chartYAxis {
                AxisMarks(values: .automatic(desiredCount: 7)) { value in
                    AxisGridLine()
                    AxisValueLabel() { 
                        if let doubleValue = value.as(Double.self) {
                            Text(formatDistanceValue(doubleValue))
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
            }
            .tabItem {
                Image(systemName: "location")
                Text("Distance")
            }
        }
        .frame(height: 300)
        .padding(.horizontal, 16)
        .padding(.bottom, 30)
        .padding(.top, 10)
    }
    
    // MARK: - Helper Functions
    
    private func parseDate(_ dateString: String) -> Date {
        let iso8601Formatter = ISO8601DateFormatter()
        if let date = iso8601Formatter.date(from: dateString) {
            return date
        }
        
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        if let date = formatter.date(from: dateString) {
            return date
        }
        
        return Date()
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
    
    private func calculateCaloriesForDataPoint(_ dataPoint: ChartDataPoint) -> Double {
        if let workoutData = parseWorkoutData(dataPoint) {
            return workoutData.reduce(0) { total, workout in
                let caloriesPerMinute = getEstimatedCaloriesPerMinute(for: workout.type)
                return total + (workout.duration * caloriesPerMinute)
            }
        }
        return 0
    }
    
    private func calculateDistanceForDataPoint(_ dataPoint: ChartDataPoint) -> Double {
        if let workoutData = parseWorkoutData(dataPoint) {
            return workoutData.reduce(0) { total, workout in
                let distancePerMinute = getEstimatedDistancePerMinute(for: workout.type)
                return total + (workout.duration * distancePerMinute)
            }
        }
        return 0
    }
    
    private func parseWorkoutData(_ dataPoint: ChartDataPoint) -> [WorkoutTypeData]? {
        if let workoutBreakdown = dataPoint.workoutBreakdown, !workoutBreakdown.isEmpty {
            return workoutBreakdown.map { WorkoutTypeData(type: $0.key, duration: $0.value) }
                .sorted { $0.type < $1.type }
        }
        
        guard let label = dataPoint.label else { 
            return [WorkoutTypeData(type: "Workout", duration: dataPoint.value)]
        }
        
        if label.contains("Strength Training") {
            return [WorkoutTypeData(type: "Strength Training", duration: dataPoint.value)]
        } else if label.contains("Walking") {
            return [WorkoutTypeData(type: "Walking", duration: dataPoint.value)]
        } else if label.contains("Core Training") {
            return [WorkoutTypeData(type: "Core Training", duration: dataPoint.value)]
        } else {
            return [WorkoutTypeData(type: "Workout", duration: dataPoint.value)]
        }
    }
    
    private func getEstimatedCaloriesPerMinute(for workoutType: String) -> Double {
        switch workoutType {
        case "Running":
            return 10.0
        case "Cycling":
            return 8.0
        case "Strength Training", "Weight Training":
            return 6.0
        case "Walking":
            return 4.0
        case "Swimming":
            return 12.0
        case "HIIT":
            return 15.0
        case "Yoga", "Pilates":
            return 3.0
        case "Core Training":
            return 5.0
        default:
            return 5.0
        }
    }
    
    private func getEstimatedDistancePerMinute(for workoutType: String) -> Double {
        switch workoutType {
        case "Running":
            return 200.0
        case "Cycling":
            return 400.0
        case "Walking":
            return 80.0
        case "Swimming":
            return 40.0
        default:
            return 0.0
        }
    }
    
    private func formatDistanceValue(_ distance: Double) -> String {
        if distance >= 1000 {
            return String(format: "%.1f km", distance / 1000)
        } else if distance < 1 {
            return "0 m"
        } else {
            return String(format: "%.0f m", distance)
        }
    }
}

// Workout data structure
struct WorkoutTypeData {
    let type: String
    let duration: Double
}

#Preview {
    if #available(iOS 16.0, *) {
        WorkoutChartsView(
            chartData: ChartData(
                metricType: .workouts,
                unit: "min",
                granularity: .daily,
                dataPoints: [],
                minValue: 0,
                maxValue: 100,
                averageValue: 50,
                totalValue: 200
            ),
            selectedGranularity: .daily
        )
    } else {
        Text("iOS 16+ required")
    }
} 