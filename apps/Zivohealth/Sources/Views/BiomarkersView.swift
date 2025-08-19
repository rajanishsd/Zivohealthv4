import SwiftUI
import Combine

struct BiomarkersView: View {
    var body: some View {
        if #available(iOS 16.0, *) {
            BiomarkersViewModern()
        } else {
            BiomarkersViewLegacy()
        }
    }
}

// MARK: - Modern iOS 16+ View
@available(iOS 16.0, *)
struct BiomarkersViewModern: View {
    @State private var categories: [SimpleBiomarkerCategory] = []
    @State private var isLoading = true
    
    var body: some View {
            biomarkersContent
    }
    
    private var biomarkersContent: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Health Progress Card with real data
                HealthProgressCard(categories: categories)
                
                // Key Insights Card
                KeyInsightsCard()
                
                // Health Reports Categories Card - Dynamic Version with Real Data
                SimpleDynamicBiomarkersCard(
                    categories: $categories,
                    isLoading: $isLoading
                )
                
                Spacer(minLength: 100)
            }
            .padding(.horizontal)
            .padding(.top, 8)
        }
        .background(Color(.systemGray6))
        .navigationTitle("Biomarkers")
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button(action: {
                    // Add biomarker action
                }) {
                    Image(systemName: "plus")
                }
            }
        }
        .onAppear {
            print("🔬 [BiomarkersViewModern] onAppear - Biomarkers view appeared")
        }
        .onDisappear {
            print("🔬 [BiomarkersViewModern] onDisappear - Biomarkers view disappeared")
        }
    }
}

// MARK: - Legacy iOS 15 View
struct BiomarkersViewLegacy: View {
    @State private var categories: [SimpleBiomarkerCategory] = []
    @State private var isLoading = true
    
    var body: some View {
        biomarkersContent
    }
    
    private var biomarkersContent: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Health Progress Card with real data
                HealthProgressCard(categories: categories)
                
                // Key Insights Card
                KeyInsightsCard()
                
                // Health Reports Categories Card - Dynamic Version with Real Data
                SimpleDynamicBiomarkersCard(
                    categories: $categories,
                    isLoading: $isLoading
                )
                
                Spacer(minLength: 100)
            }
            .padding(.horizontal)
            .padding(.top, 8)
        }
        .background(Color(.systemGray6))
        .navigationTitle("Biomarkers")
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button(action: {
                    // Add biomarker action
                }) {
                    Image(systemName: "plus")
                }
            }
        }
        .onAppear {
            print("🔬 [BiomarkersViewLegacy] onAppear - Biomarkers view appeared")
        }
        .onDisappear {
            print("🔬 [BiomarkersViewLegacy] onDisappear - Biomarkers view disappeared")
        }
    }
}

// MARK: - Health Progress Card
struct HealthProgressCard: View {
    let categories: [SimpleBiomarkerCategory]
    
    // Calculate health score based on test results
    private var healthScore: Int {
        let totalTests = categories.reduce(0) { $0 + $1.totalTests }
        let greenTests = categories.reduce(0) { $0 + $1.greenCount }
        let amberTests = categories.reduce(0) { $0 + $1.amberCount }
        let redTests = categories.reduce(0) { $0 + $1.redCount }
        
        guard totalTests > 0 else { return 0 }
        
        // Scoring algorithm:
        // Green tests: 100% score
        // Amber tests: 60% score  
        // Red tests: 0% score
        let totalScore = (greenTests * 100) + (amberTests * 60) + (redTests * 0)
        let maxPossibleScore = totalTests * 100
        
        return Int(Double(totalScore) / Double(maxPossibleScore) * 100)
    }
    
    private var progressValue: Double {
        return Double(healthScore) / 100.0
    }
    
    private var progressDescription: String {
        switch healthScore {
        case 90...100:
            return "Excellent health markers across all categories"
        case 80..<90:
            return "Good progress with minor areas for improvement"
        case 70..<80:
            return "Most markers are good, some areas need attention"
        case 60..<70:
            return "Several markers need improvement"
        case 50..<60:
            return "Multiple areas require attention"
        default:
            return "Many markers need immediate attention"
        }
    }
    
    private var statusText: String {
        switch healthScore {
        case 90...100:
            return "Excellent"
        case 80..<90:
            return "Very Good"
        case 70..<80:
            return "Good Progress"
        case 60..<70:
            return "Fair"
        case 50..<60:
            return "Needs Work"
        default:
            return "Poor"
        }
    }
    
    private var progressColors: [Color] {
        switch healthScore {
        case 80...100:
            return [.green, .mint]
        case 60..<80:
            return [.green, .yellow, .orange]
        default:
            return [.orange, .red]
        }
    }
    
