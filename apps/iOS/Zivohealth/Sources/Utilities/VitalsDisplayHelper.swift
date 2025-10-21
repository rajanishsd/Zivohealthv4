import Foundation

/// Helper class for displaying vitals data consistently across all views
class VitalsDisplayHelper {
    
    // MARK: - Steps
    
    /// Get the latest steps count (only from today)
    static func getLatestSteps(from dashboardData: VitalDashboard?) -> String {
        guard let dashboardData = dashboardData,
              let stepsMetric = dashboardData.metrics.first(where: { $0.metricType == .stepCount }),
              let latestPoint = stepsMetric.dataPoints.last,
              let averageValue = latestPoint.averageValue,
              averageValue > 0,
              let dateString = latestPoint.date else {
            return "No data"
        }
        
        // Check if data is from today
        let date = parseDate(dateString)
        let calendar = Calendar.current
        guard calendar.isDateInToday(date) else {
            return "No data"
        }
        
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.groupingSeparator = ","
        return formatter.string(from: NSNumber(value: Int(averageValue))) ?? "0"
    }
    
    /// Get steps progress (0.0 to 1.0) based on 10,000 step goal
    static func getStepsProgress(from dashboardData: VitalDashboard?) -> Double {
        let stepsString = getLatestSteps(from: dashboardData).replacingOccurrences(of: ",", with: "")
        guard stepsString != "No data" else {
            return 0.0
        }
        let steps = Double(stepsString) ?? 0
        return min(steps / 10000.0, 1.0)
    }
    
    // MARK: - Sleep
    
    /// Get the latest sleep duration (only from yesterday or today)
    static func getLatestSleep(from dashboardData: VitalDashboard?) -> String {
        guard let dashboardData = dashboardData,
              let sleepMetric = dashboardData.metrics.first(where: { $0.metricType == .sleep }),
              let latestPoint = sleepMetric.dataPoints.last,
              let averageValue = latestPoint.averageValue,
              averageValue > 0,
              let dateString = latestPoint.date else {
            return "No data"
        }
        
        // Check if data is from yesterday (last night) or today
        let date = parseDate(dateString)
        let calendar = Calendar.current
        guard calendar.isDateInYesterday(date) || calendar.isDateInToday(date) else {
            return "No data"
        }
        
        let hours = Int(averageValue)
        let minutes = Int((averageValue - Double(hours)) * 60)
        return "\(hours)h \(minutes)m"
    }
    
    /// Get sleep progress (0.0 to 1.0) based on 8 hour goal
    static func getSleepProgress(from dashboardData: VitalDashboard?) -> Double {
        guard let dashboardData = dashboardData,
              let sleepMetric = dashboardData.metrics.first(where: { $0.metricType == .sleep }),
              let latestPoint = sleepMetric.dataPoints.last,
              let averageValue = latestPoint.averageValue,
              averageValue > 0,
              let dateString = latestPoint.date else {
            return 0.0
        }
        
        // Only show progress if data is from yesterday or today
        let date = parseDate(dateString)
        let calendar = Calendar.current
        guard calendar.isDateInYesterday(date) || calendar.isDateInToday(date) else {
            return 0.0
        }
        
        return min(averageValue / 8.0, 1.0) // Goal is 8 hours
    }
    
    // MARK: - Date Helpers
    
    /// Get formatted date string for sleep data (e.g., "today", "yesterday", "10d ago")
    static func getSleepDataDate(from dashboardData: VitalDashboard?) -> String? {
        guard let dashboardData = dashboardData,
              let sleepMetric = dashboardData.metrics.first(where: { $0.metricType == .sleep }),
              let latestPoint = sleepMetric.dataPoints.last,
              let dateString = latestPoint.date else {
            return nil
        }
        
        let date = parseDate(dateString)
        let calendar = Calendar.current
        if calendar.isDateInToday(date) {
            return "today"
        } else if calendar.isDateInYesterday(date) {
            return "yesterday"
        } else {
            let daysAgo = calendar.dateComponents([.day], from: date, to: Date()).day ?? 0
            if daysAgo > 0 {
                return "\(daysAgo)d ago"
            }
        }
        return nil
    }
    
    /// Get formatted date string for steps data (e.g., "today", "yesterday", "10d ago")
    static func getStepsDataDate(from dashboardData: VitalDashboard?) -> String? {
        guard let dashboardData = dashboardData,
              let stepsMetric = dashboardData.metrics.first(where: { $0.metricType == .stepCount }),
              let latestPoint = stepsMetric.dataPoints.last,
              let dateString = latestPoint.date else {
            return nil
        }
        
        let date = parseDate(dateString)
        let calendar = Calendar.current
        if calendar.isDateInToday(date) {
            return "today"
        } else if calendar.isDateInYesterday(date) {
            return "yesterday"
        } else {
            let daysAgo = calendar.dateComponents([.day], from: date, to: Date()).day ?? 0
            if daysAgo > 0 {
                return "\(daysAgo)d ago"
            }
        }
        return nil
    }
    
    /// Check if sleep data is stale (> 2 days old)
    static func isSleepDataStale(from dashboardData: VitalDashboard?) -> Bool {
        guard let dashboardData = dashboardData,
              let sleepMetric = dashboardData.metrics.first(where: { $0.metricType == .sleep }),
              let latestPoint = sleepMetric.dataPoints.last,
              let dateString = latestPoint.date else {
            return false
        }
        
        let date = parseDate(dateString)
        let daysAgo = Calendar.current.dateComponents([.day], from: date, to: Date()).day ?? 0
        return daysAgo > 2 // Stale if more than 2 days old
    }
    
    /// Check if steps data is stale (> 2 days old)
    static func isStepsDataStale(from dashboardData: VitalDashboard?) -> Bool {
        guard let dashboardData = dashboardData,
              let stepsMetric = dashboardData.metrics.first(where: { $0.metricType == .stepCount }),
              let latestPoint = stepsMetric.dataPoints.last,
              let dateString = latestPoint.date else {
            return false
        }
        
        let date = parseDate(dateString)
        let daysAgo = Calendar.current.dateComponents([.day], from: date, to: Date()).day ?? 0
        return daysAgo > 2 // Stale if more than 2 days old
    }
    
    // MARK: - Private Helpers
    
    private static func parseDate(_ dateString: String) -> Date {
        let iso8601Formatter = ISO8601DateFormatter()
        if let date = iso8601Formatter.date(from: dateString) {
            return date
        }
        
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: dateString) ?? Date()
    }
}

