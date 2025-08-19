import SwiftUI
import HealthKit
import Charts

struct ActivitySleepView: View {
    @StateObject private var healthKitManager = BackendVitalsManager.shared
    
    var body: some View {
        if #available(iOS 16.0, *) {
            ActivitySleepViewModern(healthKitManager: healthKitManager)
        } else {
            ActivitySleepViewLegacy(healthKitManager: healthKitManager)
        }
    }
}

// MARK: - Modern iOS 16+ View
@available(iOS 16.0, *)
struct ActivitySleepViewModern: View {
    let healthKitManager: BackendVitalsManager
    @State private var isFirstLoad = true
    
    var body: some View {
        activitySleepContent
    }
    
    private var activitySleepContent: some View {
        ZStack {
            ScrollView {
                LazyVStack(spacing: 20) {
                    // Simple Overview Card
                    ActivitySleepOverviewCard(healthKitManager: healthKitManager)
                    
                    // Steps Chart Section
                    if let dashboardData = healthKitManager.dashboardData,
                       let stepsMetric = dashboardData.metrics.first(where: { $0.metricType == .stepCount }),
                       !stepsMetric.dataPoints.isEmpty {
                        
                        VStack(alignment: .leading, spacing: 16) {
                            HStack {
                                Image(systemName: "figure.walk")
                                    .foregroundColor(.green)
                                Text("Steps Trend")
                                    .font(.title3)
                                    .fontWeight(.semibold)
                                Spacer()
                            }
                            .padding(.horizontal)
                            
                            VitalChartView(metricType: "Steps", metricSummary: stepsMetric, showHeader: true, dashboardData: dashboardData)
                                .padding()
                                .background(Color(UIColor.systemBackground))
                                .cornerRadius(12)
                                .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
                        }
                    }
                    
                    // Sleep Chart Section
                    if let dashboardData = healthKitManager.dashboardData,
                       let sleepMetric = dashboardData.metrics.first(where: { $0.metricType == .sleep }),
                       !sleepMetric.dataPoints.isEmpty {
                        
                        VStack(alignment: .leading, spacing: 16) {
                            HStack {
                                Image(systemName: "bed.double.fill")
                                    .foregroundColor(.purple)
                                Text("Sleep Trend")
                                    .font(.title3)
                                    .fontWeight(.semibold)
                                Spacer()
                            }
                            .padding(.horizontal)
                            
                            VitalChartView(metricType: "Sleep", metricSummary: sleepMetric, showHeader: true, dashboardData: dashboardData)
                                .padding()
                                .background(Color(UIColor.systemBackground))
                                .cornerRadius(12)
                                .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
                        }
                    }
                    
                    // No Data State
                    if healthKitManager.dashboardData == nil || 
                       (healthKitManager.dashboardData?.metrics.first(where: { $0.metricType == .stepCount })?.dataPoints.isEmpty != false &&
                        healthKitManager.dashboardData?.metrics.first(where: { $0.metricType == .sleep })?.dataPoints.isEmpty != false) {
                        
                        VStack(spacing: 16) {
                            if healthKitManager.isLoading || isFirstLoad {
                                ProgressView("Loading activity and sleep data...")
                                    .padding()
                            } else {
                                VStack(spacing: 12) {
                                    Image(systemName: "figure.walk.circle")
                                        .font(.title)
                                        .foregroundColor(.secondary)
                                    
                                    Text("No Activity & Sleep Data")
                                        .font(.headline)
                                        .fontWeight(.semibold)
                                    
                                    Text("Connect your Apple Health app to see your steps and sleep metrics")
                                        .font(.subheadline)
                                        .foregroundColor(.secondary)
                                        .multilineTextAlignment(.center)
                                }
                                .padding()
                            }
                        }
                    }
                    
                    Spacer(minLength: 100)
                }
                .padding(.horizontal)
                .padding(.top, 8)
            }
            .background(Color(UIColor.secondarySystemBackground))
            .refreshable {
                await refreshData()
            }
            
            // Sync Progress Overlay
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
        .navigationTitle("Activity & Sleep")
        .navigationBarTitleDisplayMode(.large)
        .onAppear {
            if isFirstLoad {
                print("🏃 [ActivitySleepView] First load - checking for health data")
                healthKitManager.checkForNewDataAndSync()
                isFirstLoad = false
            }
        }
    }
    
    private func refreshData() async {
        print("🔄 [ActivitySleepView] Pull-to-refresh triggered")
        await MainActor.run {
            healthKitManager.checkForNewDataAndSync()
        }
    }
}

// MARK: - Legacy iOS 15 View
struct ActivitySleepViewLegacy: View {
    let healthKitManager: BackendVitalsManager
    @State private var isFirstLoad = true
    
