import SwiftUI
import Combine

struct ThyroidProfileView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var thyroidTests: [ThyroidTest] = []
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
                ThyroidProfileHeader(tests: thyroidTests)
                
                if isLoading {
                    ProgressView("Loading thyroid profile data...")
                        .padding()
                } else if let error = errorMessage {
                    Text("Error loading data: \(error)")
                        .foregroundColor(.red)
                        .padding()
                } else if thyroidTests.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "bolt.fill")
                            .font(.title)
                            .foregroundColor(.purple)
                        
                        Text("No Thyroid Data Available")
                            .font(.headline)
                            .fontWeight(.semibold)
                        
                        Text("Upload your lab reports to see thyroid profile results")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                } else {
                    // Test Cards
                    LazyVStack(spacing: 12) {
                        ForEach(thyroidTests) { test in
                            ThyroidTestCard(test: test)
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
        .navigationTitle("")
        .onAppear {
            print("🦋 [ThyroidProfileView] onAppear")
            loadThyroidData()
        }
        .onDisappear {
            print("❌ [ThyroidProfileView] onDisappear")
        }
    }
    
    private func loadThyroidData() {
        print("🔄 [ThyroidProfileView] Loading thyroid data from API...")
        isLoading = true
        errorMessage = nil
        
        LabReportsAPIService.shared.getCategoryTestsData(category: "Thyroid Profile")
            .sink(
                receiveCompletion: { completion in
                    switch completion {
                    case .finished:
                        print("✅ [ThyroidProfileView] Thyroid data loading completed")
                    case .failure(let error):
                        print("❌ [ThyroidProfileView] Error loading thyroid data: \(error)")
                        self.errorMessage = error.localizedDescription
                        self.isLoading = false
                        // Create empty data when API fails
                        self.thyroidTests = []
                    }
                },
                receiveValue: { response in
                    print("📊 [ThyroidProfileView] Received \(response.tests.count) thyroid tests")
                    self.convertToThyroidModel(response)
                    self.isLoading = false
                }
            )
            .store(in: &cancellables)
    }
    
    private func convertToThyroidModel(_ response: CategoryTestsResponse) {
        thyroidTests = response.tests.map { testData in
            ThyroidTest(
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
struct ThyroidProfileHeader: View {
    let tests: [ThyroidTest]
    
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
                message: "Some thyroid values require immediate attention. Please consult your healthcare provider."
            )
        } else if elevatedCount > 0 {
            return HealthInsight(
                icon: "exclamationmark.triangle.fill",
                color: .orange,
                title: "Abnormal Results",
                message: "Some thyroid values are outside normal ranges. Consider follow-up testing."
            )
        } else if normalCount > 0 {
            return HealthInsight(
                icon: "checkmark.circle.fill",
                color: .green,
                title: "Excellent Results",
                message: "All thyroid hormone levels are within normal ranges. Your thyroid function appears to be healthy."
            )
        } else {
            return HealthInsight(
                icon: "info.circle.fill",
                color: .blue,
                title: "No Data Available",
                message: "Upload your lab reports to see thyroid profile insights."
            )
        }
    }
    
    var body: some View {
        VStack(spacing: 16) {
            // Icon and Title
            HStack {
                Image(systemName: "bolt.fill")
                    .font(.title)
                    .foregroundColor(.purple)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text("Thyroid Profile")
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
struct ThyroidTestCard: View {
    let test: ThyroidTest
    
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
struct ThyroidTest: Identifiable {
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
        ThyroidProfileView()
    }
}
