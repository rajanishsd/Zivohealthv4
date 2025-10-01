import SwiftUI
import Combine

struct OthersView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var otherTests: [OtherTest] = []
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var cancellables = Set<AnyCancellable>()
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Header Section
                OthersHeader(tests: otherTests)
                
                if isLoading {
                    ProgressView("Loading other tests data...")
                        .padding()
                } else if let error = errorMessage {
                    Text("Error loading data: \(error)")
                        .foregroundColor(.red)
                        .padding()
                } else if otherTests.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "doc.text")
                            .font(.title)
                            .foregroundColor(.gray)
                        
                        Text("No Other Tests Available")
                            .font(.headline)
                            .fontWeight(.semibold)
                        
                        Text("Upload your lab reports to see other test results")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                } else {
                    // Test Cards
                    LazyVStack(spacing: 12) {
                        ForEach(otherTests) { test in
                            OtherTestCard(test: test)
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
            print("📄 [OthersView] onAppear")
            loadOtherData()
        }
        .onDisappear {
            print("❌ [OthersView] onDisappear")
        }
    }
    
    private func loadOtherData() {
        print("🔄 [OthersView] Loading other and uncategorized tests data from API...")
        isLoading = true
        errorMessage = nil
        
        LabReportsAPIService.shared.getOthersAndUncategorizedTestsData()
            .sink(
                receiveCompletion: { completion in
                    switch completion {
                    case .finished:
                        print("✅ [OthersView] Other and uncategorized tests data loading completed")
                    case .failure(let error):
                        print("❌ [OthersView] Error loading other and uncategorized tests data: \(error)")
                        self.errorMessage = error.localizedDescription
                        self.isLoading = false
                        // Create empty data when API fails
                        self.otherTests = []
                    }
                },
                receiveValue: { response in
                    print("📊 [OthersView] Received \(response.tests.count) other and uncategorized tests")
                    self.convertToOtherModel(response)
                    self.isLoading = false
                }
            )
            .store(in: &cancellables)
    }
    
    private func convertToOtherModel(_ response: CategoryTestsResponse) {
        otherTests = response.tests.map { testData in
            OtherTest(
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
struct OthersHeader: View {
    let tests: [OtherTest]
    
    private var normalCount: Int {
        tests.filter { $0.status == .normal }.count
    }
    
    private var elevatedCount: Int {
        tests.filter { $0.status == .elevated }.count
    }
    
    private var criticalCount: Int {
        tests.filter { $0.status == .critical }.count
    }
    
    private var lastUpdated: String {
        guard let mostRecent = tests.compactMap({ test in
            let formatter = DateFormatter()
            formatter.dateFormat = "MMMM dd, yyyy"
            return formatter.date(from: test.lastTested)
        }).max() else {
            return "No data"
        }
        
        let formatter = DateFormatter()
        formatter.dateFormat = "MMMM dd, yyyy"
        let dateString = formatter.string(from: mostRecent)
        
        let now = Date()
        let calendar = Calendar.current
        let components = calendar.dateComponents([.day], from: mostRecent, to: now)
        
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
        
        return dateString
    }
    
    private var healthInsight: HealthInsight {
        if criticalCount > 0 {
            return HealthInsight(
                icon: "xmark.circle.fill",
                color: .red,
                title: "Critical Results",
                message: "Some test results require immediate attention. Please consult your healthcare provider."
            )
        } else if elevatedCount > 0 {
            return HealthInsight(
                icon: "exclamationmark.triangle.fill",
                color: .orange,
                title: "Abnormal Results",
                message: "Some test results are outside normal ranges. Consider follow-up testing."
            )
        } else if normalCount > 0 {
            return HealthInsight(
                icon: "checkmark.circle.fill",
                color: .green,
                title: "All Tests Normal",
                message: "All test results are within normal ranges. Continue maintaining your healthy lifestyle."
            )
        } else {
            return HealthInsight(
                icon: "info.circle.fill",
                color: .blue,
                title: "No Data Available",
                message: "Upload your lab reports to see other test insights."
            )
        }
    }
    
    var body: some View {
        VStack(spacing: 16) {
            // Icon and Title
            HStack {
                Image(systemName: "doc.text")
                    .font(.title)
                    .foregroundColor(.gray)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text("Others")
                        .font(.title2)
                        .fontWeight(.bold)
                    
                    Text("\(tests.count) tests • Last updated \(lastUpdated)")
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
                    label: "Abnormal"
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
                Image(systemName: healthInsight.icon)
                    .foregroundColor(healthInsight.color)
                    .font(.title3)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(healthInsight.title)
                        .font(.headline)
                        .fontWeight(.semibold)
                    
                    Text(healthInsight.message)
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
}

// MARK: - Test Card
struct OtherTestCard: View {
    let test: OtherTest
    
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
struct OtherTest: Identifiable {
    let id = UUID()
    let name: String
    let description: String
    let value: String
    let unit: String
    let normalRange: String
    let status: TestStatus
    let lastTested: String
}


// MARK: - Preview
#Preview {
    NavigationView {
        OthersView()
    }
}
