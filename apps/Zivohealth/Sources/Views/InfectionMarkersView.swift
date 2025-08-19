import SwiftUI
import Combine

struct InfectionMarkersView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var infectionTests: [InfectionTest] = []
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
                    InfectionMarkersHeader(tests: infectionTests)
                    
                    if isLoading {
                        ProgressView("Loading infection markers data...")
                            .padding()
                    } else if let error = errorMessage {
                        Text("Error loading data: \(error)")
                            .foregroundColor(.red)
                            .padding()
                    } else if infectionTests.isEmpty {
                        VStack(spacing: 12) {
                            Image(systemName: "shield.fill")
                                .font(.title)
                                .foregroundColor(.orange)
                            
                            Text("No Infection Markers Data Available")
                                .font(.headline)
                                .fontWeight(.semibold)
                            
                            Text("Upload your lab reports to see infection markers results")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                        }
                        .padding()
                    } else {
                        // Test Cards
                        LazyVStack(spacing: 12) {
                            ForEach(infectionTests) { test in
                                InfectionTestCard(test: test)
                            }
                        }
                        .padding(.horizontal)
                    }
                    
                    Spacer(minLength: 100)
                }
                .padding(.top, 20)
            }
            .background(Color(.systemGray6))
        }
        .navigationBarHidden(true)
        .navigationBarTitleDisplayMode(.inline)
        .navigationTitle("")
        .onAppear {
            print("🛡️ [InfectionMarkersView] onAppear")
            loadInfectionData()
        }
        .onDisappear {
            print("❌ [InfectionMarkersView] onDisappear")
        }
    }
    
    private func loadInfectionData() {
        print("🔄 [InfectionMarkersView] Loading infection data from API...")
        isLoading = true
        errorMessage = nil
        
        LabReportsAPIService.shared.getCategoryTestsData(category: "Infection Markers")
            .sink(
                receiveCompletion: { completion in
                    switch completion {
                    case .finished:
                        print("✅ [InfectionMarkersView] Infection data loading completed")
                    case .failure(let error):
                        print("❌ [InfectionMarkersView] Error loading infection data: \(error)")
                        self.errorMessage = error.localizedDescription
                        self.isLoading = false
                        // Create empty data when API fails
                        self.infectionTests = []
                    }
                },
                receiveValue: { response in
                    print("📊 [InfectionMarkersView] Received \(response.tests.count) infection tests")
                    self.convertToInfectionModel(response)
                    self.isLoading = false
                }
            )
            .store(in: &cancellables)
    }
    
    private func convertToInfectionModel(_ response: CategoryTestsResponse) {
        infectionTests = response.tests.map { testData in
            InfectionTest(
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

struct InfectionMarkersHeader: View {
    let tests: [InfectionTest]
    
    var body: some View {
        VStack(spacing: 16) {
            HStack {
                Image(systemName: "shield.fill")
                    .font(.title)
                    .foregroundColor(.orange)
                VStack(alignment: .leading, spacing: 4) {
                    Text("Infection Markers")
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
                StatusSummaryItem(icon: "exclamationmark.triangle.fill", color: .orange, count: elevatedCount, label: "Elevated")
                StatusSummaryItem(icon: "xmark.circle.fill", color: .red, count: criticalCount, label: "Positive")
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
        guard let mostRecent = tests.compactMap({ test in
            let formatter = DateFormatter()
            formatter.dateFormat = "MMMM dd, yyyy"
            return formatter.date(from: test.lastTested.replacingOccurrences(of: " ago", with: "").replacingOccurrences(of: "Today", with: "").replacingOccurrences(of: "No data", with: ""))
        }).max() else {
            return "No data"
        }
        
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        return formatter.string(from: mostRecent)
    }
    
    private func generateInsightIcon() -> String {
        if criticalCount > 0 {
            return "xmark.circle.fill"
        } else if elevatedCount > 0 {
            return "exclamationmark.triangle.fill"
        } else {
            return "checkmark.circle.fill"
        }
    }
    
    private func generateInsightColor() -> Color {
        if criticalCount > 0 {
            return .red
        } else if elevatedCount > 0 {
            return .orange
        } else {
            return .green
        }
    }
    
    private func generateInsightTitle() -> String {
        if tests.isEmpty {
            return "No Data Available"
        } else if criticalCount > 0 {
            return "Active Infections Detected"
        } else if elevatedCount > 0 {
            return "Elevated Markers"
        } else {
            return "No Active Infections"
        }
    }
    
    private func generateInsight() -> String {
        if tests.isEmpty {
            return "Upload your lab reports to see infection markers analysis and recommendations."
        } else if criticalCount > 0 {
            return "Critical infection markers detected. Please consult with your healthcare provider immediately."
        } else if elevatedCount > 0 {
            return "Some infection markers are elevated. Monitor symptoms and consider follow-up testing."
        } else {
            return "All infection markers are within normal ranges. No signs of bacterial or viral infections detected."
        }
    }
}

struct InfectionTestCard: View {
    let test: InfectionTest
    
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
                        if !test.unit.isEmpty {
                            Text(test.unit)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
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

struct InfectionTest: Identifiable {
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
        InfectionMarkersView()
    }
}