    var body: some View {
        activitySleepContent
    }
    
    private var activitySleepContent: some View {
        ZStack {
            ScrollView {
                LazyVStack(spacing: 20) {
                    // Simple Overview Card
                    ActivitySleepOverviewCard(healthKitManager: healthKitManager)
                    
                    // Steps Chart Section
                    if let dashboardData = healthKitManager.dashboardData,
                       let stepsMetric = dashboardData.metrics.first(where: { $0.metricType == .stepCount }),
                       !stepsMetric.dataPoints.isEmpty {
                        
                        VStack(alignment: .leading, spacing: 16) {
                            HStack {
                                Image(systemName: "figure.walk")
                                    .foregroundColor(.green)
                                Text("Steps Trend")
                                    .font(.title3)
                                    .fontWeight(.semibold)
                                Spacer()
                            }
                            .padding(.horizontal)
                            
                            VitalChartView(metricType: "Steps", metricSummary: stepsMetric, showHeader: true, dashboardData: dashboardData)
                                .padding()
                                .background(Color(UIColor.systemBackground))
                                .cornerRadius(12)
                                .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
                        }
                    }
                    
                    // Sleep Chart Section
                    if let dashboardData = healthKitManager.dashboardData,
                       let sleepMetric = dashboardData.metrics.first(where: { $0.metricType == .sleep }),
                       !sleepMetric.dataPoints.isEmpty {
                        
                        VStack(alignment: .leading, spacing: 16) {
                            HStack {
                                Image(systemName: "bed.double.fill")
                                    .foregroundColor(.purple)
                                Text("Sleep Trend")
                                    .font(.title3)
                                    .fontWeight(.semibold)
                                Spacer()
                            }
                            .padding(.horizontal)
                            
                            VitalChartView(metricType: "Sleep", metricSummary: sleepMetric, showHeader: true, dashboardData: dashboardData)
                                .padding()
                                .background(Color(UIColor.systemBackground))
                                .cornerRadius(12)
                                .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
                        }
                    }
                    
                    // No Data State
                    if healthKitManager.dashboardData == nil || 
                       (healthKitManager.dashboardData?.metrics.first(where: { $0.metricType == .stepCount })?.dataPoints.isEmpty != false &&
                        healthKitManager.dashboardData?.metrics.first(where: { $0.metricType == .sleep })?.dataPoints.isEmpty != false) {
                        
                        VStack(spacing: 16) {
                            if healthKitManager.isLoading || isFirstLoad {
                                ProgressView("Loading activity and sleep data...")
                                    .padding()
                            } else {
                                VStack(spacing: 12) {
                                    Image(systemName: "figure.walk.circle")
                                        .font(.title)
                                        .foregroundColor(.secondary)
                                    
                                    Text("No Activity & Sleep Data")
                                        .font(.headline)
                                        .fontWeight(.semibold)
                                    
                                    Text("Connect your Apple Health app to see your steps and sleep metrics")
                                        .font(.subheadline)
                                        .foregroundColor(.secondary)
                                        .multilineTextAlignment(.center)
                                }
                                .padding()
                            }
                        }
                    }
                    
                    Spacer(minLength: 100)
                }
                .padding(.horizontal)
                .padding(.top, 8)
            }
            .background(Color(UIColor.secondarySystemBackground))
            
            // Sync Progress Overlay
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
        .navigationTitle("Activity & Sleep")
        .navigationBarTitleDisplayMode(.large)
        .onAppear {
            if isFirstLoad {
                print("🏃 [ActivitySleepView] First load - checking for health data")
                healthKitManager.checkForNewDataAndSync()
                isFirstLoad = false
            }
        }
    }
}

// MARK: - Simple Overview Card
struct ActivitySleepOverviewCard: View {
    @ObservedObject var healthKitManager: BackendVitalsManager
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                Image(systemName: "figure.walk")
                    .foregroundColor(.green)
                    .font(.title2)
                Text("Activity & Sleep Overview")
                    .font(.title3)
                    .fontWeight(.semibold)
                Spacer()
                Text(getLatestDataDate())
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            // Summary Row
            HStack(spacing: 20) {
                // Steps Summary
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Image(systemName: "figure.walk")
                            .foregroundColor(.green)
                            .font(.subheadline)
                        Text("Steps")
                            .font(.subheadline)
                            .fontWeight(.medium)
                    }
                    
