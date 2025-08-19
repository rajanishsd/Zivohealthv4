import SwiftUI
import Charts
import Combine
import Foundation
import UIKit

struct TestTrendsView: View {
    let testName: String
    
    @State private var trendsData: TestTrendsResponse?
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var cancellables = Set<AnyCancellable>()
    @State private var selectedPeriod: TrendPeriod = .daily
    
    enum TrendPeriod: CaseIterable {
        case daily, monthly, quarterly, yearly
        
        var displayName: String {
            switch self {
            case .daily: return "Daily"
            case .monthly: return "Monthly"
            case .quarterly: return "Quarterly"
            case .yearly: return "Yearly"
            }
        }
    }
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                if isLoading {
                    ProgressView("Loading trends data...")
                        .padding()
                } else if let error = errorMessage {
                    VStack(spacing: 12) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.title)
                            .foregroundColor(.orange)
                        
                        Text("Error loading trends")
                            .font(.headline)
                            .fontWeight(.semibold)
                        
                        Text(error)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                } else if let trends = trendsData {
                    // Header Section
                    TestTrendsHeader(trends: trends)
                    
                    // Period Selector
                    PeriodSelector(selectedPeriod: $selectedPeriod)
                    
                    // Chart Section
                    TestTrendsChart(trends: trends, selectedPeriod: selectedPeriod)
                    
                    // Data Summary
                    TrendsDataSummary(trends: trends, selectedPeriod: selectedPeriod)
                } else {
                    VStack(spacing: 12) {
                        Image(systemName: "chart.line.uptrend.xyaxis")
                            .font(.title)
                            .foregroundColor(.blue)
                        
                        Text("No Trends Data Available")
                            .font(.headline)
                            .fontWeight(.semibold)
                        
                        Text("Upload more lab reports to see trend analysis")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                }
                
                Spacer(minLength: 100)
            }
        }
        .background(Color(UIColor.systemGray6))
        .navigationTitle("Trends")
        .navigationBarTitleDisplayMode(.large)
        .onAppear {
            loadTrendsData()
        }
    }
    
    private func loadTrendsData() {
        print("📈 [TestTrendsView] Loading trends data for: \(testName)")
        isLoading = true
        errorMessage = nil
        
        LabReportsAPIService.shared.getTestTrends(testName: testName)
            .sink(
                receiveCompletion: { completion in
                    switch completion {
                    case .finished:
                        print("✅ [TestTrendsView] Trends data loading completed")
                    case .failure(let error):
                        print("❌ [TestTrendsView] Error loading trends data: \(error)")
                        self.errorMessage = error.localizedDescription
                        self.isLoading = false
                    }
                },
                receiveValue: { response in
                    print("📊 [TestTrendsView] Received trends data for \(response.testName)")
                    self.trendsData = response
                    self.isLoading = false
                }
            )
            .store(in: &cancellables)
    }
}

// MARK: - Header
struct TestTrendsHeader: View {
    let trends: TestTrendsResponse
    
    var body: some View {
        VStack(spacing: 16) {
            // Test name and current value
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(trends.testName)
                        .font(.title2)
                        .fontWeight(.bold)
                    
                    Text("Last tested: \(trends.lastTested ?? "Unknown")")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                // Current status badge
                HStack(spacing: 4) {
                    Image(systemName: statusIcon(for: trends.currentStatus ?? "unknown"))
                        .foregroundColor(statusColor(for: trends.currentStatus ?? "unknown"))
                        .font(.caption)
                    
                    Text((trends.currentStatus ?? "unknown").capitalized)
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(statusColor(for: trends.currentStatus ?? "unknown"))
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(statusColor(for: trends.currentStatus ?? "unknown").opacity(0.1))
                .cornerRadius(8)
            }
            
            // Current value display
            HStack(spacing: 24) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Current Value")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    HStack(alignment: .bottom, spacing: 2) {
                        Text((trends.currentValue?.isEmpty ?? true) ? "--" : (trends.currentValue ?? "--"))
                            .font(.title)
                            .fontWeight(.bold)
                            .foregroundColor(statusColor(for: trends.currentStatus ?? "unknown"))
                        
                        Text(trends.currentUnit ?? "")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 4) {
                    Text("Normal Range")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Text((trends.normalRange?.isEmpty ?? true) ? "Not specified" : (trends.normalRange ?? "Not specified"))
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(.primary)
                        .multilineTextAlignment(.trailing)
                }
            }
        }
        .padding()
        .background(Color(UIColor.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
        .padding(.horizontal)
    }
    
    private func statusIcon(for status: String) -> String {
        switch status.lowercased() {
        case "normal": return "checkmark.circle.fill"
        case "elevated", "high": return "exclamationmark.triangle.fill"
        case "critical", "low": return "xmark.circle.fill"
        default: return "questionmark.circle.fill"
        }
    }
    
    private func statusColor(for status: String) -> Color {
        switch status.lowercased() {
        case "normal": return .green
        case "elevated", "high": return .orange
        case "critical", "low": return .red
        default: return .gray
        }
    }
}

// MARK: - Period Selector
struct PeriodSelector: View {
    @Binding var selectedPeriod: TestTrendsView.TrendPeriod
    
    var body: some View {
        HStack(spacing: 0) {
            ForEach(TestTrendsView.TrendPeriod.allCases, id: \.self) { period in
                Button(action: {
                    selectedPeriod = period
                }) {
                    Text(period.displayName)
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(selectedPeriod == period ? .white : .primary)
                        .padding(.vertical, 8)
                        .padding(.horizontal, 16)
                        .background(
                            selectedPeriod == period 
                                ? Color.blue 
                                : Color.clear
                        )
                        .cornerRadius(8)
                }
            }
        }
        .padding(4)
        .background(Color(UIColor.systemGray6))
        .cornerRadius(12)
        .padding(.horizontal)
    }
}

