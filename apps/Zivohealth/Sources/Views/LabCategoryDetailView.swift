import SwiftUI
import Combine

struct LabCategoryDetailView: View {
    let category: String
    private let apiService = LabReportsAPIService.shared
    @State private var categoryDetail: LabCategoryDetail?
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var cancellables = Set<AnyCancellable>()
    @AppStorage("apiEndpoint") private var apiEndpoint = AppConfig.defaultAPIEndpoint
    
    var body: some View {
        ScrollView {
            if isLoading {
                ProgressView("Loading tests...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .padding()
            } else if let error = errorMessage {
                VStack(spacing: 16) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.largeTitle)
                        .foregroundColor(.orange)
                    Text("Error loading tests")
                        .font(.title2)
                        .fontWeight(.semibold)
                    Text(error)
                        .font(.body)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                    Button("Retry") {
                        loadCategoryDetails()
                    }
                    .buttonStyle(.borderedProminent)
                }
                .padding()
            } else if let detail = categoryDetail {
                LazyVStack(spacing: 16) {
                    // Category Header
                    categoryHeaderCard(detail: detail)
                        .cardStyle()
                    
                    // Tests List
                    ForEach(detail.tests) { test in
                        labTestCard(test: test)
                            .cardStyle()
                    }
                    
                    Spacer(minLength: 100)
                }
                .padding(.horizontal)
                .padding(.top, 8)
            }
        }
        .navigationTitle(category)
        .navigationBarTitleDisplayMode(.large)
        .onAppear {
            print("🔍 [LabCategoryDetailView] onAppear called for category: \(category)")
            loadCategoryDetails()
        }
        .onDisappear {
            print("❌ [LabCategoryDetailView] onDisappear called for category: \(category)")
        }
    }
    
    private func categoryHeaderCard(detail: LabCategoryDetail) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "chart.bar.doc.horizontal")
                    .foregroundColor(.blue)
                    .font(.title2)
                Text("Test Summary")
                    .font(.title3)
                    .fontWeight(.semibold)
                Spacer()
            }
            
            // Status counts
            HStack(spacing: 0) {
                statusColumn(
                    title: "Normal",
                    count: detail.summary.greenCount,
                    color: .green,
                    icon: "checkmark.circle.fill"
                )
                .frame(maxWidth: .infinity)
                
                statusColumn(
                    title: "Attention",
                    count: detail.summary.amberCount,
                    color: .orange,
                    icon: "exclamationmark.triangle.fill"
                )
                .frame(maxWidth: .infinity)
                
                statusColumn(
                    title: "Critical",
                    count: detail.summary.redCount,
                    color: .red,
                    icon: "exclamationmark.circle.fill"
                )
                .frame(maxWidth: .infinity)
            }
        }
        .padding()
    }
    
    private func statusColumn(title: String, count: Int, color: Color, icon: String) -> some View {
        VStack(spacing: 8) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(color)
            
            Text("\(count)")
                .font(.title2)
                .fontWeight(.bold)
                .foregroundColor(color)
            
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }
    
    private func labTestCard(test: LabTestResult) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            // Test header
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(test.testName)
                        .font(.headline)
                        .fontWeight(.semibold)
                    
                    if let value = test.value, let unit = test.unit {
                        Text("\(value, specifier: "%.1f") \(unit)")
                            .font(.subheadline)
                            .foregroundColor(.primary)
                    }
                }
                
                Spacer()
                
                // Status badge
                HStack(spacing: 4) {
                    Circle()
                        .fill(test.status.color)
                        .frame(width: 8, height: 8)
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
            
            // Normal range
            if let minRange = test.normalRangeMin, let maxRange = test.normalRangeMax {
                HStack {
                    Text("Normal Range:")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("\(minRange, specifier: "%.1f") - \(maxRange, specifier: "%.1f") \(test.unit ?? "")")
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(.secondary)
                    Spacer()
                }
            }
            
            // Date
            HStack {
                Image(systemName: "calendar")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text(test.date)
                    .font(.caption)
                    .foregroundColor(.secondary)
                Spacer()
            }
        }
        .padding()
    }
    
    private func loadCategoryDetails() {
        print("🔄 [LabCategoryDetailView] Loading details for category: \(category)")
        isLoading = true
        errorMessage = nil
        
        // Create a completely independent API call to avoid any shared state issues
        guard let encodedCategory = category.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(apiEndpoint)/api/v1/lab-reports/category/\(encodedCategory)") else {
            print("❌ [LabCategoryDetailView] Invalid URL for category: \(category)")
            isLoading = false
            errorMessage = "Invalid URL"
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        
        // Add authentication token if available
        let token = NetworkService.shared.getCurrentToken()
        if !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: LabCategoryDetail.self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .sink(
                receiveCompletion: { completion in
                    isLoading = false
                    print("📡 [LabCategoryDetailView] API call completed for \(category)")
                    if case .failure(let error) = completion {
                        print("❌ [LabCategoryDetailView] API error: \(error.localizedDescription)")
                        errorMessage = error.localizedDescription
                    }
                },
                receiveValue: { detail in
                    print("✅ [LabCategoryDetailView] Received data for \(category): \(detail.tests.count) tests")
                    // Add delay to prevent any potential race conditions
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                        print("🔄 [LabCategoryDetailView] Setting categoryDetail after delay")
                        // Temporarily disable to test if state update is causing the issue
                        // categoryDetail = detail
                        print("🧪 [LabCategoryDetailView] State update disabled for testing")
                    }
                }
            )
            .store(in: &cancellables)
    }
}

struct LabCategoryDetailView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            LabCategoryDetailView(category: "Liver Function Tests (LFT)")
        }
    }
}
