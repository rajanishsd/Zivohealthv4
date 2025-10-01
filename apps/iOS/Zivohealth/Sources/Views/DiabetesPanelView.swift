import SwiftUI
import Combine

struct DiabetesPanelView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var diabetesTests: [DiabetesTest] = []
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var cancellables = Set<AnyCancellable>()
    
    var body: some View {
        VStack(spacing: 0) {
            // Custom Navigation Bar
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
                
                Spacer()
            }
            .padding(.top, 8)
            .padding(.bottom, 8)
            .background(Color(.systemGray6))
            
            // Content
        ScrollView {
            VStack(spacing: 20) {
                // Header Section
                DiabetesPanelHeader(tests: diabetesTests)
                
                if isLoading {
                    ProgressView("Loading diabetes panel data...")
                        .padding()
                } else if let error = errorMessage {
                    Text("Error loading data: \(error)")
                        .foregroundColor(.red)
                        .padding()
                } else if diabetesTests.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "drop.fill")
                            .font(.title)
                            .foregroundColor(.green)
                        
                        Text("No Diabetes Panel Data Available")
                            .font(.headline)
                            .fontWeight(.semibold)
                        
                        Text("Upload your lab reports to see diabetes test results")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                } else {
                    // Test Cards
                    LazyVStack(spacing: 12) {
                        ForEach(diabetesTests) { test in
                            DiabetesTestCard(test: test)
                        }
                    }
                    .padding(.horizontal)
                }
                
                Spacer(minLength: 100)
            }
        }
            .background(Color(.systemGray6))
        }
        .navigationBarHidden(true)
        .navigationBarTitleDisplayMode(.inline)
        .navigationTitle("")
        .onAppear {
            print("🩺 [DiabetesPanelView] onAppear")
            loadDiabetesPanelData()
        }
        .onDisappear {
            print("❌ [DiabetesPanelView] onDisappear")
        }
    }
    
    private func loadDiabetesPanelData() {
        print("🔄 [DiabetesPanelView] Loading diabetes panel data from API...")
        isLoading = true
        errorMessage = nil
        
        LabReportsAPIService.shared.getCategoryTestsData(category: "Diabetes Panel")
            .sink(
                receiveCompletion: { completion in
                    switch completion {
                    case .finished:
                        print("✅ [DiabetesPanelView] Diabetes data loading completed")
                    case .failure(let error):
                        print("❌ [DiabetesPanelView] Error loading diabetes data: \(error)")
                        self.errorMessage = error.localizedDescription
                        self.isLoading = false
                        // Create empty data when API fails
                        self.diabetesTests = []
                    }
                },
                receiveValue: { response in
                    print("📊 [DiabetesPanelView] Received \(response.tests.count) diabetes tests")
                    self.convertToDiabetesModel(response)
                    self.isLoading = false
                }
            )
            .store(in: &cancellables)
    }
    
    private func convertToDiabetesModel(_ response: CategoryTestsResponse) {
        diabetesTests = response.tests.map { testData in
            DiabetesTest(
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

// MARK: - Header
struct DiabetesPanelHeader: View {
    let tests: [DiabetesTest]
    
    var body: some View {
        VStack(spacing: 16) {
            // Icon and Title
            HStack {
                Image(systemName: "cross.case.fill")
                    .font(.title)
                    .foregroundColor(.green)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text("Diabetes Panel")
                        .font(.title2)
                        .fontWeight(.bold)
                    
                    Text("\(tests.count) tests • Last updated \(lastUpdatedText)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
            }
            
            // Status Summary
            HStack(spacing: 20) {
                StatusSummaryItem(
                    icon: "checkmark.circle.fill",
                    color: .green,
                    count: normalCount,
                    label: "Normal"
                )
                
                StatusSummaryItem(
                    icon: "exclamationmark.triangle.fill",
                    color: .orange,
                    count: elevatedCount,
                    label: "Elevated"
                )
                
                StatusSummaryItem(
                    icon: "xmark.circle.fill",
                    color: .red,
                    count: criticalCount,
                    label: "Critical"
                )
                
                Spacer()
            }
            
            // Key Insight
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: "lightbulb.fill")
                    .foregroundColor(.orange)
                    .font(.title3)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text("Key Insight")
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
            return "Some values are elevated. Consider monitoring carbohydrate intake and regular exercise."
        } else {
            return "Your diabetes panel shows normal values. Continue maintaining your healthy lifestyle."
        }
    }
}

// MARK: - Status Summary Item
struct StatusSummaryItem: View {
    let icon: String
    let color: Color
    let count: Int
    let label: String
    
    var body: some View {
        VStack(spacing: 4) {
            HStack(spacing: 4) {
                Image(systemName: icon)
                    .foregroundColor(color)
                    .font(.caption)
                
                Text("\(count)")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(color)
            }
            
            Text(label)
                .font(.caption2)
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - Test Card
struct DiabetesTestCard: View {
    let test: DiabetesTest
    
    var body: some View {
        VStack(spacing: 16) {
            // Header
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
                
                // Status Badge
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
            
            // Values Section
            HStack(spacing: 24) {
                // Current Value
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
                
                // Normal Range
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
            
            // Footer
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

// MARK: - Data Models
struct DiabetesTest: Identifiable {
    let id = UUID()
    let name: String
    let description: String
    let value: String
    let unit: String
    let normalRange: String
    let status: TestStatus
    let lastTested: String
}

enum TestStatus {
    case normal
    case elevated
    case critical
    
    var displayName: String {
        switch self {
        case .normal: return "Normal"
        case .elevated: return "Elevated"
        case .critical: return "Critical"
        }
    }
    
    var color: Color {
        switch self {
        case .normal: return .green
        case .elevated: return .orange
        case .critical: return .red
        }
    }
    
    var icon: String {
        switch self {
        case .normal: return "checkmark.circle.fill"
        case .elevated: return "exclamationmark.triangle.fill"
        case .critical: return "xmark.circle.fill"
        }
    }
}

// MARK: - Preview
#Preview {
    NavigationView {
        DiabetesPanelView()
    }
}
