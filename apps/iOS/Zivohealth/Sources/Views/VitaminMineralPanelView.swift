import SwiftUI
import Combine

struct VitaminMineralPanelView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var vitaminTests: [VitaminTest] = []
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var cancellables = Set<AnyCancellable>()
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Header Section
                VitaminMineralHeader(tests: vitaminTests)
                
                if isLoading {
                    ProgressView("Loading vitamin & mineral panel data...")
                        .padding()
                } else if let error = errorMessage {
                    Text("Error loading data: \(error)")
                        .foregroundColor(.red)
                        .padding()
                } else if vitaminTests.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "pills")
                            .font(.title)
                            .foregroundColor(.green)
                        
                        Text("No Vitamin & Mineral Data Available")
                            .font(.headline)
                            .fontWeight(.semibold)
                        
                        Text("Upload your lab reports to see vitamin & mineral panel results")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                } else {
                    // Test Cards
                    LazyVStack(spacing: 12) {
                        ForEach(vitaminTests) { test in
                            VitaminTestCard(test: test)
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
            print("💊 [VitaminMineralPanelView] onAppear")
            loadVitaminData()
        }
        .onDisappear {
            print("❌ [VitaminMineralPanelView] onDisappear")
        }
    }
    
    private func loadVitaminData() {
        print("🔄 [VitaminMineralPanelView] Loading vitamin data from API...")
        isLoading = true
        errorMessage = nil
        
        LabReportsAPIService.shared.getCategoryTestsData(category: "Vitamin & Mineral Panel")
            .sink(
                receiveCompletion: { completion in
                    switch completion {
                    case .finished:
                        print("✅ [VitaminMineralPanelView] Vitamin data loading completed")
                    case .failure(let error):
                        print("❌ [VitaminMineralPanelView] Error loading vitamin data: \(error)")
                        self.errorMessage = error.localizedDescription
                        self.isLoading = false
                        // Create empty data when API fails
                        self.vitaminTests = []
                    }
                },
                receiveValue: { response in
                    print("📊 [VitaminMineralPanelView] Received \(response.tests.count) vitamin tests")
                    self.convertToVitaminModel(response)
                    self.isLoading = false
                }
            )
            .store(in: &cancellables)
    }
    
    private func convertToVitaminModel(_ response: CategoryTestsResponse) {
        vitaminTests = response.tests.map { testData in
            VitaminTest(
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

struct VitaminMineralHeader: View {
    let tests: [VitaminTest]
    
    private var normalCount: Int {
        tests.filter { $0.status == .normal }.count
    }
    
    private var elevatedCount: Int {
        tests.filter { $0.status == .elevated }.count
    }
    
    private var criticalCount: Int {
        tests.filter { $0.status == .critical }.count
    }
    
    private var mostRecentTestDate: String {
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "MMMM dd, yyyy"
        
        var mostRecentDate: Date?
        
        for test in tests {
            if let date = dateFormatter.date(from: test.lastTested.replacingOccurrences(of: "Last tested: ", with: "")) {
                if mostRecentDate == nil || date > mostRecentDate! {
                    mostRecentDate = date
                }
            }
        }
        
        if let recentDate = mostRecentDate {
            let now = Date()
            let calendar = Calendar.current
            let components = calendar.dateComponents([.day], from: recentDate, to: now)
            
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
                    return dateFormatter.string(from: recentDate)
                }
            }
        }
        
        return "No recent data"
    }
    
    var body: some View {
        VStack(spacing: 16) {
            HStack {
                Image(systemName: "leaf.fill")
                    .font(.title)
                    .foregroundColor(.green)
                VStack(alignment: .leading, spacing: 4) {
                    Text("Vitamin & Mineral Panel")
                        .font(.title2)
                        .fontWeight(.bold)
                    Text("\(tests.count) tests • Last updated \(mostRecentTestDate)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                Spacer()
            }
            HStack(spacing: 20) {
                StatusSummaryItem(icon: "checkmark.circle.fill", color: .green, count: normalCount, label: "Normal")
                StatusSummaryItem(icon: "exclamationmark.triangle.fill", color: .orange, count: elevatedCount, label: "Low")
                StatusSummaryItem(icon: "xmark.circle.fill", color: .red, count: criticalCount, label: "Deficient")
                Spacer()
            }
            
            // Show attention message only if there are elevated or critical tests
            if elevatedCount > 0 || criticalCount > 0 {
                HStack(alignment: .top, spacing: 12) {
                    Image(systemName: criticalCount > 0 ? "xmark.circle.fill" : "exclamationmark.triangle.fill")
                        .foregroundColor(criticalCount > 0 ? .red : .orange)
                        .font(.title3)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(criticalCount > 0 ? "Critical Deficiency Detected" : "Vitamin Levels Need Attention")
                            .font(.headline)
                            .fontWeight(.semibold)
                        Text(criticalCount > 0 ? "Some vitamin levels are critically low. Please consult your healthcare provider immediately." : "Some vitamin levels are below optimal. Consider supplements and dietary improvements.")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    Spacer()
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
        .padding(.horizontal)
    }
}

struct VitaminTestCard: View {
    let test: VitaminTest
    
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

struct VitaminTest: Identifiable {
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
        VitaminMineralPanelView()
    }
}
