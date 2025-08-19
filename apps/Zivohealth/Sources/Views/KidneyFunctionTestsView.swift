import SwiftUI
import Combine

struct KidneyFunctionTestsView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var kftTests: [KFTTest] = []
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var cancellables = Set<AnyCancellable>()
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Header Section
                KFTHeader(tests: kftTests)
                
                if isLoading {
                    ProgressView("Loading kidney function tests data...")
                        .padding()
                } else if let error = errorMessage {
                    Text("Error loading data: \(error)")
                        .foregroundColor(.red)
                        .padding()
                } else if kftTests.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "drop.triangle")
                            .font(.title)
                            .foregroundColor(.cyan)
                        
                        Text("No KFT Data Available")
                            .font(.headline)
                            .fontWeight(.semibold)
                        
                        Text("Upload your lab reports to see kidney function test results")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                } else {
                    // Test Cards
                    LazyVStack(spacing: 12) {
                        ForEach(kftTests) { test in
                            KFTTestCard(test: test)
                        }
                    }
                    .padding(.horizontal)
                }
                
                Spacer(minLength: 100)
            }
            .padding(.top, 20)
        }
        .background(Color(.systemGray6))
        .navigationBarHidden(true)
        .overlay(
            VStack {
                HStack {
                    Button(action: {
                        dismiss()
                    }) {
                        Image(systemName: "arrow.left")
                            .font(.title2)
                            .foregroundColor(.primary)
                            .padding(8)
                            .background(Color.white)
                            .clipShape(Circle())
                            .shadow(color: .black.opacity(0.1), radius: 2, x: 0, y: 1)
                    }
                    .padding(.leading, 16)
                    .padding(.top, 8)
                    
                    Spacer()
                }
                Spacer()
            },
            alignment: .topLeading
        )
        .onAppear {
            print("🫘 [KidneyFunctionTestsView] onAppear")
            loadKFTData()
        }
        .onDisappear {
            print("❌ [KidneyFunctionTestsView] onDisappear")
        }
    }
    
    private func loadKFTData() {
        print("🔄 [KidneyFunctionTestsView] Loading KFT data from API...")
        isLoading = true
        errorMessage = nil
        
        LabReportsAPIService.shared.getCategoryTestsData(category: "Kidney Function Tests (KFT)")
            .sink(
                receiveCompletion: { completion in
                    switch completion {
                    case .finished:
                        print("✅ [KidneyFunctionTestsView] KFT data loading completed")
                    case .failure(let error):
                        print("❌ [KidneyFunctionTestsView] Error loading KFT data: \(error)")
                        self.errorMessage = error.localizedDescription
                        self.isLoading = false
                        // Create empty data when API fails
                        self.kftTests = []
                    }
                },
                receiveValue: { response in
                    print("📊 [KidneyFunctionTestsView] Received \(response.tests.count) KFT tests")
                    self.convertToKFTModel(response)
                    self.isLoading = false
                }
            )
            .store(in: &cancellables)
    }
    
    private func convertToKFTModel(_ response: CategoryTestsResponse) {
        kftTests = response.tests.map { testData in
            KFTTest(
                name: testData.name,
                description: testData.description,
                value: testData.value.isEmpty ? "--" : testData.value,
                unit: testData.unit,
                normalRange: testData.normalRange,
                status: convertStatus(testData.status),
                lastTested: testData.lastTested.isEmpty ? "No data" : formatLastTested(testData.lastTested)
            )
        }
    }
    
    private func convertStatus(_ statusString: String) -> TestStatus {
        switch statusString.lowercased() {
        case "normal", "green":
            return .normal
        case "elevated", "high", "amber", "orange":
            return .elevated
        case "critical", "red":
            return .critical
        default:
            return .normal
        }
    }
    
    private func formatLastTested(_ dateString: String) -> String {
        if dateString.isEmpty {
            return "No data"
        }
        
        // Try to parse the date and convert to relative format
        let formatter = DateFormatter()
        formatter.dateFormat = "MMMM dd, yyyy"
        
        if let date = formatter.date(from: dateString) {
            let now = Date()
            let calendar = Calendar.current
            let components = calendar.dateComponents([.day], from: date, to: now)
            
            if let days = components.day {
                if days == 0 {
                    return "Today"
                } else if days == 1 {
                    return "1 day ago"
                } else if days < 7 {
                    return "\(days) days ago"
                } else if days < 14 {
                    return "1 week ago"
                } else if days < 30 {
                    return "\(days / 7) weeks ago"
                } else {
                    return dateString
                }
            }
        }
        
        return dateString
    }
}

struct KFTHeader: View {
    let tests: [KFTTest]
    
