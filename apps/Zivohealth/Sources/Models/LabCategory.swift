import SwiftUI
import Foundation

struct LabCategory: Identifiable, Codable {
    let id = UUID()
    let category: String
    let totalTests: Int
    let greenCount: Int
    let amberCount: Int
    let redCount: Int
    
    enum CodingKeys: String, CodingKey {
        case category
        case totalTests = "total_tests"
        case greenCount = "green_count"
        case amberCount = "amber_count"
        case redCount = "red_count"
    }
}

struct LabCategoriesResponse: Codable {
    let categories: [LabCategory]
}

struct LabTestResult: Identifiable, Codable {
    let id: Int
    let testName: String
    let testCategory: String
    let value: Double?
    let unit: String?
    let normalRangeMin: Double?
    let normalRangeMax: Double?
    let status: LabTestStatus
    let date: String
    let createdAt: String
    
    enum CodingKeys: String, CodingKey {
        case id
        case testName = "test_name"
        case testCategory = "test_category"
        case value
        case unit
        case normalRangeMin = "normal_range_min"
        case normalRangeMax = "normal_range_max"
        case status
        case date
        case createdAt = "created_at"
    }
}

enum LabTestStatus: String, Codable, CaseIterable {
    case green = "green"
    case amber = "amber"
    case red = "red"
    
    var color: Color {
        switch self {
        case .green:
            return .green
        case .amber:
            return .orange
        case .red:
            return .red
        }
    }
    
    var displayName: String {
        switch self {
        case .green:
            return "Normal"
        case .amber:
            return "Attention"
        case .red:
            return "Critical"
        }
    }
}

struct LabCategoryDetail: Codable {
    let category: String
    let tests: [LabTestResult]
    let summary: LabCategorySummary
}

struct LabCategorySummary: Codable {
    let totalTests: Int
    let greenCount: Int
    let amberCount: Int
    let redCount: Int
    
    enum CodingKeys: String, CodingKey {
        case totalTests = "total_tests"
        case greenCount = "green_count"
        case amberCount = "amber_count"
        case redCount = "red_count"
    }
}

// MARK: - Diabetes Panel Models
struct DiabetesPanelResponse: Codable {
    let tests: [DiabetesTestData]
    let category: String
    let totalTests: Int
    
    enum CodingKeys: String, CodingKey {
        case tests
        case category
        case totalTests = "totalTests"
    }
}

struct DiabetesTestData: Codable {
    let name: String
    let description: String
    let value: String
    let unit: String
    let normalRange: String
    let status: String
    let lastTested: String
    
    enum CodingKeys: String, CodingKey {
        case name
        case description
        case value
        case unit
        case normalRange
        case status
        case lastTested
    }
}

// MARK: - Liver Function Tests Models
struct LiverFunctionTestsResponse: Codable {
    let tests: [LiverFunctionTestData]
    let category: String
    let totalTests: Int
    
    enum CodingKeys: String, CodingKey {
        case tests
        case category
        case totalTests = "totalTests"
    }
}

struct LiverFunctionTestData: Codable {
    let name: String
    let description: String
    let value: String
    let unit: String
    let normalRange: String
    let status: String
    let lastTested: String
    
    enum CodingKeys: String, CodingKey {
        case name
        case description
        case value
        case unit
        case normalRange
        case status
        case lastTested
    }
}

// MARK: - Kidney Function Tests Models
struct KidneyFunctionTestsResponse: Codable {
    let tests: [KidneyFunctionTestData]
    let category: String
    let totalTests: Int
    
    enum CodingKeys: String, CodingKey {
        case tests
        case category
        case totalTests = "totalTests"
    }
}

struct KidneyFunctionTestData: Codable {
    let name: String
    let description: String
    let value: String
    let unit: String
    let normalRange: String
    let status: String
    let lastTested: String
    
    enum CodingKeys: String, CodingKey {
        case name
        case description
        case value
        case unit
        case normalRange
        case status
        case lastTested
    }
}

// MARK: - Dynamic Categories Models
struct AvailableCategoriesResponse: Codable {
    let categories: [DynamicCategoryData]
    let totalCategories: Int
    
    enum CodingKeys: String, CodingKey {
        case categories
        case totalCategories
    }
}

struct DynamicCategoryData: Codable {
    let name: String
    let icon: String
    let iconColor: String
    let totalTests: Int
    let greenCount: Int
    let amberCount: Int
    let redCount: Int
    
    enum CodingKeys: String, CodingKey {
        case name
        case icon
        case iconColor
        case totalTests
        case greenCount
        case amberCount
        case redCount
    }
}

struct CategoryTestsResponse: Codable {
    let tests: [CategoryTestData]
    let category: String
    let totalTests: Int
    
    enum CodingKeys: String, CodingKey {
        case tests
        case category
        case totalTests
    }
}

struct CategoryTestData: Codable {
    let name: String
    let description: String
    let value: String
    let unit: String
    let normalRange: String
    let status: String
    let lastTested: String
    
    enum CodingKeys: String, CodingKey {
        case name
        case description
        case value
        case unit
        case normalRange
        case status
        case lastTested
    }
}