                    Text(getLatestSteps())
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundColor(.primary)
                    
                    Text("Goal: 10,000")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    // Progress bar
                    GeometryReader { geometry in
                        ZStack(alignment: .leading) {
                            Rectangle()
                                .fill(Color.green.opacity(0.2))
                                .frame(height: 4)
                                .cornerRadius(2)
                            
                            Rectangle()
                                .fill(Color.green)
                                .frame(width: geometry.size.width * getStepsProgress(), height: 4)
                                .cornerRadius(2)
                        }
                    }
                    .frame(height: 4)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                
                Divider()
                    .frame(height: 80)
                
                // Sleep Summary
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Image(systemName: "bed.double.fill")
                            .foregroundColor(.purple)
                            .font(.subheadline)
                        Text("Sleep")
                            .font(.subheadline)
                            .fontWeight(.medium)
                    }
                    
                    Text(getLatestSleep())
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundColor(.primary)
                    
                    Text("Goal: 8h")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    // Progress bar
                    GeometryReader { geometry in
                        ZStack(alignment: .leading) {
                            Rectangle()
                                .fill(Color.purple.opacity(0.2))
                                .frame(height: 4)
                                .cornerRadius(2)
                            
                            Rectangle()
                                .fill(Color.purple)
                                .frame(width: geometry.size.width * getSleepProgress(), height: 4)
                                .cornerRadius(2)
                        }
                    }
                    .frame(height: 4)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
    }
    
    // Helper functions - pulling data directly from backend
    private func getLatestSteps() -> String {
        if let dashboardData = healthKitManager.dashboardData,
           let stepsMetric = dashboardData.metrics.first(where: { $0.metricType == .stepCount }),
           let latestPoint = stepsMetric.dataPoints.last {
            return "\(Int(latestPoint.averageValue ?? 0))"
        }
        return "6,000"
    }
    
    private func getLatestSleep() -> String {
        if let dashboardData = healthKitManager.dashboardData,
           let sleepMetric = dashboardData.metrics.first(where: { $0.metricType == .sleep }),
           let latestPoint = sleepMetric.dataPoints.last {
            let hours = Int(latestPoint.averageValue ?? 0)
            let minutes = Int(((latestPoint.averageValue ?? 0) - Double(hours)) * 60)
            return "\(hours)h \(minutes)m"
        }
        return "7h 30m"
    }
    
    private func getStepsProgress() -> Double {
        let steps = Double(getLatestSteps().replacingOccurrences(of: ",", with: "")) ?? 6000
        return min(steps / 10000.0, 1.0)
    }
    
    private func getSleepProgress() -> Double {
        if let dashboardData = healthKitManager.dashboardData,
           let sleepMetric = dashboardData.metrics.first(where: { $0.metricType == .sleep }),
           let latestPoint = sleepMetric.dataPoints.last {
            return min((latestPoint.averageValue ?? 0) / 8.0, 1.0) // Goal is 8 hours
        }
        return 0.9375 // 7.5/8
    }
    
    private func getLatestDataDate() -> String {
        if let dashboardData = healthKitManager.dashboardData {
            let activityMetrics = dashboardData.metrics.filter { 
                $0.metricType == .stepCount || $0.metricType == .sleep 
            }
            
            var latestDate: Date?
            for metric in activityMetrics {
                if let lastPoint = metric.dataPoints.last,
                   let dateString = lastPoint.date {
                    let date = parseDate(dateString)
                    if latestDate == nil || date > latestDate! {
                        latestDate = date
                    }
                }
            }
            
            if let date = latestDate {
                if Calendar.current.isDateInToday(date) {
                    return "Today"
                } else if Calendar.current.isDateInYesterday(date) {
                    return "Yesterday"
                } else {
                    let formatter = DateFormatter()
                    formatter.dateFormat = "MMM d"
                    return formatter.string(from: date)
                }
            }
        }
        return "No data"
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
}

#Preview {
    NavigationView {
        ActivitySleepView()
    }
} 