    var body: some View {
        VStack(spacing: 16) {
            HStack {
                Image(systemName: "drop.triangle.fill")
                    .font(.title)
                    .foregroundColor(.cyan)
                VStack(alignment: .leading, spacing: 4) {
                    Text("Kidney Function Tests")
                        .font(.title2)
                        .fontWeight(.bold)
                    Text("\(tests.count) tests • Last updated \(lastUpdatedText)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                Spacer()
            }
            HStack(spacing: 20) {
                StatusSummaryItem(icon: "checkmark.circle.fill", color: .green, count: normalCount, label: "Normal")
                StatusSummaryItem(icon: "exclamationmark.triangle.fill", color: .orange, count: elevatedCount, label: "Abnormal")
                StatusSummaryItem(icon: "xmark.circle.fill", color: .red, count: criticalCount, label: "Critical")
                Spacer()
            }
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: generateInsightIcon())
                    .foregroundColor(generateInsightColor())
                    .font(.title3)
                VStack(alignment: .leading, spacing: 4) {
                    Text(generateInsightTitle())
                        .font(.headline)
                        .fontWeight(.semibold)
                    Text(generateInsight())
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer()
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
        .padding(.horizontal)
    }
    
    private var normalCount: Int {
        tests.filter { $0.status == .normal }.count
    }
    
    private var elevatedCount: Int {
        tests.filter { $0.status == .elevated }.count
    }
    
    private var criticalCount: Int {
        tests.filter { $0.status == .critical }.count
    }
    
    private var lastUpdatedText: String {
        let recentTests = tests.filter { $0.lastTested != "No data" && $0.lastTested != "--" }
        if recentTests.isEmpty {
            return "No recent data"
        }
        return recentTests.first?.lastTested ?? "No recent data"
    }
    
    private func generateInsight() -> String {
        let hasElevated = elevatedCount > 0
        let hasCritical = criticalCount > 0
        let hasData = tests.contains { $0.value != "--" && $0.value != "" }
        
        if !hasData {
            return "No lab report data available. Upload your recent lab reports to see personalized insights."
        }
        
        if hasCritical {
            return "Critical values detected. Please consult with your healthcare provider immediately."
        } else if hasElevated {
            return "Some kidney function markers are abnormal. Consider discussing with your doctor."
        } else {
            return "All kidney function markers are within normal ranges. Your kidneys are filtering waste effectively."
        }
    }
    
    private func generateInsightTitle() -> String {
        let hasElevated = elevatedCount > 0
        let hasCritical = criticalCount > 0
        let hasData = tests.contains { $0.value != "--" && $0.value != "" }
        
        if !hasData {
            return "No Data Available"
        }
        
        if hasCritical {
            return "Critical Values Detected"
        } else if hasElevated {
            return "Abnormal Values"
        } else {
            return "Excellent Kidney Health"
        }
    }
    
    private func generateInsightIcon() -> String {
        let hasElevated = elevatedCount > 0
        let hasCritical = criticalCount > 0
        let hasData = tests.contains { $0.value != "--" && $0.value != "" }
        
        if !hasData {
            return "exclamationmark.circle.fill"
        }
        
        if hasCritical {
            return "xmark.circle.fill"
        } else if hasElevated {
            return "exclamationmark.triangle.fill"
        } else {
            return "checkmark.circle.fill"
        }
    }
    
    private func generateInsightColor() -> Color {
        let hasElevated = elevatedCount > 0
        let hasCritical = criticalCount > 0
        let hasData = tests.contains { $0.value != "--" && $0.value != "" }
        
        if !hasData {
            return .orange
        }
        
        if hasCritical {
            return .red
        } else if hasElevated {
            return .orange
        } else {
            return .green
        }
    }
}

struct KFTTestCard: View {
    let test: KFTTest
    
    var body: some View {
        VStack(spacing: 16) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(test.name)
                        .font(.headline)
                        .fontWeight(.semibold)
                    Text(test.description)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                Spacer()
                HStack(spacing: 4) {
                    Image(systemName: test.status.icon)
                        .foregroundColor(test.status.color)
                        .font(.caption)
                    Text(test.status.displayName)
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(test.status.color)
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(test.status.color.opacity(0.1))
                .cornerRadius(8)
            }
            HStack(spacing: 24) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Current Value")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    HStack(alignment: .bottom, spacing: 2) {
                        Text(test.value)
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(test.status.color)
                        Text(test.unit)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 4) {
                    Text("Normal Range")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(test.normalRange)
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(.primary)
                }
            }
            HStack {
                Text("Last tested: \(test.lastTested)")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Spacer()
                NavigationLink(destination: TestTrendsView(testName: test.name)) {
                    HStack(spacing: 4) {
                        Image(systemName: "chart.line.uptrend.xyaxis")
                        Text("View Trend")
                    }
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
}

struct KFTTest: Identifiable {
    let id = UUID()
    let name: String
    let description: String
    let value: String
    let unit: String
    let normalRange: String
    let status: TestStatus
    let lastTested: String
}

#Preview {
    NavigationView {
        KidneyFunctionTestsView()
    }
}