// MARK: - Chart
struct TestTrendsChart: View {
    let trends: TestTrendsResponse
    let selectedPeriod: TestTrendsView.TrendPeriod
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Trend Chart")
                    .font(.headline)
                    .fontWeight(.semibold)
                
                Spacer()
                
                Text(selectedPeriod.displayName)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            if #available(iOS 16.0, *) {
                Chart {
                    ForEach(Array(dataPoints.enumerated()), id: \.offset) { index, point in
                        if let value = point.value {
                            LineMark(
                                x: .value("Period", point.displayLabel),
                                y: .value("Value", value)
                            )
                            .foregroundStyle(Color.blue)
                            .lineStyle(StrokeStyle(lineWidth: 2))
                            
                            PointMark(
                                x: .value("Period", point.displayLabel),
                                y: .value("Value", value)
                            )
                            .foregroundStyle(pointColor(for: point.status))
                            .symbolSize(30)
                        }
                    }
                }
                .frame(height: 200)
                .chartYAxisLabel("Value (\(trends.currentUnit ?? ""))")
                .chartXAxisLabel("Time Period")
            } else {
                // Fallback for iOS 15
                VStack(spacing: 8) {
                    Text("Chart view requires iOS 16.0 or later")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    // Simple list view as fallback
                    ForEach(Array(dataPoints.prefix(5).enumerated()), id: \.offset) { index, point in
                        if let value = point.value {
                            HStack {
                                Text(point.displayLabel)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                
                                Spacer()
                                
                                Text("\(value, specifier: "%.2f")")
                                    .font(.caption)
                                    .fontWeight(.medium)
                                    .foregroundColor(pointColor(for: point.status))
                            }
                        }
                    }
                }
                .padding()
                .background(Color(UIColor.systemGray6))
                .cornerRadius(8)
            }
        }
        .padding()
        .background(Color(UIColor.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
        .padding(.horizontal)
    }
    
    private var dataPoints: [TrendDataPoint] {
        switch selectedPeriod {
        case .daily:
            return trends.trends.daily
        case .monthly:
            return trends.trends.monthly
        case .quarterly:
            return trends.trends.quarterly
        case .yearly:
            return trends.trends.yearly
        }
    }
    
    private func pointColor(for status: String?) -> Color {
        guard let status = status else { return .blue }
        switch status.lowercased() {
        case "green": return .green
        case "amber": return .orange
        case "red": return .red
        default: return .blue
        }
    }
}

// MARK: - Data Summary
struct TrendsDataSummary: View {
    let trends: TestTrendsResponse
    let selectedPeriod: TestTrendsView.TrendPeriod
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Data Points")
                .font(.headline)
                .fontWeight(.semibold)
            
            if dataPoints.isEmpty {
                HStack {
                    Image(systemName: "info.circle")
                        .foregroundColor(.orange)
                    
                    Text("No data available for this period")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .padding()
                .background(Color(UIColor.systemGray6))
                .cornerRadius(8)
            } else {
                LazyVStack(spacing: 8) {
                    ForEach(Array(dataPoints.prefix(10).enumerated()), id: \.offset) { index, point in
                        if let value = point.value {
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(point.displayLabel)
                                        .font(.subheadline)
                                        .fontWeight(.medium)
                                    
                                    if let count = point.count, count > 1 {
                                        Text("\(count) readings")
                                            .font(.caption2)
                                            .foregroundColor(.secondary)
                                    }
                                }
                                
                                Spacer()
                                
                                VStack(alignment: .trailing, spacing: 2) {
                                    Text("\(value, specifier: "%.2f") \(trends.currentUnit ?? "")")
                                        .font(.subheadline)
                                        .fontWeight(.medium)
                                    
                                    if let status = point.status {
                                        Text(status.capitalized)
                                            .font(.caption2)
                                            .foregroundColor(statusColor(for: status))
                                    }
                                }
                            }
                            .padding(.vertical, 4)
                        }
                    }
                }
            }
        }
        .padding()
        .background(Color(UIColor.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
        .padding(.horizontal)
    }
    
    private var dataPoints: [TrendDataPoint] {
        switch selectedPeriod {
        case .daily:
            return trends.trends.daily
        case .monthly:
            return trends.trends.monthly
        case .quarterly:
            return trends.trends.quarterly
        case .yearly:
            return trends.trends.yearly
        }
    }
    
    private func statusColor(for status: String) -> Color {
        switch status.lowercased() {
        case "green": return .green
        case "amber": return .orange
        case "red": return .red
        default: return .primary
        }
    }
}

// MARK: - Extensions
extension TrendDataPoint {
    var displayLabel: String {
        if let period = period {
            return period
        } else if let date = date {
            let formatter = DateFormatter()
            formatter.dateFormat = "yyyy-MM-dd"
            if let dateObj = formatter.date(from: date) {
                // Include year for daily data to distinguish between different years
                formatter.dateFormat = "MMM dd, yyyy"
                return formatter.string(from: dateObj)
            }
            return date
        } else if let year = year, let month = month {
            let dateFormatter = DateFormatter()
            return dateFormatter.monthSymbols[month - 1] + " \(year)"
        } else if let year = year, let quarter = quarter {
            return "Q\(quarter) \(year)"
        } else if let year = year {
            return "\(year)"
        }
        return "Unknown"
    }
}

// MARK: - Preview
#Preview {
    NavigationView {
        TestTrendsView(testName: "HbA1c")
    }
} 