    var body: some View {
        VStack(spacing: 20) {
            // Header
            HStack {
                Image(systemName: "chart.pie.fill")
                    .foregroundColor(.purple)
                    .font(.title2)
                Text("Health Progress")
                    .font(.title3)
                    .fontWeight(.semibold)
                Spacer()
                Text("Latest Results")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            // Progress Circle
            ZStack {
                Circle()
                    .stroke(Color.gray.opacity(0.2), lineWidth: 12)
                    .frame(width: 120, height: 120)
                
                Circle()
                    .trim(from: 0, to: progressValue)
                    .stroke(
                        AngularGradient(
                            colors: progressColors,
                            center: .center
                        ),
                        style: StrokeStyle(lineWidth: 12, lineCap: .round)
                    )
                    .frame(width: 120, height: 120)
                    .rotationEffect(.degrees(-90))
                
                VStack(spacing: 4) {
                    Text("\(healthScore)/100")
                        .font(.title)
                        .fontWeight(.bold)
                        .foregroundColor(.primary)
                    Text(statusText)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            // Progress Description
            Text(progressDescription)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            
            // Test Summary
            HStack(spacing: 20) {
                VStack(spacing: 4) {
                    Text("\(categories.reduce(0) { $0 + $1.totalTests })")
                        .font(.headline)
                        .fontWeight(.bold)
                    Text("Total Tests")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                VStack(spacing: 4) {
                    Text("\(categories.reduce(0) { $0 + $1.greenCount })")
                        .font(.headline)
                        .fontWeight(.bold)
                        .foregroundColor(.green)
                    Text("Normal")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                VStack(spacing: 4) {
                    Text("\(categories.reduce(0) { $0 + $1.amberCount })")
                        .font(.headline)
                        .fontWeight(.bold)
                        .foregroundColor(.orange)
                    Text("Elevated")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                VStack(spacing: 4) {
                    Text("\(categories.reduce(0) { $0 + $1.redCount })")
                        .font(.headline)
                        .fontWeight(.bold)
                        .foregroundColor(.red)
                    Text("Critical")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
    }
}

// MARK: - Key Insights Card
struct KeyInsightsCard: View {
    private let insights = [
        InsightItem(
            icon: "exclamationmark.triangle.fill",
            iconColor: .red,
            title: "Immediate Attention: LDL Cholesterol Elevated",
            description: "Your LDL is 165 mg/dL (target: <100). Consider reducing saturated fats and increasing fiber intake."
        ),
        InsightItem(
            icon: "exclamationmark.circle.fill",
            iconColor: .orange,
            title: "Monitor: Vitamin D Levels Low",
            description: "Your Vitamin D is 22 ng/mL (target: 30-50). Consider supplements and more sunlight exposure."
        ),
        InsightItem(
            icon: "checkmark.circle.fill",
            iconColor: .green,
            title: "Great: Kidney Function Normal",
            description: "Your creatinine and eGFR levels are within healthy ranges. Keep up the good hydration!"
        )
    ]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                Image(systemName: "lightbulb.fill")
                    .foregroundColor(.orange)
                    .font(.title2)
                Text("Key Insights")
                    .font(.title3)
                    .fontWeight(.semibold)
                Spacer()
            }
            
            // Insights List
            VStack(spacing: 12) {
                ForEach(Array(insights.enumerated()), id: \.offset) { index, insight in
                    InsightRowView(insight: insight)
                    if index < insights.count - 1 {
                        Divider()
                    }
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
    }
}

// MARK: - Supporting Views
struct InsightRowView: View {
    let insight: InsightItem
    
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: insight.icon)
                    .font(.title3)
                .foregroundColor(insight.iconColor)
                .frame(width: 24)
            
            VStack(alignment: .leading, spacing: 4) {
                Text(insight.title)
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(.primary)
                
                Text(insight.description)
                    .font(.system(size: 13))
                    .foregroundColor(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            
            Spacer()
        }
    }
}

struct StatusDot: View {
    let count: Int
    let color: Color
    
    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            Text("\(count)")
                .font(.caption2)
                .fontWeight(.medium)
                .foregroundColor(color)
        }
    }
}

// MARK: - Data Models
struct InsightItem {
    let icon: String
    let iconColor: Color
    let title: String
    let description: String
}

struct LabCategoryItem {
    let name: String
    let icon: String
    let iconColor: Color
    let greenCount: Int
    let amberCount: Int
    let redCount: Int
    let totalTests: Int
}

// MARK: - Static Biomarkers Card Legacy (iOS 15)
struct BiomarkersCardLegacy: View {
    private let categories = [
        LabCategoryItem(
            name: "Diabetes Panel",
            icon: "drop.fill",
            iconColor: .green,
            greenCount: 3,
            amberCount: 1,
            redCount: 1,
            totalTests: 5
        ),
        LabCategoryItem(
            name: "Thyroid Profile",
            icon: "bolt.fill",
            iconColor: .purple,
            greenCount: 2,
            amberCount: 1,
            redCount: 1,
            totalTests: 4
        ),
        LabCategoryItem(
            name: "Lipid Profile",
            icon: "waveform.path.ecg",
            iconColor: .red,
            greenCount: 4,
            amberCount: 1,
            redCount: 1,
            totalTests: 6
        ),
        LabCategoryItem(
            name: "Complete Blood Count",
            icon: "drop.circle.fill",
            iconColor: .red,
            greenCount: 6,
            amberCount: 1,
            redCount: 1,
            totalTests: 8
        ),
        LabCategoryItem(
            name: "Infection Markers",
            icon: "shield.fill",
            iconColor: .orange,
            greenCount: 4,
            amberCount: 2,
            redCount: 0,
            totalTests: 6
        ),
        LabCategoryItem(
            name: "Electrolyte Panel",
            icon: "atom",
            iconColor: .blue,
            greenCount: 5,
            amberCount: 1,
            redCount: 0,
            totalTests: 6
        ),
        LabCategoryItem(
            name: "Vitamin & Mineral Panel",
            icon: "pills",
            iconColor: .green,
            greenCount: 8,
            amberCount: 3,
            redCount: 1,
            totalTests: 12
        ),
        LabCategoryItem(
            name: "Liver Function Tests (LFT)",
            icon: "leaf.fill",
            iconColor: .brown,
            greenCount: 6,
            amberCount: 1,
            redCount: 0,
            totalTests: 7
        ),
        LabCategoryItem(
            name: "Kidney Function Tests (KFT)",
            icon: "drop.triangle",
            iconColor: .cyan,
            greenCount: 4,
            amberCount: 0,
            redCount: 0,
            totalTests: 4
        ),
        LabCategoryItem(
            name: "Cardiac Markers",
            icon: "heart.fill",
            iconColor: .pink,
            greenCount: 3,
            amberCount: 1,
            redCount: 0,
            totalTests: 4
        ),
        LabCategoryItem(
            name: "Urine Routine",
            icon: "drop.circle",
            iconColor: .yellow,
            greenCount: 5,
            amberCount: 2,
            redCount: 1,
            totalTests: 8
        ),
        LabCategoryItem(
            name: "Others",
            icon: "doc.text",
            iconColor: .gray,
            greenCount: 4,
            amberCount: 3,
            redCount: 2,
            totalTests: 9
        )
    ]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                Image(systemName: "doc.text.fill")
                    .foregroundColor(.blue)
                    .font(.title2)
                Text("Biomarkers")
                    .font(.title3)
                    .fontWeight(.semibold)
                Spacer()
            }
            
            // Categories List
            VStack(spacing: 12) {
                ForEach(categories, id: \.name) { category in
                    CategoryRowViewLegacy(category: category)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
    }
}

// MARK: - Legacy Category Row (iOS 15)
struct CategoryRowViewLegacy: View {
    let category: LabCategoryItem
    
    var body: some View {
        NavigationLink(destination: destinationView(for: category.name)) {
            categoryContent
        }
        .buttonStyle(.plain)
    }
    
    @ViewBuilder
    private func destinationView(for categoryName: String) -> some View {
        switch categoryName {
        case "Diabetes Panel":
            DiabetesPanelView()
                .navigationBarHidden(true)
        case "Thyroid Profile":
            ThyroidProfileView()
                .navigationBarHidden(true)
        case "Lipid Profile":
            LipidProfileView()
                .navigationBarHidden(true)
        case "Complete Blood Count":
            CompleteBloodCountView()
                .navigationBarHidden(true)
        case "Liver Function Tests (LFT)":
            LiverFunctionTestsView()
                .navigationBarHidden(true)
        case "Kidney Function Tests (KFT)":
            KidneyFunctionTestsView()
                .navigationBarHidden(true)
        case "Electrolyte Panel":
            ElectrolytePanelView()
                .navigationBarHidden(true)
        case "Infection Markers":
            InfectionMarkersView()
                .navigationBarHidden(true)
        case "Vitamin & Mineral Panel":
            VitaminMineralPanelView()
                .navigationBarHidden(true)
        case "Cardiac Markers":
            CardiacMarkersView()
                .navigationBarHidden(true)
        case "Urine Routine":
            UrineRoutineView()
                .navigationBarHidden(true)
        case "Others":
            OthersView()
                .navigationBarHidden(true)
        default:
            Text("Coming Soon: \(categoryName)")
                .navigationTitle(categoryName)
        }
    }
    
    private var categoryContent: some View {
        HStack(spacing: 16) {
            // Category icon
            Image(systemName: category.icon)
                .font(.title2)
                .foregroundColor(category.iconColor)
                .frame(width: 32, height: 32)
            
            VStack(alignment: .leading, spacing: 8) {
                // Category name
                Text(category.name)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(.primary)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
                
                // Status dots
                HStack(spacing: 8) {
                    StatusDot(count: category.greenCount, color: .green)
                    StatusDot(count: category.amberCount, color: .orange)
                    StatusDot(count: category.redCount, color: .red)
                    Spacer()
                }
                
                // Total tests
                Text("\(category.totalTests) tests")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            // Chevron
            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(16)
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 1)
    }
}

// MARK: - Preview
#Preview {
    NavigationView {
        BiomarkersView()
    }
} 