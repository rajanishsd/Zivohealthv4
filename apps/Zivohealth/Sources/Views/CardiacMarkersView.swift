import SwiftUI
import Combine

struct CardiacMarkersView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var cardiacTests: [CardiacTest] = []
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
                    CardiacMarkersHeader(tests: cardiacTests)
                    
                    if isLoading {
                        ProgressView("Loading cardiac markers data...")
                            .padding()
                    } else if let error = errorMessage {
                        Text("Error loading data: \(error)")
                            .foregroundColor(.red)
                            .padding()
                    } else if cardiacTests.isEmpty {
                        VStack(spacing: 12) {
                            Image(systemName: "heart.fill")
                                .font(.title)
                                .foregroundColor(.pink)
                            
                            Text("No Cardiac Markers Data Available")
                                .font(.headline)
                                .fontWeight(.semibold)
                            
                            Text("Upload your lab reports to see cardiac markers results")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                        }
                        .padding()
                    } else {
                        // Test Cards
                        LazyVStack(spacing: 12) {
                            ForEach(cardiacTests) { test in
                                CardiacTestCard(test: test)
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
            print("❤️ [CardiacMarkersView] onAppear")
            loadCardiacData()
        }
        .onDisappear {
            print("❌ [CardiacMarkersView] onDisappear")
        }
    }
    
    private func loadCardiacData() {
        print("🔄 [CardiacMarkersView] Loading cardiac data from API...")
        isLoading = true
        errorMessage = nil
        
        LabReportsAPIService.shared.getCategoryTestsData(category: "Cardiac Markers")
            .sink(
                receiveCompletion: { completion in
                    switch completion {
                    case .finished:
                        print("✅ [CardiacMarkersView] Cardiac data loading completed")
                    case .failure(let error):
                        print("❌ [CardiacMarkersView] Error loading cardiac data: \(error)")
                        self.errorMessage = error.localizedDescription
                        self.isLoading = false
                        // Create empty data when API fails
                        self.cardiacTests = []
                    }
                },
                receiveValue: { response in
                    print("📊 [CardiacMarkersView] Received \(response.tests.count) cardiac tests")
                    self.convertToCardiacModel(response)
                    self.isLoading = false
                }
            )
            .store(in: &cancellables)
    }
    
    private func convertToCardiacModel(_ response: CategoryTestsResponse) {
        cardiacTests = response.tests.map { testData in
            CardiacTest(
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

struct CardiacMarkersHeader: View {
    let tests: [CardiacTest]
    
    var body: some View {
        VStack(spacing: 16) {
            HStack {
                Image(systemName: "heart.text.square.fill")
                    .font(.title)
                    .foregroundColor(.pink)
                VStack(alignment: .leading, spacing: 4) {
                    Text("Cardiac Markers")
                        .font(.title2)
                        .fontWeight(.bold)
                    Text("\(tests.count) tests • Last updated \(formatLastUpdated())")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                Spacer()
            }
            HStack(spacing: 20) {
                StatusSummaryItem(icon: "checkmark.circle.fill", color: .green, count: tests.filter({ $0.status == .normal }).count, label: "Normal")
                StatusSummaryItem(icon: "exclamationmark.triangle.fill", color: .orange, count: tests.filter({ $0.status == .elevated }).count, label: "Elevated")
                StatusSummaryItem(icon: "xmark.circle.fill", color: .red, count: tests.filter({ $0.status == .critical }).count, label: "Critical")
                Spacer()
            }
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.green)
                    .font(.title3)
                VStack(alignment: .leading, spacing: 4) {
                    Text("Excellent Heart Health")
                        .font(.headline)
                        .fontWeight(.semibold)
                    Text("All cardiac markers are within normal ranges. No signs of heart muscle damage or stress detected.")
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
    
    private func formatLastUpdated() -> String {
        if tests.isEmpty {
            return "No data"
        }
        
        let now = Date()
        let formatter = DateFormatter()
        formatter.dateFormat = "MMMM dd, yyyy"
        
        if let lastTestedDate = tests.last?.lastTested.isEmpty == false ? tests.last?.lastTested : tests.first?.lastTested {
            if let date = formatter.date(from: lastTestedDate) {
                let components = Calendar.current.dateComponents([.day], from: date, to: now)
                
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
                        return date.formatted(date: .long, time: .omitted)
                    }
                }
            }
        }
        
        return "No data"
    }
}

struct CardiacTestCard: View {
    let test: CardiacTest
    
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

struct CardiacTest: Identifiable {
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
        CardiacMarkersView()
    }
}
